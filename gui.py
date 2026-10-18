import wx
import wx.adv
import json

try:
    from .TH_Transistor_Common import render_footprint_preview
except ImportError:
    from TH_Transistor_Common import render_footprint_preview

RES_COMP_OPTS = ["Metal Film", "Carbon Film"]
RES_PWR_OPTS = ["1/8 watt", "1/4 watt", "1/2 watt", "1 watt"]
RES_TOL_OPTS = ["+- .1%", "+-1%", "+-2%", "+-5%", "+-10%", "+-20%"]

CAP_ALUM_TYPE_OPTS = ["Axial", "Radial"]
CAP_ALUM_VOL_OPTS = ["6.3v", "10v", "16v", "25v", "50v", "63v", "100v"]
CAP_FILM_TYPE_OPTS = ["Disc", "Film"]
CAP_FILM_VOL_OPTS = ["25v", "50v", "100v", "500v", "1kV", "2kV", "I don't care"]

DIODE_TYPE_RADIO_OPTS = ["I don't care", "Standard Diode", "Zener", "Bridge Rectifier"]
DIODE_TYPE_PICK_OPTS = ["Diode Array", "Zener Array", "RF Diode", "Variable Capacitance (Varicap)"]
DIODE_TECH_OPTS = ["I don't care", "Schottky", "Standard", "SiC Schottky"]
DIODE_PKG_OPTS = ["I don't care", "DO-41", "DO-35", "DO-15", "DO-201AD"]
# Type indices (into the combined radio+picklist list) for which the Technology filter applies
DIODE_TYPES_WITH_TECHNOLOGY = {0, 1, 3}

TRANSISTOR_PKG_OPTS = ["I don't care", "TO-92", "TO-18", "TO-39", "TO-220", "TO-126", "TO-247"]
BJT_POLARITY_OPTS = ["I don't care", "NPN", "PNP"]
FET_POLARITY_OPTS = ["I don't care", "N-Channel", "P-Channel"]

# Surface mount. Labels double as the batch-import field values (see BatchImport)
# and as the keys the SMD_* search functions map to Digi-Key ValueIds.
SMD_RES_SIZE_OPTS = ["I don't care", "0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512"]
SMD_RES_TOL_OPTS = ["I don't care", "0.1%", "0.5%", "1%", "5%"]
SMD_RES_PWR_OPTS = ["I don't care", "1/20W", "1/16W", "1/10W", "1/8W", "1/4W", "1/2W", "1W"]
SMD_CAP_SIZE_OPTS = ["I don't care", "0201", "0402", "0603", "0805", "1206", "1210", "1812", "2220"]
SMD_CAP_VOL_OPTS = ["I don't care", "6.3v", "10v", "16v", "25v", "35v", "50v", "100v"]
SMD_CAP_DIELECTRIC_OPTS = ["I don't care", "C0G/NP0", "X5R", "X7R", "X7S", "Y5V"]
SMD_TANT_CASE_OPTS = ["I don't care", "A (3216)", "B (3528)", "C (6032)", "D (7343)", "E (7360)"]
# Index-aligned with TH_Diodes.SMD_DIODE_PACKAGE_IDX / TH_Transistor_Common.SMD_TRANSISTOR_PACKAGE_IDX
SMD_DIODE_PKG_OPTS = ["I don't care", "SOD-123", "SOD-323", "SOD-523", "SMA", "SMB", "SMC", "MiniMELF"]
SMD_TRANSISTOR_PKG_OPTS = ["I don't care", "SOT-23", "SOT-323", "SOT-523", "SOT-89", "SOT-223", "DPAK (TO-252)", "D2PAK (TO-263)"]
SMD_RES_SIZE_DEFAULT = SMD_RES_SIZE_OPTS.index("0603")
SMD_RES_TOL_DEFAULT = SMD_RES_TOL_OPTS.index("1%")
SMD_CAP_SIZE_DEFAULT = SMD_CAP_SIZE_OPTS.index("0603")

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
    def create_cap_controls(self, parent, key, state, show_type=True, type_opts=None, custom_vol_opts=None):
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
            if type_opts is None:
                type_opts = CAP_ALUM_TYPE_OPTS
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
            vol_opts = CAP_ALUM_VOL_OPTS
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

    def _radio_row(self, parent, sizer, label, opts, state, state_key, default_idx=0):
        """Label + one radio group, restored from/registered under state_key so
        plugin.on_search_click can save every group generically."""
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        wrap = wx.WrapSizer(wx.HORIZONTAL)
        saved_idx = state.get(state_key, default_idx)
        if saved_idx >= len(opts):
            saved_idx = default_idx
        radios = []
        for i, opt in enumerate(opts):
            rb = wx.RadioButton(parent, label=opt, style=wx.RB_GROUP if i == 0 else 0)
            if i == saved_idx:
                rb.SetValue(True)
            radios.append(rb)
            wrap.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        row.Add(wrap, 1, wx.EXPAND)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)
        self.radio_groups[state_key] = radios
        return radios

    def _text_row(self, parent, sizer, label, state, state_key=None):
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        ctrl = wx.TextCtrl(parent)
        if state_key:
            ctrl.SetValue(state.get(state_key, ''))
            self.text_fields[state_key] = ctrl
        row.Add(ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)
        return ctrl

    def create_smd_cap_controls(self, parent, key, state, size=False, dielectric=False, case=False):
        """Value-first controls for the SMD capacitor sub-tabs."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = {'val': self._text_row(parent, sizer, "Value:", state)}
        if size:
            controls['size'] = self._radio_row(parent, sizer, "Size:", SMD_CAP_SIZE_OPTS, state,
                                               f'{key}_size_idx', SMD_CAP_SIZE_DEFAULT)
        controls['vol'] = self._radio_row(parent, sizer, "Voltage:", SMD_CAP_VOL_OPTS, state, f'{key}_vol_idx')
        controls['cust_vol'] = self._text_row(parent, sizer, "Custom voltage:", state)
        if dielectric:
            controls['dielectric'] = self._radio_row(parent, sizer, "Dielectric:", SMD_CAP_DIELECTRIC_OPTS,
                                                     state, f'{key}_dielectric_idx')
        if case:
            controls['case'] = self._radio_row(parent, sizer, "Case:", SMD_TANT_CASE_OPTS, state, f'{key}_case_idx')
        parent.SetSizer(sizer)
        return controls

    def create_diode_controls(self, parent, key, state, pkg_opts):
        """Part-number-first diode controls, shared by the THT and SMD Diodes
        tabs. Type is a radio row (first 4) + picklist (rest), combined into one
        type index; Technology is only enabled for types that support it."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        pn_ctrl = self._text_row(parent, sizer, "Part Number:", state, f'{key}_pn')

        hint = wx.StaticText(parent, label="Other filters below are ignored when a part number is given.")
        sizer.Add(hint, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        saved_type_idx = state.get(f'{key}_type_idx', 0)

        row_type = wx.BoxSizer(wx.HORIZONTAL)
        row_type.Add(wx.StaticText(parent, label="Type:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        type_radios = []
        for i, opt in enumerate(DIODE_TYPE_RADIO_OPTS):
            rb = wx.RadioButton(parent, label=opt, style=wx.RB_GROUP if i == 0 else 0)
            if i == saved_type_idx:
                rb.SetValue(True)
            type_radios.append(rb)
            row_type.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        type_pick = wx.Choice(parent, choices=DIODE_TYPE_PICK_OPTS)
        pick_idx = saved_type_idx - len(DIODE_TYPE_RADIO_OPTS)
        if 0 <= pick_idx < len(DIODE_TYPE_PICK_OPTS):
            type_pick.SetSelection(pick_idx)
        row_type.Add(type_pick, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        sizer.Add(row_type, 0, wx.EXPAND | wx.ALL, 5)

        tech_radios = self._radio_row(parent, sizer, "Technology:", DIODE_TECH_OPTS, state, f'{key}_tech_idx')

        def type_idx():
            pick_sel = type_pick.GetSelection()
            if pick_sel != wx.NOT_FOUND:
                return len(DIODE_TYPE_RADIO_OPTS) + pick_sel
            for i, rb in enumerate(type_radios):
                if rb.GetValue():
                    return i
            return 0

        def update_tech_enabled():
            enabled = type_idx() in DIODE_TYPES_WITH_TECHNOLOGY
            for rb in tech_radios:
                rb.Enable(enabled)

        def on_type_radio(event):
            type_pick.SetSelection(wx.NOT_FOUND)
            update_tech_enabled()

        def on_type_pick(event):
            for rb in type_radios:
                rb.SetValue(False)
            update_tech_enabled()

        for rb in type_radios:
            rb.Bind(wx.EVT_RADIOBUTTON, on_type_radio)
        type_pick.Bind(wx.EVT_CHOICE, on_type_pick)
        update_tech_enabled()

        pkg_radios = self._radio_row(parent, sizer, "Package:", pkg_opts, state, f'{key}_pkg_idx')

        parent.SetSizer(sizer)
        # type_idx is a callable - the combined radio+picklist selection isn't a
        # plain radio group, so it's saved separately (plugin.on_search_click).
        return {'pn': pn_ctrl, 'type_idx': type_idx, 'tech': tech_radios, 'pkg': pkg_radios}

    def create_transistor_controls(self, parent, key, state, polarity_opts, pkg_opts=TRANSISTOR_PKG_OPTS):
        """Part-number-first controls shared by the BJT/JFET/MOSFET sub-tabs -
        transistors aren't specified by one scalar 'value' the way R/C are, so
        this mirrors the Diode tab's part-number-first layout rather than
        create_cap_controls's value-first one."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        pn_ctrl = self._text_row(parent, sizer, "Part Number:", state, f'{key}_pn')

        hint = wx.StaticText(parent, label="Other filters below are ignored when a part number is given.")
        sizer.Add(hint, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        pol_radios = self._radio_row(parent, sizer, "Polarity:", polarity_opts, state, f'{key}_polarity_idx')
        pkg_radios = self._radio_row(parent, sizer, "Package:", pkg_opts, state, f'{key}_pkg_idx')

        parent.SetSizer(sizer)
        return {'pn': pn_ctrl, 'polarity': pol_radios, 'pkg': pkg_radios}

    def __init__(self, parent, state):
        wx.Dialog.__init__(self, parent, title="Digikey Importer", size=(760, 480), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        # state_key -> radio group / text control, saved generically by
        # plugin.on_search_click (see _radio_row / _text_row)
        self.radio_groups = {}
        self.text_fields = {}

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
        
        # Composition
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_comp = wx.StaticText(self.tht_resistors, label="Composition:")
        row1.Add(lbl_comp, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        comp_opts = RES_COMP_OPTS
        self.tht_res_comp_radios = []
        saved_comp_idx = state.get('res_comp_idx', 0)
        for i, opt in enumerate(comp_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(self.tht_resistors, label=opt, style=style)
            if i == saved_comp_idx:
                rb.SetValue(True)
            self.tht_res_comp_radios.append(rb)
            row1.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 5)
        
        # Value Input
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_val = wx.StaticText(self.tht_resistors, label="Value:")
        self.tht_res_val = wx.TextCtrl(self.tht_resistors)
        row2.Add(lbl_val, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        row2.Add(self.tht_res_val, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row2, 0, wx.EXPAND | wx.ALL, 5)

        # Power Rating
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_pwr = wx.StaticText(self.tht_resistors, label="Power Rating:")
        row3.Add(lbl_pwr, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        pwr_opts = RES_PWR_OPTS
        self.tht_res_pwr_radios = []
        saved_pwr_idx = state.get('pwr_idx', 0)
        for i, opt in enumerate(pwr_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(self.tht_resistors, label=opt, style=style)
            if i == saved_pwr_idx:
                rb.SetValue(True)
            self.tht_res_pwr_radios.append(rb)
            row3.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row3, 0, wx.EXPAND | wx.ALL, 5)

        # Tolerance
        row4 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_tol = wx.StaticText(self.tht_resistors, label="Tolerance:")
        row4.Add(lbl_tol, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        tol_opts = RES_TOL_OPTS
        self.tht_res_tol_radios = []
        saved_tol_idx = state.get('tol_idx', 0)
        for i, opt in enumerate(tol_opts):
            style = wx.RB_GROUP if i == 0 else 0
            rb = wx.RadioButton(self.tht_resistors, label=opt, style=style)
            if i == saved_tol_idx:
                rb.SetValue(True)
            self.tht_res_tol_radios.append(rb)
            row4.Add(rb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        res_sizer.Add(row4, 0, wx.EXPAND | wx.ALL, 5)

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
        self.cap_tabs['film'] = self.create_cap_controls(self.tht_cap_film, 'film', state, show_type=True, type_opts=CAP_FILM_TYPE_OPTS, custom_vol_opts=CAP_FILM_VOL_OPTS)
        self.tht_cap_notebook.AddPage(self.tht_cap_film, "Disc/Film")

        # 3. Mica/PTFE
        self.tht_cap_mica = wx.Panel(self.tht_cap_notebook)
        self.cap_tabs['mica'] = self.create_cap_controls(self.tht_cap_mica, 'mica', state)
        self.tht_cap_notebook.AddPage(self.tht_cap_mica, "Mica/PTFE")

        cap_sizer.Add(self.tht_cap_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tht_capacitors.SetSizer(cap_sizer)

        self.tht_notebook.AddPage(self.tht_capacitors, "Capacitors")

        self.tht_diodes = wx.Panel(self.tht_notebook)
        self.diode_tabs = {}
        # 'diode' state prefix kept from before the SMD tab existed
        self.diode_tabs['tht'] = self.create_diode_controls(self.tht_diodes, 'diode', state, DIODE_PKG_OPTS)
        self.tht_notebook.AddPage(self.tht_diodes, "Diodes")

        self.tht_transistors = wx.Panel(self.tht_notebook)
        transistor_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tht_transistor_notebook = wx.Notebook(self.tht_transistors)
        self.transistor_tabs = {}

        # 1. BJT
        self.tht_transistor_bjt = wx.Panel(self.tht_transistor_notebook)
        self.transistor_tabs['bjt'] = self.create_transistor_controls(
            self.tht_transistor_bjt, 'transistor_bjt', state, BJT_POLARITY_OPTS)
        self.tht_transistor_notebook.AddPage(self.tht_transistor_bjt, "BJT")

        # 2. JFET
        self.tht_transistor_jfet = wx.Panel(self.tht_transistor_notebook)
        self.transistor_tabs['jfet'] = self.create_transistor_controls(
            self.tht_transistor_jfet, 'transistor_jfet', state, FET_POLARITY_OPTS)
        self.tht_transistor_notebook.AddPage(self.tht_transistor_jfet, "JFET")

        # 3. MOSFET
        self.tht_transistor_mosfet = wx.Panel(self.tht_transistor_notebook)
        self.transistor_tabs['mosfet'] = self.create_transistor_controls(
            self.tht_transistor_mosfet, 'transistor_mosfet', state, FET_POLARITY_OPTS)
        self.tht_transistor_notebook.AddPage(self.tht_transistor_mosfet, "MOSFET")

        transistor_sizer.Add(self.tht_transistor_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tht_transistors.SetSizer(transistor_sizer)

        self.tht_notebook.AddPage(self.tht_transistors, "Transistors")

        # Restore THT tab selection
        self.tht_notebook.SetSelection(state.get('tht_tab', 0))
        self.tht_cap_notebook.SetSelection(state.get('cap_tab', 0))
        self.tht_transistor_notebook.SetSelection(state.get('transistor_tab', 0))

        tht_sizer.Add(self.tht_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_tht.SetSizer(tht_sizer)

        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Tab 2: Surface Mount
        self.tab_smd = wx.Panel(self.notebook)
        self.notebook.AddPage(self.tab_smd, "Surface Mount")

        smd_sizer = wx.BoxSizer(wx.VERTICAL)
        # Shared by every SMD sub-tab: picks KiCad's _HandSolder/_Handsoldering
        # stock pad variant wherever one exists (chip R/C, tantalum, most diodes).
        self.smd_handsolder = wx.CheckBox(self.tab_smd, label="Hand-solder pads (where KiCad has a variant)")
        self.smd_handsolder.SetValue(state.get('smd_handsolder', True))
        smd_sizer.Add(self.smd_handsolder, 0, wx.ALL, 5)

        self.smd_notebook = wx.Notebook(self.tab_smd)

        # Resistors
        self.smd_resistors = wx.Panel(self.smd_notebook)
        smd_res_sizer = wx.BoxSizer(wx.VERTICAL)
        self.smd_res = {
            'val': self._text_row(self.smd_resistors, smd_res_sizer, "Value:", state),
            'size': self._radio_row(self.smd_resistors, smd_res_sizer, "Size:", SMD_RES_SIZE_OPTS, state,
                                    'smd_res_size_idx', SMD_RES_SIZE_DEFAULT),
            'tol': self._radio_row(self.smd_resistors, smd_res_sizer, "Tolerance:", SMD_RES_TOL_OPTS, state,
                                   'smd_res_tol_idx', SMD_RES_TOL_DEFAULT),
            'pwr': self._radio_row(self.smd_resistors, smd_res_sizer, "Power:", SMD_RES_PWR_OPTS, state,
                                   'smd_res_pwr_idx'),
        }
        self.smd_resistors.SetSizer(smd_res_sizer)
        self.smd_notebook.AddPage(self.smd_resistors, "Resistors")

        # Capacitors
        self.smd_capacitors = wx.Panel(self.smd_notebook)
        smd_cap_sizer = wx.BoxSizer(wx.VERTICAL)
        self.smd_cap_notebook = wx.Notebook(self.smd_capacitors)
        self.smd_cap_tabs = {}
        for key, title, opts in (('mlcc', "Ceramic (MLCC)", {'size': True, 'dielectric': True}),
                                 ('tant', "Tantalum", {'case': True}),
                                 ('alum', "Aluminium Electrolytic", {})):
            panel = wx.Panel(self.smd_cap_notebook)
            self.smd_cap_tabs[key] = self.create_smd_cap_controls(panel, f'smd_cap_{key}', state, **opts)
            self.smd_cap_notebook.AddPage(panel, title)
        smd_cap_sizer.Add(self.smd_cap_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.smd_capacitors.SetSizer(smd_cap_sizer)
        self.smd_notebook.AddPage(self.smd_capacitors, "Capacitors")

        # Diodes
        self.smd_diodes = wx.Panel(self.smd_notebook)
        self.diode_tabs['smd'] = self.create_diode_controls(self.smd_diodes, 'smd_diode', state, SMD_DIODE_PKG_OPTS)
        self.smd_notebook.AddPage(self.smd_diodes, "Diodes")

        # Transistors
        self.smd_transistors = wx.Panel(self.smd_notebook)
        smd_tr_sizer = wx.BoxSizer(wx.VERTICAL)
        self.smd_transistor_notebook = wx.Notebook(self.smd_transistors)
        self.smd_transistor_tabs = {}
        for key, title, pol_opts in (('bjt', "BJT", BJT_POLARITY_OPTS),
                                     ('jfet', "JFET", FET_POLARITY_OPTS),
                                     ('mosfet', "MOSFET", FET_POLARITY_OPTS)):
            panel = wx.Panel(self.smd_transistor_notebook)
            self.smd_transistor_tabs[key] = self.create_transistor_controls(
                panel, f'smd_transistor_{key}', state, pol_opts, SMD_TRANSISTOR_PKG_OPTS)
            self.smd_transistor_notebook.AddPage(panel, title)
        smd_tr_sizer.Add(self.smd_transistor_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.smd_transistors.SetSizer(smd_tr_sizer)
        self.smd_notebook.AddPage(self.smd_transistors, "Transistors")

        self.smd_notebook.SetSelection(state.get('smd_tab', 0))
        self.smd_cap_notebook.SetSelection(state.get('smd_cap_tab', 0))
        self.smd_transistor_notebook.SetSelection(state.get('smd_transistor_tab', 0))

        smd_sizer.Add(self.smd_notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_smd.SetSizer(smd_sizer)

        # Tab 3: Batch Import
        self.tab_batch = wx.Panel(self.notebook)
        self.notebook.AddPage(self.tab_batch, "Batch Import")

        batch_sizer = wx.BoxSizer(wx.VERTICAL)
        hint = wx.StaticText(self.tab_batch, label=(
            "One spec per line: <type> field=value ... (# comments and blank lines are ignored).\n"
            "THT types: resistor, cap_alum, cap_film, cap_mica, diode, bjt, jfet, mosfet\n"
            "SMD types: smd_resistor, smd_cap, smd_tant, smd_alum, smd_diode, smd_bjt, smd_jfet, smd_mosfet\n"
            "Transistors: add pins=BEC (terminal per pin 1..3) to skip the pinout dialog. See README.md."))
        batch_sizer.Add(hint, 0, wx.EXPAND | wx.ALL, 5)

        self.batch_text = wx.TextCtrl(self.tab_batch, style=wx.TE_MULTILINE)
        batch_sizer.Add(self.batch_text, 1, wx.EXPAND | wx.ALL, 5)

        btn_load = wx.Button(self.tab_batch, label="Load from File...")
        batch_sizer.Add(btn_load, 0, wx.ALL, 5)
        btn_load.Bind(wx.EVT_BUTTON, self.on_load_batch_file)

        self.tab_batch.SetSizer(batch_sizer)

        # Restore Main tab selection
        self.notebook.SetSelection(state.get('main_tab', 0))

        # Buttons
        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.CenterOnParent()

    def on_load_batch_file(self, event):
        with wx.FileDialog(self, "Load batch import file", wildcard="Text files (*.txt)|*.txt|All files (*.*)|*.*",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dlg:
            if file_dlg.ShowModal() != wx.ID_OK:
                return
            path = file_dlg.GetPath()
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    contents = f.read()
            except Exception as e:
                wx.MessageBox(f"Could not read file:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)
                return
            self.batch_text.SetValue(contents)

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

class BatchResultDialog(wx.Dialog):
    def __init__(self, parent, report_rows):
        wx.Dialog.__init__(self, parent, title="Batch Import Results", size=(750, 450),
                            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.list_ctrl.InsertColumn(0, "Line#", width=50)
        self.list_ctrl.InsertColumn(1, "Type", width=90)
        self.list_ctrl.InsertColumn(2, "Value", width=100)
        self.list_ctrl.InsertColumn(3, "Status", width=110)
        self.list_ctrl.InsertColumn(4, "Detail", width=350)

        for row in report_rows:
            index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), str(row['line_no']))
            self.list_ctrl.SetItem(index, 1, row['type'])
            self.list_ctrl.SetItem(index, 2, row['value'])
            self.list_ctrl.SetItem(index, 3, row['status'])
            self.list_ctrl.SetItem(index, 4, row['detail'])

        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        summary = wx.StaticText(self, label=self._summarize(report_rows))
        sizer.Add(summary, 0, wx.EXPAND | wx.ALL, 5)

        btns = self.CreateButtonSizer(wx.OK)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)
        self.CenterOnParent()

    @staticmethod
    def _summarize(rows):
        from collections import Counter
        counts = Counter(row['status'] for row in rows)
        return " | ".join(f"{status}: {count}" for status, count in counts.items())

class PinoutConfirmDialog(wx.Dialog):
    """Human-in-the-loop gate between a transistor search result and library
    generation: package/footprint and pin-to-terminal identity are never
    trusted from Digikey data or an LLM guess alone - a human must see the
    evidence (or be told none exists yet) and explicitly assign every pin."""
    def __init__(self, parent, pinout_confirm, evidence_images=None, rationale=""):
        wx.Dialog.__init__(self, parent, title="Confirm Pin Assignment", size=(560, 760),
                            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.pinout_confirm = pinout_confirm
        self.pin_mapping = None
        self.chosen_footprint = None
        self.fp_choice = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, label=(
            f"{pinout_confirm.get('mpn', '?')}  (package: {pinout_confirm.get('package_raw', '?')})\n"
            "Verify against the datasheet before approving - nothing here is auto-trusted."))
        sizer.Add(header, 0, wx.EXPAND | wx.ALL, 8)

        datasheet = pinout_confirm.get('datasheet', '')
        if datasheet:
            link = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, label=datasheet, url=datasheet,
                                         style=wx.adv.HL_ALIGN_LEFT)
            link.SetNormalColour(wx.Colour(0, 102, 204))
            link.SetVisitedColour(wx.Colour(102, 0, 204))
            sizer.Add(link, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

            # Read-only, pre-selected so the user can copy/paste even if the
            # click-to-open handler above is blocked (e.g. no default browser set).
            copy_field = wx.TextCtrl(self, value=datasheet, style=wx.TE_READONLY)
            copy_field.SetSelection(0, len(datasheet))
            sizer.Add(copy_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        else:
            sizer.Add(wx.StaticText(self, label="(no datasheet URL returned)"), 0, wx.EXPAND | wx.ALL, 8)

        if evidence_images:
            scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
            scroll.SetScrollRate(0, 10)
            img_sizer = wx.BoxSizer(wx.VERTICAL)
            for path in evidence_images:
                try:
                    bmp = wx.Image(path, wx.BITMAP_TYPE_ANY).ConvertToBitmap()
                    img_sizer.Add(wx.StaticBitmap(scroll, bitmap=bmp), 0, wx.ALL, 5)
                except Exception:
                    pass
            scroll.SetSizer(img_sizer)
            scroll.SetMinSize((-1, 220))
            sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 5)
        else:
            warn = wx.StaticText(self, label=(
                "No visual evidence available yet - open the datasheet yourself and "
                "assign pins manually."))
            warn.Wrap(480)
            sizer.Add(warn, 0, wx.EXPAND | wx.ALL, 8)

        rationale_box = wx.TextCtrl(
            self, value=rationale or "(no automated rationale - manual assignment required)",
            style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 60))
        sizer.Add(rationale_box, 0, wx.EXPAND | wx.ALL, 5)

        candidates = pinout_confirm.get('footprint_candidates', [])
        resolved = pinout_confirm.get('footprint_resolved')
        fp_row = wx.BoxSizer(wx.HORIZONTAL)
        fp_row.Add(wx.StaticText(self, label="Footprint:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        if resolved:
            fp_row.Add(wx.StaticText(self, label=resolved), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        elif candidates:
            self.fp_choice = wx.Choice(self, choices=candidates)
            self.fp_choice.SetSelection(0)
            fp_row.Add(self.fp_choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        else:
            fp_row.Add(wx.StaticText(self, label="No stock footprint match found - cannot generate."),
                       0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        sizer.Add(fp_row, 0, wx.EXPAND | wx.ALL, 5)

        # KiCad's own pad numbering for the footprint above - the datasheet's pinout
        # diagram is pictorial (D/S/G drawn at physical locations, not "pin 1 = D"),
        # so the human needs to see what KiCad calls pin 1/2/3 to map one to the other.
        fp_preview_label = wx.StaticText(self, label=(
            "KiCad pad numbering for this footprint (component/silkscreen side, i.e. "
            "looking down at the top of the board) - if your datasheet's diagram is a "
            "bottom/lead view instead, it will be mirrored left-right from this:"))
        fp_preview_label.Wrap(480)
        sizer.Add(fp_preview_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)

        self.fp_preview_bitmap = wx.StaticBitmap(self, size=(260, 200))
        sizer.Add(self.fp_preview_bitmap, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)

        self._refresh_fp_preview(resolved or (candidates[0] if candidates else None))
        if self.fp_choice is not None:
            self.fp_choice.Bind(wx.EVT_CHOICE, self._on_fp_choice_changed)

        terminals = pinout_confirm.get('terminals', [])
        default_numbers = pinout_confirm.get('default_numbers', {})
        num_to_term = {v: k for k, v in default_numbers.items()}
        term_opts = list(terminals) + ["Unknown/Manual"]

        self.pin_choices = {}
        grid = wx.FlexGridSizer(len(terminals), 2, 5, 5)
        grid.AddGrowableCol(1)
        for i in range(1, len(terminals) + 1):
            pin_num = str(i)
            grid.Add(wx.StaticText(self, label=f"Pin {pin_num}:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            choice = wx.Choice(self, choices=term_opts)
            guess = num_to_term.get(pin_num, "Unknown/Manual")
            choice.SetSelection(term_opts.index(guess) if guess in term_opts else len(term_opts) - 1)
            grid.Add(choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
            self.pin_choices[pin_num] = choice
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 5)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()

        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def _refresh_fp_preview(self, footprint_name):
        fp_dir = self.pinout_confirm.get('footprint_dir')
        if footprint_name and fp_dir:
            bmp = render_footprint_preview(footprint_name, fp_dir=fp_dir)
        elif footprint_name:
            bmp = render_footprint_preview(footprint_name)
        else:
            bmp = None
        if bmp is None:
            bmp = wx.Bitmap(260, 200)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(wx.Colour(255, 255, 255)))
            dc.Clear()
            dc.DrawText("No preview available for this footprint.", 10, 90)
            dc.SelectObject(wx.NullBitmap)
        self.fp_preview_bitmap.SetBitmap(bmp)

    def _on_fp_choice_changed(self, event):
        self._refresh_fp_preview(self.fp_choice.GetStringSelection())

    def on_ok(self, event):
        terminals = self.pinout_confirm.get('terminals', [])
        resolved = self.pinout_confirm.get('footprint_resolved')

        mapping = {}
        for pin_num, choice in self.pin_choices.items():
            val = choice.GetStringSelection()
            if val == "Unknown/Manual" or not val:
                wx.MessageBox(f"Pin {pin_num} is not assigned. Every pin must be assigned before approving.",
                              "Incomplete", wx.OK | wx.ICON_WARNING, parent=self)
                return
            mapping[pin_num] = val

        if len(set(mapping.values())) != len(terminals):
            wx.MessageBox("Two pins were assigned the same terminal - each terminal must be used exactly once.",
                          "Duplicate assignment", wx.OK | wx.ICON_WARNING, parent=self)
            return

        if resolved:
            footprint = resolved
        elif self.fp_choice is not None:
            footprint = self.fp_choice.GetStringSelection()
        else:
            wx.MessageBox("No stock footprint is available for this package - cannot generate.",
                          "No footprint", wx.OK | wx.ICON_ERROR, parent=self)
            return

        self.pin_mapping = mapping
        self.chosen_footprint = footprint
        self.EndModal(wx.ID_OK)

    def get_result(self):
        return self.pin_mapping, self.chosen_footprint