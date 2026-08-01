# Code Map

- Source: `/home/kidwidget/Documents/projects/KicadCompMaker`
- Generated: 2026-07-15T08:37:11
- Files mapped: 8 code, 2 data/doc, 14 skipped (no grammar)

## BatchImport.py — python, 317 lines
Imports: `import shlex`; `import concurrent.futures`; `from dataclasses import dataclass, field`

- **class** `BatchSpecError` — L32-33: `class BatchSpecError(Exception):`
- @dataclass
- **class** `BatchSpec` — L37-41: `class BatchSpec:`
- **def** `_match_option` — L44-51: `def _match_option(value, opts):`
- **def** `_resolve_voltage` — L54-65: `def _resolve_voltage(value, vol_opts):`
- **def** `parse_batch_text` — L68-96: `def parse_batch_text(text):`
- **def** `resolve_resistor` — L99-124: `def resolve_resistor(spec):`
- **def** `_resolve_cap_common` — L127-145: `def _resolve_cap_common(spec, key, type_opts, vol_opts):`
- **def** `resolve_cap_alum` — L148-159: `def resolve_cap_alum(spec):`
- **def** `resolve_cap_film` — L162-175: `def resolve_cap_film(spec):`
- **def** `resolve_cap_mica` — L178-194: `def resolve_cap_mica(spec):`
- **def** `_search_job` — L205-222: `def _search_job(job, access_token, client_id, token_refresher):`
- **def** `run_batch` — L225-317: `def run_batch(batch_text, access_token, client_id, token_refresher, generate_library_files, max_workers=5):`

## DigikeyVoltageMap.py — python, 76 lines
Imports: `import re`

- **def** `parse_voltage_volts` — L56-68: `def parse_voltage_volts(s):`
- **def** `lookup_value_id` — L71-76: `def lookup_value_id(volts):`

## TH_Disc_Capacitors.py — python, 265 lines
Imports: `import requests`; `import re`

- **def** `_product_voltage_volts` — L12-26: `def _product_voltage_volts(product_json):`
- **def** `search_tht_disc_capacitor` — L29-115: `def search_tht_disc_capacitor(capacitance, voltage, cat_id, access_token, client_id, token_refresher=None, type_idx=0):`
- **def** `process_disc_capacitor` — L117-237: `def process_disc_capacitor(product_json, lib_config=None):`
  - **def** `parse_pitch` — L185-189: `def parse_pitch(val):`

## TH_Radial_ElectrolyticCapacitors.py — python, 278 lines
Imports: `import requests`; `import re`; `import math`

- **def** `_product_voltage_volts` — L11-25: `def _product_voltage_volts(product_json):`
- **def** `generate_capacitor_polygons` — L28-78: `def generate_capacitor_polygons(diameter=5.0, pitch=2.0):`
  - **def** `get_arc_points` — L47-57: `def get_arc_points(y_start, y_end, steps):`
- **def** `format_kicad_poly` — L80-82: `def format_kicad_poly(points, layer="F.SilkS"):`
- **def** `process_capacitor` — L84-197: `def process_capacitor(product_json, lib_config=None):`
  - **def** `parse_dim` — L138-143: `def parse_dim(val):`
- **def** `search_tht_capacitor` — L199-278: `def search_tht_capacitor(capacitance, voltage, type_idx, cat_id, access_token, client_id, token_refresher=None):`

## TH_Resistors.py — python, 180 lines
Imports: `import requests`; `import re`; `import math`

- **def** `process_resistor` — L7-106: `def process_resistor(product_json):`
- **def** `search_tht_resistor` — L108-180: `def search_tht_resistor(resistance, power_idx, tolerance_idx, comp_idx, access_token, client_id, token_refresher=None):`

## __init__.py — python, 7 lines
Imports: `from .plugin import DigikeyPlugin`

_(no top-level classes/functions found)_

## gui.py — python, 445 lines
Imports: `import wx`; `import json`

- **class** `ProgressCounterDialog` — L13-34: `class ProgressCounterDialog(wx.Dialog):`
  - **def** `__init__` — L14-30: `def __init__(self, parent, title, message):`
  - **def** `on_timer` — L32-34: `def on_timer(self, event):`
- **class** `DigikeyDialog` — L36-283: `class DigikeyDialog(wx.Dialog):`
  - **def** `create_cap_controls` — L37-95: `def create_cap_controls(self, parent, key, state, show_type=True, type_opts=None, custom_vol_opts=None):`
  - **def** `__init__` — L97-269: `def __init__(self, parent, state):`
  - **def** `on_load_batch_file` — L271-283: `def on_load_batch_file(self, event):`
- **class** `JsonViewDialog` — L285-319: `class JsonViewDialog(wx.Dialog):`
  - **def** `__init__` — L286-314: `def __init__(self, parent, product_json, generator_callback):`
  - **def** `on_generate` — L316-319: `def on_generate(self, event):`
- **class** `CredentialsDialog` — L321-352: `class CredentialsDialog(wx.Dialog):`
  - **def** `__init__` — L322-349: `def __init__(self, parent):`
  - **def** `get_credentials` — L351-352: `def get_credentials(self):`
- **class** `ResultDialog` — L354-407: `class ResultDialog(wx.Dialog):`
  - **def** `__init__` — L355-388: `def __init__(self, parent, results, processor, generator_callback):`
  - **def** `on_ok` — L390-407: `def on_ok(self, event):`
- **class** `BatchResultDialog` — L409-445: `class BatchResultDialog(wx.Dialog):`
  - **def** `__init__` — L410-439: `def __init__(self, parent, report_rows):`
  - @staticmethod
  - **def** `_summarize` — L442-445: `def _summarize(rows):`

## plugin.py — python, 421 lines
Imports: `import os`; `import wx`; `import requests`; `import json`; `import time`; `import jinja2`; `import wx.lib.delayedresult as delayedresult`; `import sys`

- **class** `pcbnew` — L6-8: `class pcbnew:`
  - **class** `ActionPlugin` — L7-8: `class ActionPlugin:`
    - **def** `register` — L8-8: `def register(self): pass`
- **def** `generate_library_files` — L30-112: `def generate_library_files(data):`
  - **def** `append_to_lib` — L81-96: `def append_to_lib(lib_path, content_to_add):`
- **class** `DigikeyPlugin` — L114-412: `class DigikeyPlugin(pcbnew.ActionPlugin):`
  - **def** `__init__` — L115-124: `def __init__(self):`
  - **def** `defaults` — L126-137: `def defaults(self):`
  - **def** `Run` — L139-157: `def Run(self):`
  - **def** `on_search_click` — L159-238: `def on_search_click(self, event):`
  - **def** `_ensure_credentials` — L240-296: `def _ensure_credentials(self):`
  - **def** `_prompt_for_credentials` — L298-303: `def _prompt_for_credentials(self):`
  - **def** `_api_worker_resistor` — L305-309: `def _api_worker_resistor(self, res_val, pwr_idx, tol_idx, comp_idx):`
  - **def** `_on_api_result_resistor` — L311-329: `def _on_api_result_resistor(self, delayedResult):`
  - **def** `_api_worker_capacitor` — L331-337: `def _api_worker_capacitor(self, cap_val, vol_str, type_idx, cat_id):`
  - **def** `_on_api_result_capacitor` — L339-364: `def _on_api_result_capacitor(self, delayedResult, lib_config=None):`
  - **def** `_api_worker_batch` — L366-371: `def _api_worker_batch(self, batch_text):`
  - **def** `_on_api_result_batch` — L373-392: `def _on_api_result_batch(self, delayedResult):`
  - **def** `get_token` — L394-412: `def get_token(self, force_refresh=False):`

## Data / doc files (not parsed for definitions)

- `README.md` — markdown, 100 lines
- `config.json` — json, 4 lines
