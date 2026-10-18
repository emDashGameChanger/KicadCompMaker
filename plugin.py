#!/usr/bin/env python3

try:
    import pcbnew
except ImportError:
    class pcbnew:
        class ActionPlugin:
            def register(self): pass

import os
import wx
import requests
import json
import time
import jinja2
import wx.lib.delayedresult as delayedresult
try:
    from .gui import DigikeyDialog, ProgressCounterDialog, ResultDialog, CredentialsDialog, BatchResultDialog, PinoutConfirmDialog
    from .TH_Resistors import process_resistor, search_tht_resistor
    from .TH_Radial_ElectrolyticCapacitors import process_capacitor, search_tht_capacitor
    from .TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor
    from .TH_Diodes import process_diode, search_diode
    from .TH_Transistors_BJT import process_bjt, search_tht_bjt
    from .TH_Transistors_JFET import process_jfet, search_tht_jfet
    from .TH_Transistors_MOSFET import process_mosfet, search_tht_mosfet
    from .TH_Transistor_Common import apply_pinout
    from .SMD_Resistors import search_smd_resistor, process_smd_resistor
    from .SMD_Capacitors import (search_smd_mlcc, process_smd_mlcc, search_smd_tantalum,
                                    process_smd_tantalum, search_smd_aluminum, process_smd_aluminum)
    from .gui import (SMD_RES_SIZE_OPTS, SMD_RES_TOL_OPTS, SMD_RES_PWR_OPTS, SMD_CAP_SIZE_OPTS,
                       SMD_CAP_VOL_OPTS, SMD_CAP_DIELECTRIC_OPTS, SMD_TANT_CASE_OPTS)
    from .BatchImport import run_batch, record_generate, CAP_TAB_CONFIGS
except ImportError:
    from gui import DigikeyDialog, ProgressCounterDialog, ResultDialog, CredentialsDialog, BatchResultDialog, PinoutConfirmDialog
    from TH_Resistors import process_resistor, search_tht_resistor
    from TH_Radial_ElectrolyticCapacitors import process_capacitor, search_tht_capacitor
    from TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor
    from TH_Diodes import process_diode, search_diode
    from TH_Transistors_BJT import process_bjt, search_tht_bjt
    from TH_Transistors_JFET import process_jfet, search_tht_jfet
    from TH_Transistors_MOSFET import process_mosfet, search_tht_mosfet
    from TH_Transistor_Common import apply_pinout
    from SMD_Resistors import search_smd_resistor, process_smd_resistor
    from SMD_Capacitors import (search_smd_mlcc, process_smd_mlcc, search_smd_tantalum,
                                    process_smd_tantalum, search_smd_aluminum, process_smd_aluminum)
    from gui import (SMD_RES_SIZE_OPTS, SMD_RES_TOL_OPTS, SMD_RES_PWR_OPTS, SMD_CAP_SIZE_OPTS,
                       SMD_CAP_VOL_OPTS, SMD_CAP_DIELECTRIC_OPTS, SMD_TANT_CASE_OPTS)
    from BatchImport import run_batch, record_generate, CAP_TAB_CONFIGS

def generate_library_files(data):
    # Debug: Display variables
    print("DEBUG: Generating Library Files with Data:")
    print(json.dumps(data, indent=4, default=str))

    # Processors flag parts they can't map to a valid symbol/footprint (e.g. an
    # SMD diode in a 3-pin package) instead of raising - write nothing for those.
    if data.get("error"):
        return False, data["error"]

    # Paths
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    
    fp_lib_name = data.get("fp_lib_name", "Digikey_Import_FP")
    sym_lib_name = data.get("sym_lib_name", "Digikey_Import")
    
    fp_lib_path = os.path.expanduser(f"~/.local/share/kicad/9.0/footprints/{fp_lib_name}.pretty")
    sym_lib_file = os.path.expanduser(f"~/.local/share/kicad/9.0/symbols/{sym_lib_name}.kicad_sym")
    
    # Ensure directories exist
    if not data.get("skip_footprint_gen") and not os.path.exists(fp_lib_path):
        os.makedirs(fp_lib_path)
    if not os.path.exists(os.path.dirname(sym_lib_file)):
        os.makedirs(os.path.dirname(sym_lib_file))
        
    # Jinja2 Setup
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(plugin_dir))
    
    # 1. Footprint Generation - skipped when a stock KiCad footprint is reused by
    # reference instead (e.g. diodes pointing at Diode_THT:<name>)
    if not data.get("skip_footprint_gen"):
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
        if "sym_text" in data:
            rendered_sym = data["sym_text"]  # pre-built (Stock_Parts copies a stock symbol)
        else:
            rendered_sym = env.get_template(sym_template_file).render(sym_data)
        
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
                        return True
            return False

        # Write to global library
        appended_global = append_to_lib(sym_lib_file, rendered_sym)

        # Write to local plugin folder
        local_sym_lib_file = os.path.join(plugin_dir, f"{sym_lib_name}.kicad_sym")
        appended_local = append_to_lib(local_sym_lib_file, rendered_sym)

    except Exception as e:
        return False, f"Symbol Error: {e}"

    # NOTE: callers (e.g. BatchImport.run_batch) key off this exact "Already exists:" prefix
    # to classify a line as a duplicate vs. a new part - keep the prefix stable.
    if appended_global or appended_local:
        return True, f"Generated: {symbol_name}"
    return True, f"Already exists: {symbol_name}"

class DigikeyPlugin(pcbnew.ActionPlugin):
    def __init__(self):
        pcbnew.ActionPlugin.__init__(self)
        # Initialize state with defaults (Index 0 for both)
        self.state = {'pwr_idx': 0, 'tol_idx': 0, 'film_vol_idx': 6, 'res_comp_idx': 0}
        self.client_id = None
        self.client_secret = None
        self.progress_dialog = None
        self.token = None
        self.token_time = 0
        self.dlg = None

    def defaults(self):
        """
        Define the metadata for the plugin. 
        """
        self.name = "Digikey Importer"
        self.category = "Footprint Wizards"
        self.description = "Download parts from Digikey API"
        self.show_toolbar_button = True # This places the button on the top toolbar
        
        # Set the icon file path
        # Use realpath so this resolves correctly even when invoked via a symlink
        # (e.g. the ~/.local/bin/kicadcompmaker desktop launcher)
        self.icon_file_name = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'icon.png')

    def Run(self):
        """
        The entry point when the toolbar button is clicked.
        """
        if not self._ensure_credentials():
            return  # User cancelled or failed to provide credentials

        pcbnew_window = wx.FindWindowByName("PcbFrame")
        self.dlg = DigikeyDialog(pcbnew_window, self.state)
        
        # Change OK button to "Search" and bind to keep dialog open
        btn_ok = self.dlg.FindWindow(wx.ID_OK)
        if btn_ok:
            btn_ok.SetLabel("Search")
            self.dlg.Bind(wx.EVT_BUTTON, self.on_search_click, id=wx.ID_OK)

        self.dlg.ShowModal()
        self.dlg.Destroy()
        self.dlg = None

    @staticmethod
    def _selected_idx(radios, default=0):
        for i, rb in enumerate(radios):
            if rb.GetValue():
                return i
        return default

    def _save_state(self, dlg):
        # Tab selections
        self.state['main_tab'] = dlg.notebook.GetSelection()
        self.state['tht_tab'] = dlg.tht_notebook.GetSelection()
        self.state['cap_tab'] = dlg.tht_cap_notebook.GetSelection()
        self.state['transistor_tab'] = dlg.tht_transistor_notebook.GetSelection()
        self.state['smd_tab'] = dlg.smd_notebook.GetSelection()
        self.state['smd_cap_tab'] = dlg.smd_cap_notebook.GetSelection()
        self.state['smd_transistor_tab'] = dlg.smd_transistor_notebook.GetSelection()
        self.state['smd_handsolder'] = dlg.smd_handsolder.GetValue()

        # THT resistor / capacitor groups (built before the generic registry)
        self.state['pwr_idx'] = self._selected_idx(dlg.tht_res_pwr_radios)
        self.state['tol_idx'] = self._selected_idx(dlg.tht_res_tol_radios)
        self.state['res_comp_idx'] = self._selected_idx(dlg.tht_res_comp_radios)
        for key, controls in dlg.cap_tabs.items():
            self.state[f'{key}_type_idx'] = self._selected_idx(controls['type'])
            self.state[f'{key}_vol_idx'] = self._selected_idx(controls['vol'])

        # Everything registered via DigikeyDialog._radio_row / _text_row
        for state_key, radios in dlg.radio_groups.items():
            self.state[state_key] = self._selected_idx(radios)
        for state_key, ctrl in dlg.text_fields.items():
            self.state[state_key] = ctrl.GetValue()
        # Diode type is a radio row + picklist combo, not a plain radio group
        for key, controls in (('diode', dlg.diode_tabs['tht']), ('smd_diode', dlg.diode_tabs['smd'])):
            self.state[f'{key}_type_idx'] = controls['type_idx']()

    def on_search_click(self, event):
        dlg = self.dlg
        self._save_state(dlg)

        main_sel = dlg.notebook.GetSelection()
        if main_sel == 0: # Through Hole
            tht_sel = dlg.tht_notebook.GetSelection()
            if tht_sel == 0: # Resistors
                res_val = dlg.tht_res_val.GetValue()
                if res_val:
                    self._start_search("Searching for resistors...", search_tht_resistor,
                                       (res_val, self.state['pwr_idx'], self.state['tol_idx'], self.state['res_comp_idx']),
                                       processor=process_resistor)

            elif tht_sel == 1: # Capacitors
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

                        # Configs (shared with BatchImport.py so both search paths agree)
                        cat_id, base_lib_config = CAP_TAB_CONFIGS.get(key, ('58', {}))
                        lib_config = dict(base_lib_config)

                        if key == 'film':
                            if type_idx == 1: # Film
                                lib_config['is_film'] = True

                        if lib_config.get('proc', 'alum') == 'disc':
                            processor = lambda p: process_disc_capacitor(p, lib_config)
                        else:
                            processor = lambda p: process_capacitor(p, lib_config)
                        if cat_id == '60':
                            self._start_search("Searching for capacitors...", search_tht_disc_capacitor,
                                               (cap_val, vol_str, cat_id), {'type_idx': type_idx}, processor=processor)
                        else:
                            self._start_search("Searching for capacitors...", search_tht_capacitor,
                                               (cap_val, vol_str, type_idx, cat_id), processor=processor)

            elif tht_sel == 2: # Diodes
                self._search_diode(dlg.diode_tabs['tht'], 'diode', smd=False)

            elif tht_sel == 3: # Transistors
                keys = ['bjt', 'jfet', 'mosfet']
                sel = dlg.tht_transistor_notebook.GetSelection()
                if sel < len(keys):
                    self._search_transistor(keys[sel], f'transistor_{keys[sel]}', smd=False)

        elif main_sel == 1: # Surface Mount
            self._search_smd(dlg)

        elif main_sel == 2: # Batch Import
            batch_text = dlg.batch_text.GetValue()
            if batch_text.strip():
                self.progress_dialog = ProgressCounterDialog(dlg, "API Call", "Running batch import...")
                self.progress_dialog.Show()
                delayedresult.startWorker(self._on_api_result_batch, self._api_worker_batch,
                                          wargs=[batch_text])
            else:
                wx.MessageBox("Batch text is empty.", "Info", wx.OK | wx.ICON_INFORMATION, parent=dlg)

    def _search_diode(self, controls, key, smd):
        lib_config = {'smd': True, 'handsolder': self.state['smd_handsolder']} if smd else None
        self._start_search("Searching for diodes...", search_diode,
                           (controls['pn'].GetValue(), self.state.get(f'{key}_type_idx', 0),
                            self.state.get(f'{key}_tech_idx', 0), self.state.get(f'{key}_pkg_idx', 0)),
                           {'smd': smd}, processor=lambda p: process_diode(p, lib_config))

    def _search_transistor(self, family, key, smd):
        search_fn, process_fn = {
            'bjt': (search_tht_bjt, process_bjt),
            'jfet': (search_tht_jfet, process_jfet),
            'mosfet': (search_tht_mosfet, process_mosfet),
        }[family]
        lib_config = {'smd': smd}
        self._start_search("Searching for transistors...", search_fn,
                           (self.state.get(f'{key}_pn', ''), self.state.get(f'{key}_polarity_idx', 0),
                            self.state.get(f'{key}_pkg_idx', 0)),
                           {'smd': smd}, processor=lambda p: process_fn(p, lib_config),
                           generator=self._confirm_and_generate_transistor)

    def _search_smd(self, dlg):
        st = self.state
        lib_config = {'handsolder': st['smd_handsolder']}
        smd_sel = dlg.smd_notebook.GetSelection()
        if smd_sel == 0: # Resistors
            res_val = dlg.smd_res['val'].GetValue()
            if res_val:
                self._start_search("Searching for resistors...", search_smd_resistor,
                                   (res_val, SMD_RES_SIZE_OPTS[st['smd_res_size_idx']],
                                    SMD_RES_TOL_OPTS[st['smd_res_tol_idx']], SMD_RES_PWR_OPTS[st['smd_res_pwr_idx']]),
                                   processor=lambda p: process_smd_resistor(p, lib_config))

        elif smd_sel == 1: # Capacitors
            key = ['mlcc', 'tant', 'alum'][dlg.smd_cap_notebook.GetSelection()]
            controls = dlg.smd_cap_tabs[key]
            cap_val = controls['val'].GetValue()
            if not cap_val:
                return
            prefix = f'smd_cap_{key}'
            voltage = controls['cust_vol'].GetValue() or SMD_CAP_VOL_OPTS[st[f'{prefix}_vol_idx']]
            if key == 'mlcc':
                self._start_search("Searching for capacitors...", search_smd_mlcc,
                                   (cap_val, SMD_CAP_SIZE_OPTS[st[f'{prefix}_size_idx']], voltage,
                                    SMD_CAP_DIELECTRIC_OPTS[st[f'{prefix}_dielectric_idx']]),
                                   processor=lambda p: process_smd_mlcc(p, lib_config))
            elif key == 'tant':
                self._start_search("Searching for capacitors...", search_smd_tantalum,
                                   (cap_val, voltage, SMD_TANT_CASE_OPTS[st[f'{prefix}_case_idx']]),
                                   processor=lambda p: process_smd_tantalum(p, lib_config))
            else:
                self._start_search("Searching for capacitors...", search_smd_aluminum,
                                   (cap_val, voltage),
                                   processor=lambda p: process_smd_aluminum(p, lib_config))

        elif smd_sel == 2: # Diodes
            self._search_diode(dlg.diode_tabs['smd'], 'smd_diode', smd=True)

        elif smd_sel == 3: # Transistors
            family = ['bjt', 'jfet', 'mosfet'][dlg.smd_transistor_notebook.GetSelection()]
            self._search_transistor(family, f'smd_transistor_{family}', smd=True)

    def _start_search(self, msg, search_fn, args=(), kwargs=None, processor=None, generator=None):
        """Runs search_fn(*args, token, client_id, refresher, **kwargs) on a worker
        thread, then shows the results with processor/generator on the main thread."""
        self.progress_dialog = ProgressCounterDialog(self.dlg, "API Call", msg)
        self.progress_dialog.Show()
        delayedresult.startWorker(self._on_api_result, self._api_worker,
                                  wargs=[search_fn, args, kwargs or {}],
                                  cargs=[processor, generator or generate_library_files])

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
        # realpath (not just abspath) so this resolves correctly even when invoked via a
        # symlink (e.g. the ~/.local/bin/kicadcompmaker desktop launcher)
        PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
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

    def _api_worker(self, search_fn, args, kwargs):
        token = self.get_token()
        if token:
            return search_fn(*args, token, self.client_id, lambda: self.get_token(force_refresh=True), **kwargs)
        return None

    def _on_api_result(self, delayedResult, processor, generator):
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        parent = self.dlg if self.dlg else wx.FindWindowByName("PcbFrame")
        try:
            results = delayedResult.get()
            if results and results.get("ProductsCount", 0) > 0 and results.get("Products"):
                res_dlg = ResultDialog(parent, results, processor=processor, generator_callback=generator)
                res_dlg.ShowModal()
                res_dlg.Destroy()
            elif results is None:
                wx.MessageBox("API call failed. This could be due to an authentication issue.", "API Error", wx.OK | wx.ICON_ERROR, parent=parent)
            else: # results is not None but no products
                wx.MessageBox("No results found for the specified criteria.", "Info", wx.OK | wx.ICON_INFORMATION, parent=parent)
        except Exception as e:
            wx.MessageBox(f"API Error: {e}", "Error", wx.OK | wx.ICON_ERROR, parent=parent)

    def _confirm_pinout(self, processed_data):
        """Shows PinoutConfirmDialog; returns (pin_mapping, footprint) or None if cancelled."""
        parent = self.dlg if self.dlg else wx.FindWindowByName("PcbFrame")
        dlg = PinoutConfirmDialog(parent, processed_data["pinout_confirm"])
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.get_result()
        finally:
            dlg.Destroy()

    def _confirm_and_generate_transistor(self, processed_data):
        """generator_callback shared by every transistor family: gates
        generate_library_files behind a human-approved pin/footprint mapping via
        PinoutConfirmDialog - Digikey's data alone never establishes pin identity,
        so nothing here is written to the library without that approval."""
        if not processed_data.get("pinout_confirm"):
            return generate_library_files(processed_data)
        result = self._confirm_pinout(processed_data)
        if result is None:
            return False, "Cancelled - no pinout was confirmed."
        apply_pinout(processed_data, *result)
        return generate_library_files(processed_data)

    def _api_worker_batch(self, batch_text):
        token = self.get_token()
        if token is None:
            return None
        return run_batch(batch_text, token, self.client_id,
                          lambda: self.get_token(force_refresh=True), generate_library_files)

    def _on_api_result_batch(self, delayedResult):
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        parent = self.dlg if self.dlg else wx.FindWindowByName("PcbFrame")
        try:
            report_rows = delayedResult.get()
            if report_rows is None:
                wx.MessageBox("API call failed. This could be due to an authentication issue.", "API Error", wx.OK | wx.ICON_ERROR, parent=parent)
                return
            if not report_rows:
                wx.MessageBox("No valid batch lines found.", "Info", wx.OK | wx.ICON_INFORMATION, parent=parent)
                return
            # Transistor lines without a usable pins=/footprint were searched and
            # processed by run_batch but held back - confirm each one now, on the
            # main thread, before anything is written for them.
            for row in report_rows:
                if row['status'] != 'needs_pinout':
                    continue
                processed = row.pop('processed')
                result = self._confirm_pinout(processed)
                if result is None:
                    row['status'], row['detail'] = 'cancelled', "Pinout not confirmed - nothing generated."
                    continue
                apply_pinout(processed, *result)
                try:
                    record_generate(row, *generate_library_files(processed))
                except Exception as e:
                    row['status'], row['detail'] = 'gen_error', str(e)
            res_dlg = BatchResultDialog(parent, report_rows)
            res_dlg.ShowModal()
            res_dlg.Destroy()
        except Exception as e:
            wx.MessageBox(f"Batch Error: {e}", "Error", wx.OK | wx.ICON_ERROR, parent=parent)

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

import sys

# This allows the script to run outside of KiCad
if __name__ == "__main__":
    app = wx.App(False)
    plugin = DigikeyPlugin()
    plugin.Run()
    app.MainLoop()
