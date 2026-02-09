import wx
import json

class ProgressCounterDialog(wx.Dialog):
    def __init__(self, parent, title, message):
        wx.Dialog.__init__(self, parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.count = 0
        
        self.message_label = wx.StaticText(self, label=message)
        self.counter_label = wx.StaticText(self, label="0 seconds")
        
        sizer.Add(self.message_label, 0, wx.ALL | wx.EXPAND, 15)
        sizer.Add(self.counter_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 15)
        
        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(1000) # 1 second interval

    def on_timer(self, event):
        self.count += 1
        self.counter_label.SetLabel(f"{self.count} seconds")

class DigikeyDialog(wx.Dialog):
    def create_cap_controls(self, parent, key, state, show_type=True, custom_vol_opts=None):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Value
        row_val = wx.BoxSizer(wx.HORIZONTAL)
        lbl_val = wx.StaticText(parent, label="Value:")
        val_ctrl = wx.TextCtrl(parent)
        row_val.Add(lbl_val, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        row_val.Add(val_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        sizer.Add(row_val, 0, wx.EXPAND | wx.ALL, 5)

        # Type (Axial/Radial)
        type_radios = []
        if show_type:
            row_type = wx.BoxSizer(wx.HORIZONTAL)
            lbl_type = wx.StaticText(parent, label="Type:")
            row_type.Add(lbl_type, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            type_opts = ["Axial", "Radial"]
            saved_type_idx = state.get(f'{key}_type_idx', 0)
            for i, opt in enumerate(type_opts):
                style = wx.RB_GROUP if i == 0 else 0
                rb = wx.RadioButton(parent, label=opt, style=style)
                if i == saved_type_idx:
                    rb.SetValue(True)
                type_radios.append(rb)
                row_type.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            sizer.Add(row_type, 0, wx.EXPAND | wx.ALL, 5)

        # Voltage
        row_vol = wx.BoxSizer(wx.HORIZONTAL)
        lbl_vol = wx.StaticText(parent, label="Voltage:")
        row_vol.Add(lbl_vol, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        # Expanded voltage list to cover common Film/Mica ratings
        if custom_vol_opts:
            vol_opts = custom_vol_opts
        else:
            vol_opts = ["6.3v", "10v", "16v", "25v", "50v", "63v", "100v"]
        vol_radios = []
        saved_vol_idx = state.get(f'{key}_vol_idx', 0)
        if saved_vol_idx >= len(vol_opts): saved_vol_idx = 0
        for i, opt in enumerate(vol_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(parent, label=opt, style=style)
            if i == saved_vol_idx:
                rb.SetValue(True)
            vol_radios.append(rb)
            row_vol.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # Custom Voltage
        lbl_vol_cust = wx.StaticText(parent, label="Custom:")
        vol_cust_ctrl = wx.TextCtrl(parent)
        row_vol.Add(lbl_vol_cust, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        row_vol.Add(vol_cust_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        sizer.Add(row_vol, 0, wx.EXPAND | wx.ALL, 5)
        parent.SetSizer(sizer)
        
        return {'val': val_ctrl, 'type': type_radios, 'vol': vol_radios, 'cust_vol': vol_cust_ctrl, 'vol_opts': vol_opts}

    def __init__(self, parent, state):
        wx.Dialog.__init__(self, parent, title="Digikey Importer", size=(650, 400), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Create Notebook (Tabs)
        self.notebook = wx.Notebook(self)
        
        # Tab 1: Through Hole
        self.tab_tht = wx.Panel(self.notebook)
        self.notebook.AddPage(self.tab_tht, "Through Hole")

        # THT Sub-tabs
        tht_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tht_notebook = wx.Notebook(self.tab_tht)

        self.tht_resistors = wx.Panel(self.tht_notebook)

        res_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Value Input
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_val = wx.StaticText(self.tht_resistors, label="Value:")
        self.tht_res_val = wx.TextCtrl(self.tht_resistors)
        row1.Add(lbl_val, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        row1.Add(self.tht_res_val, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 5)

        # Power Rating
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_pwr = wx.StaticText(self.tht_resistors, label="Power Rating:")
        row2.Add(lbl_pwr, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        pwr_opts = ["1/8 watt", "1/4 watt", "1/2 watt", "1 watt"]
        self.tht_res_pwr_radios = []
        saved_pwr_idx = state.get('pwr_idx', 0)
        for i, opt in enumerate(pwr_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(self.tht_resistors, label=opt, style=style)
            if i == saved_pwr_idx:
                rb.SetValue(True)
            self.tht_res_pwr_radios.append(rb)
            row2.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row2, 0, wx.EXPAND | wx.ALL, 5)

        # Tolerance
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_tol = wx.StaticText(self.tht_resistors, label="Tolerance:")
        row3.Add(lbl_tol, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        tol_opts = ["+- .1%", "+-1%", "+-2%", "+-5%", "+-10%", "+-20%"]
        self.tht_res_tol_radios = []
        saved_tol_idx = state.get('tol_idx', 0)
        for i, opt in enumerate(tol_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(self.tht_resistors, label=opt, style=style)
            if i == saved_tol_idx:
                rb.SetValue(True)
            self.tht_res_tol_radios.append(rb)
            row3.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row3, 0, wx.EXPAND | wx.ALL, 5)

        self.tht_resistors.SetSizer(res_sizer)

        self.tht_notebook.AddPage(self.tht_resistors, "Resistors")

        self.tht_capacitors = wx.Panel(self.tht_notebook)
        
        # Capacitor Sub-tabs
        cap_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tht_cap_notebook = wx.Notebook(self.tht_capacitors)
        self.cap_tabs = {}

        # 1. Aluminium Electrolytic
        self.tht_cap_alum = wx.Panel(self.tht_cap_notebook)
        self.cap_tabs['alum'] = self.create_cap_controls(self.tht_cap_alum, 'alum', state)
        self.tht_cap_notebook.AddPage(self.tht_cap_alum, "Aluminium Electrolytic")

        # 2. Film (Disc)
        self.tht_cap_film = wx.Panel(self.tht_cap_notebook)
        disc_vol_opts = ["25v", "50v", "100v", "500v", "1kV", "2kV", "I don't care"]
        self.cap_tabs['film'] = self.create_cap_controls(self.tht_cap_film, 'film', state, show_type=False, custom_vol_opts=disc_vol_opts)
        self.tht_cap_notebook.AddPage(self.tht_cap_film, "Disc")

        # 3. Mica/PTFE
        self.tht_cap_mica = wx.Panel(self.tht_cap_notebook)
        self.cap_tabs['mica'] = self.create_cap_controls(self.tht_cap_mica, 'mica', state)
        self.tht_cap_notebook.AddPage(self.tht_cap_mica, "Mica/PTFE")

        cap_sizer.Add(self.tht_cap_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tht_capacitors.SetSizer(cap_sizer)

        self.tht_notebook.AddPage(self.tht_capacitors, "Capacitors")

        self.tht_diodes = wx.Panel(self.tht_notebook)
        self.tht_notebook.AddPage(self.tht_diodes, "Diodes")

        # Restore THT tab selection
        self.tht_notebook.SetSelection(state.get('tht_tab', 0))
        self.tht_cap_notebook.SetSelection(state.get('cap_tab', 0))

        tht_sizer.Add(self.tht_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_tht.SetSizer(tht_sizer)

        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Tab 2: Surface Mount
        self.tab_smd = wx.Panel(self.notebook)
        self.notebook.AddPage(self.tab_smd, "Surface Mount")

        # SMD Sub-tabs
        smd_sizer = wx.BoxSizer(wx.VERTICAL)
        self.smd_notebook = wx.Notebook(self.tab_smd)

        self.smd_resistors = wx.Panel(self.smd_notebook)

        # Hello World Example
        res_sizer = wx.BoxSizer(wx.VERTICAL)
        res_label = wx.StaticText(self.smd_resistors, label="Hello Surface Mount Resitor")
        res_sizer.Add(res_label, 0, wx.ALL, 10)
        self.smd_resistors.SetSizer(res_sizer)

        self.smd_notebook.AddPage(self.smd_resistors, "Resistors")
        self.smd_capacitors = wx.Panel(self.smd_notebook)
        self.smd_notebook.AddPage(self.smd_capacitors, "Capacitors")

        self.smd_diodes = wx.Panel(self.smd_notebook)
        self.smd_notebook.AddPage(self.smd_diodes, "Diodes")

        smd_sizer.Add(self.smd_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_smd.SetSizer(smd_sizer)

        # Restore Main tab selection
        self.notebook.SetSelection(state.get('main_tab', 0))

        # Buttons
        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.CenterOnParent()

class JsonViewDialog(wx.Dialog):
    def __init__(self, parent, product_json, generator_callback):
        wx.Dialog.__init__(self, parent, title="Component JSON", size=(600, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        sizer = wx.BoxSizer(wx.VERTICAL)
        
        text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        text.SetValue(json.dumps(product_json, indent=4, ensure_ascii=False))
        self.product_data = product_json
        self.generator_callback = generator_callback
        
        # Use a monospaced font for JSON readability
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        text.SetFont(font)
        
        sizer.Add(text, 1, wx.EXPAND | wx.ALL, 5)
        
        btns = wx.BoxSizer(wx.HORIZONTAL)
        btn_gen = wx.Button(self, label="Generate")
        btn_ok = wx.Button(self, wx.ID_OK, label="Close")
        
        btns.Add(btn_gen, 0, wx.ALL, 5)
        btns.Add(btn_ok, 0, wx.ALL, 5)
        
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(sizer)
        self.CenterOnParent()
        
        btn_gen.Bind(wx.EVT_BUTTON, self.on_generate)

    def on_generate(self, event):
        success, msg = self.generator_callback(self.product_data)
        icon = wx.ICON_INFORMATION if success else wx.ICON_ERROR
        wx.MessageBox(msg, "Generation Status", wx.OK | icon)

class CredentialsDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="Digi-Key API Credentials", style=wx.DEFAULT_DIALOG_STYLE)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        instructions = wx.StaticText(self, label="Please enter your Digi-Key API credentials.\nThese can be created from your Digi-Key developer account.")
        sizer.Add(instructions, 0, wx.ALL | wx.EXPAND, 15)

        grid = wx.FlexGridSizer(2, 2, 5, 5)
        grid.AddGrowableCol(1)

        lbl_id = wx.StaticText(self, label="Client ID:")
        self.txt_id = wx.TextCtrl(self)
        grid.Add(lbl_id, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid.Add(self.txt_id, 1, wx.EXPAND | wx.ALL, 5)

        lbl_secret = wx.StaticText(self, label="Client Secret:")
        self.txt_secret = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        grid.Add(lbl_secret, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid.Add(self.txt_secret, 1, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 5)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()

    def get_credentials(self):
        return self.txt_id.GetValue(), self.txt_secret.GetValue()

class ResultDialog(wx.Dialog):
    def __init__(self, parent, results, processor, generator_callback):
        wx.Dialog.__init__(self, parent, title="Search Results", size=(700, 400), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.processor = processor
        self.generator_callback = generator_callback

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.list_ctrl.InsertColumn(0, "Part Number", width=150)
        self.list_ctrl.InsertColumn(1, "Price", width=80)
        self.list_ctrl.InsertColumn(2, "Stock", width=80)
        self.list_ctrl.InsertColumn(3, "Description", width=350)

        self.products = results.get("Products", [])
        for product in self.products:
            mpn = product.get("ManufacturerProductNumber", "N/A")
            price = str(product.get("UnitPrice", "N/A"))
            stock = str(product.get("QuantityAvailable", "N/A"))
            desc = product.get("Description", {}).get("DetailedDescription", "N/A")

            index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), mpn)
            self.list_ctrl.SetItem(index, 1, price)
            self.list_ctrl.SetItem(index, 2, stock)
            self.list_ctrl.SetItem(index, 3, desc)

        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.CenterOnParent()
        
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def on_ok(self, event):
        selected_idx = self.list_ctrl.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox("Please select a component.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        product = self.products[selected_idx]
        processed_data = self.processor(product)
        # dlg = JsonViewDialog(self, processed_data, self.generator_callback)
        # dlg.SetTitle("Processed Data")
        # dlg.ShowModal()
        # dlg.Destroy()
        
        success, msg = self.generator_callback(processed_data)
        icon = wx.ICON_INFORMATION if success else wx.ICON_ERROR
        wx.MessageBox(msg, "Generation Status", wx.OK | icon)
        
        self.EndModal(wx.ID_OK)