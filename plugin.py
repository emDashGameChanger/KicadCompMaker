import pcbnew
import os
import wx
import requests
import json
import time
import jinja2
import wx.lib.delayedresult as delayedresult
from .gui import DigikeyDialog, ProgressCounterDialog, ResultDialog, CredentialsDialog
from .TH_Resistors import process_resistor, search_tht_resistor
from .TH_Radial_ElectrolyticCapacitors import process_capacitor, search_tht_capacitor
from .TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor

def generate_library_files(data):
    # Debug: Display variables
    print("DEBUG: Generating Library Files with Data:")
    print(json.dumps(data, indent=4, default=str))

    # Paths
    plugin_dir = os.path.dirname(__file__)
    
    fp_lib_name = data.get("fp_lib_name", "Digikey_Import_FP")
    sym_lib_name = data.get("sym_lib_name", "Digikey_Import")
    
    fp_lib_path = os.path.expanduser(f"~/.local/share/kicad/9.0/footprints/{fp_lib_name}.pretty")
    sym_lib_file = os.path.expanduser(f"~/.local/share/kicad/9.0/symbols/{sym_lib_name}.kicad_sym")
    
    # Ensure directories exist
    if not os.path.exists(fp_lib_path):
        os.makedirs(fp_lib_path)
    if not os.path.exists(os.path.dirname(sym_lib_file)):
        os.makedirs(os.path.dirname(sym_lib_file))
        
    # Jinja2 Setup
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(plugin_dir))
    
    # 1. Footprint Generation
    fp_name = data['footprint_name']
    fp_file_path = os.path.join(fp_lib_path, fp_name)
    fp_template_file = data.get("fp_template", "footprintTemplates/TH_ResistorTemplate.kicad_mod")
    
    try:
        template = env.get_template(fp_template_file)
        rendered_fp = template.render(data['Footprint Data'])
        
        # Write to global library
        if not os.path.exists(fp_file_path):
            with open(fp_file_path, 'w') as f:
                f.write(rendered_fp)
            
    except Exception as e:
        return False, f"Footprint Error: {e}"

    # 2. Symbol Generation
    sym_data = data['Symbol Data']
    symbol_name = sym_data['symbol']
    
    sym_preamble = data.get("sym_preamble", '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s resistor generator")\n\t(generator_version ".01")\n')
    sym_template_file = data.get("sym_template", "symbolTemplates/ResistorSymbolTemplate.txt")
    
    try:
        template = env.get_template(sym_template_file)
        rendered_sym = template.render(sym_data)
        
        def append_to_lib(lib_path, content_to_add):
            if not os.path.exists(lib_path):
                with open(lib_path, 'w') as f:
                    f.write(sym_preamble + ")")
            
            with open(lib_path, 'r+') as f:
                content = f.read()
                if f'(symbol "{symbol_name}"' not in content:
                    last_paren_idx = content.rfind(')')
                    if last_paren_idx != -1:
                        new_content = content[:last_paren_idx] + "\n" + content_to_add + "\n)"
                        f.seek(0)
                        f.write(new_content)
                        f.truncate()

        # Write to global library
        append_to_lib(sym_lib_file, rendered_sym)
        
        # Write to local plugin folder
        local_sym_lib_file = os.path.join(plugin_dir, f"{sym_lib_name}.kicad_sym")
        append_to_lib(local_sym_lib_file, rendered_sym)

    except Exception as e:
        return False, f"Symbol Error: {e}"

    return True, f"Generated: {symbol_name}"

class DigikeyPlugin(pcbnew.ActionPlugin):
    def __init__(self):
        pcbnew.ActionPlugin.__init__(self)
        # Initialize state with defaults (Index 0 for both)
        self.state = {'pwr_idx': 0, 'tol_idx': 0, 'film_vol_idx': 6}
        self.client_id = None
        self.client_secret = None
        self.progress_dialog = None
        self.token = None
        self.token_time = 0

    def defaults(self):
        """
        Define the metadata for the plugin. 
        """
        self.name = "Digikey Importer"
        self.category = "Footprint Wizards"
        self.description = "Download parts from Digikey API"
        self.show_toolbar_button = True # This places the button on the top toolbar
        
        # Set the icon file path
        # We use os.path.dirname(__file__) to ensure we look in the plugin's folder
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        """
        The entry point when the toolbar button is clicked.
        """
        if not self._ensure_credentials():
            return  # User cancelled or failed to provide credentials

        pcbnew_window = wx.FindWindowByName("PcbFrame")
        dlg = DigikeyDialog(pcbnew_window, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            # Save Tab States
            self.state['main_tab'] = dlg.notebook.GetSelection()
            self.state['tht_tab'] = dlg.tht_notebook.GetSelection()
            self.state['cap_tab'] = dlg.tht_cap_notebook.GetSelection()

            # Save the state of Power Rating
            for i, rb in enumerate(dlg.tht_res_pwr_radios):
                if rb.GetValue():
                    self.state['pwr_idx'] = i
            
            # Save the state of Tolerance
            for i, rb in enumerate(dlg.tht_res_tol_radios):
                if rb.GetValue():
                    self.state['tol_idx'] = i
            
            # Save Capacitor States
            for key, controls in dlg.cap_tabs.items():
                for i, rb in enumerate(controls['type']):
                    if rb.GetValue(): self.state[f'{key}_type_idx'] = i
                for i, rb in enumerate(controls['vol']):
                    if rb.GetValue(): self.state[f'{key}_vol_idx'] = i
            
            # Trigger Search
            # Check which tab is active
            if dlg.notebook.GetSelection() == 0: # Through Hole
                if dlg.tht_notebook.GetSelection() == 0: # Resistors
                    res_val = dlg.tht_res_val.GetValue()
                    if res_val:
                        self.progress_dialog = ProgressCounterDialog(pcbnew_window, "API Call", "Searching for resistors...")
                        self.progress_dialog.Show()
                        delayedresult.startWorker(self._on_api_result_resistor, self._api_worker_resistor, 
                                                  wargs=[res_val, self.state['pwr_idx'], self.state['tol_idx']])

                elif dlg.tht_notebook.GetSelection() == 1: # Capacitors
                    sel = dlg.tht_cap_notebook.GetSelection()
                    tab_keys = ['alum', 'film', 'mica']
                    if sel < len(tab_keys):
                        key = tab_keys[sel]
                        controls = dlg.cap_tabs[key]
                        
                        cap_val = controls['val'].GetValue()
                        if cap_val:
                            cap_val = cap_val.replace("u", "µ")
                            vol_idx = self.state.get(f'{key}_vol_idx', 0)
                            vol_str = controls['vol_opts'][vol_idx]
                            cust_vol = controls['cust_vol'].GetValue()
                            if cust_vol: vol_str = cust_vol
                            
                            type_idx = self.state.get(f'{key}_type_idx', 0)
                            
                            # Configs
                            configs = {
                                'alum': ('58', {'designator': 'CP', 'sym_lib': 'CP_TH_emDashGameChanger', 'proc': 'alum'}),
                                'film': ('60', {'designator': 'C', 'sym_lib': 'C_TH_emDashGameChanger', 'proc': 'disc'}),
                                'mica': ('61', {'designator': 'C', 'sym_lib': 'C_TH_emDashGameChanger', 'proc': 'disc'})
                            }
                            cat_id, lib_config = configs.get(key, ('58', {}))

                            self.progress_dialog = ProgressCounterDialog(pcbnew_window, "API Call", "Searching for capacitors...")
                            self.progress_dialog.Show()
                            delayedresult.startWorker(self._on_api_result_capacitor, self._api_worker_capacitor, 
                                                      wargs=[cap_val, vol_str, type_idx, cat_id], cargs=[lib_config])

        dlg.Destroy()

    def _ensure_credentials(self):
        # If already loaded, do nothing.
        if self.client_id and self.client_secret:
            return True

        # Try environment variables
        self.client_id = os.environ.get("DIGIKEY_CLIENT_ID")
        self.client_secret = os.environ.get("DIGIKEY_CLIENT_SECRET")
        if self.client_id and self.client_secret:
            return True

        # Fallback: Try to load from config.json
        # config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(PLUGIN_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.client_id = config.get("DIGIKEY_CLIENT_ID")
                    self.client_secret = config.get("DIGIKEY_CLIENT_SECRET")
                if self.client_id and self.client_secret:
                    return True
            except Exception:
                # Corrupt json or other issue, we'll proceed to ask the user
                pass
        
        # If we are here, no credentials found. Prompt user.
        client_id, client_secret = self._prompt_for_credentials()

        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
            
            # Save to config.json
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                except Exception:
                    pass
            config["DIGIKEY_CLIENT_ID"] = client_id
            config["DIGIKEY_CLIENT_SECRET"] = client_secret
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
            except Exception as e:
                parent = wx.FindWindowByName("PcbFrame")
                wx.MessageBox(f"Could not save credentials to config.json:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=parent)
            
            return True # We have the credentials for this session anyway
        
        parent = wx.FindWindowByName("PcbFrame")
        if client_id is not None or client_secret is not None: # i.e. user didn't cancel both
            wx.MessageBox("Client ID and Secret are required to use the Digikey API.", "Credentials Required", wx.OK | wx.ICON_WARNING, parent=parent)
        return False

    def _prompt_for_credentials(self):
        parent = wx.FindWindowByName("PcbFrame")
        with CredentialsDialog(parent) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                return dlg.get_credentials()
        return None, None

    def _api_worker_resistor(self, res_val, pwr_idx, tol_idx):
        token = self.get_token()
        if token:
            return search_tht_resistor(res_val, pwr_idx, tol_idx, token, self.client_id, lambda: self.get_token(force_refresh=True))
        return None

    def _on_api_result_resistor(self, delayedResult):
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        try:
            results = delayedResult.get()
            if results and results.get("ProductsCount", 0) > 0:
                pcbnew_window = wx.FindWindowByName("PcbFrame")
                res_dlg = ResultDialog(pcbnew_window, results, processor=process_resistor, generator_callback=generate_library_files)
                res_dlg.ShowModal()
                res_dlg.Destroy()
            elif results is None:
                wx.MessageBox("API call failed. This could be due to an authentication issue.", "API Error", wx.OK | wx.ICON_ERROR)
            else: # results is not None but no products
                wx.MessageBox("No results found for the specified criteria.", "Info", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"API Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _api_worker_capacitor(self, cap_val, vol_str, type_idx, cat_id):
        token = self.get_token()
        if token:
            if cat_id == '60':
                return search_tht_disc_capacitor(cap_val, vol_str, cat_id, token, self.client_id, lambda: self.get_token(force_refresh=True))
            return search_tht_capacitor(cap_val, vol_str, type_idx, cat_id, token, self.client_id, lambda: self.get_token(force_refresh=True))
        return None

    def _on_api_result_capacitor(self, delayedResult, lib_config=None):
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        try:
            results = delayedResult.get()
            if results and results.get("ProductsCount", 0) > 0:
                pcbnew_window = wx.FindWindowByName("PcbFrame")
                
                proc_type = lib_config.get('proc', 'alum') if lib_config else 'alum'
                if proc_type == 'disc':
                    processor = lambda p: process_disc_capacitor(p, lib_config)
                else:
                    processor = lambda p: process_capacitor(p, lib_config)

                res_dlg = ResultDialog(pcbnew_window, results, processor=processor, generator_callback=generate_library_files)
                res_dlg.ShowModal()
                res_dlg.Destroy()
            elif results is None:
                wx.MessageBox("API call failed. This could be due to an authentication issue.", "API Error", wx.OK | wx.ICON_ERROR)
            else: # results is not None but no products
                wx.MessageBox("No results found for the specified criteria.", "Info", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"API Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def get_token(self, force_refresh=False):
        if not force_refresh and self.token and (time.time() - self.token_time < 300):
            return self.token

        url = "https://api.digikey.com/v1/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.token_time = time.time()
            return self.token
        else:
            print(f"Token Error: {response.text}")
            return None
