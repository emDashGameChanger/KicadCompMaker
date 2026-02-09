import requests
import re
import json
import os

def search_tht_disc_capacitor(capacitance, voltage, cat_id, access_token, client_id, token_refresher=None):
    # Format Capacitance
    cap_clean = capacitance.strip()
    if not cap_clean.endswith("F"):
        cap_clean += "F"
    
    # Ensure space between value and unit (e.g. "22 µF")
    match = re.match(r'^([\d\.]+)\s*([µumkM]?)F$', cap_clean)
    if match:
        val, unit = match.groups()
        cap_str = f"{val} {unit}F"
    else:
        cap_str = cap_clean

    # Format Voltage
    if voltage.lower() == "i don't care":
        vol_str = None
    else:
        vol_clean = voltage.lower().replace("v", "").strip()
        vol_str = f"{vol_clean} V"

    filters = [
        {"ParameterID": 2049, "FilterValues": [{"Id": cap_str}]},
        {"ParameterId": 69, "FilterValues": [{"Id": "411897"}]},
        {"ParameterId": 16, "FilterValues": [{"Id": "392278"}, {"Id": "392342"}]}
    ]
    if vol_str:
        filters.append({"ParameterId": 2079, "FilterValues": [{"Id": vol_str}]})

    url = "https://api.digikey.com/products/v4/search/keyword"
    payload = {
        "Keywords": "capacitor",
        "Limit": 50,
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MinimumOrderQuantity": 1,
            "CategoryFilter": [{"id": "3"}],
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "ParameterFilterRequest": {
                "CategoryFilter": {"id": str(cat_id)},
                "ParameterFilters": filters
            },
            "SearchOptions": ["NormallyStocking"]
        },
        "ExcludedContent": ["FilterOptions"],
        "SortOptions": {"Field": "Price", "SortOrder": "Ascending"}
    }
    headers = {
        "x-digikey-client-id": client_id,
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}"
    }
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 401 and token_refresher:
        new_token = token_refresher()
        if new_token:
            headers["authorization"] = f"Bearer {new_token}"
            response = requests.post(url, json=payload, headers=headers)

    return response.json()

def process_disc_capacitor(product_json, lib_config=None):
    if lib_config is None:
        lib_config = {}
    
    designator = lib_config.get("designator", "C")
    sym_lib_name = lib_config.get("sym_lib", "C_TH_emDashGameChanger")
    fp_lib_name = lib_config.get("fp_lib", "C_TH_emDashGameChanger")

    # 1. General Info
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 0.0)
    
    # DK Part Number
    variations = product_json.get("ProductVariations", [])
    dk_pn = "N/A"
    for v in variations:
        if v.get("PackageType", {}).get("Id") in [1, 2]: # Tape&Reel or CutTape
            dk_pn = v.get("DigiKeyProductNumber")
            break
    if dk_pn == "N/A" and variations:
        dk_pn = variations[0].get("DigiKeyProductNumber")

    # 2. Parameters
    params = product_json.get("Parameters", [])
    capacitance = "Unknown"
    tolerance = "Unknown"
    voltage = "Unknown"
    lead_spacing_raw = "Unknown"
    diameter_raw = "Unknown"
    
    for p in params:
        pid = p.get("ParameterId")
        val = p.get("ValueText", "Unknown")
        if pid == 2049: capacitance = val
        elif pid == 3: tolerance = val
        elif pid == 2079: voltage = val
        elif pid == 508: lead_spacing_raw = val
        elif pid == 46: diameter_raw = val

    # Fallback for Voltage if Unknown
    if voltage == "Unknown":
        desc = product_json.get("Description", {}).get("DetailedDescription", "")
        match = re.search(r'(\d+(\.\d+)?)\s*V', desc)
        if match:
            voltage = match.group(1) + "V"

    # 3. Parsing
    diameter = 0.0
    width = 3.0 # Default thickness for disc capacitors if not specified
    diameter_str = "0.0"
    width_str = "3.0"

    if diameter_raw and diameter_raw != "Unknown":
        # Try LxW format first: "0.157\" L x 0.098\" W (4.00mm x 2.50mm)"
        lxw_match = re.search(r'\(([\d\.]+)\s*mm\s*x\s*([\d\.]+)\s*mm\)', diameter_raw)
        if lxw_match:
            diameter = float(lxw_match.group(1))
            width = float(lxw_match.group(2))
            diameter_str = lxw_match.group(1)
            width_str = lxw_match.group(2)
        else:
            # Try Diameter format: "0.252\" Dia (6.40mm)"
            dia_match = re.search(r'\(?([\d\.]+)\s*mm\)?', diameter_raw)
            if dia_match:
                diameter = float(dia_match.group(1))
                diameter_str = dia_match.group(1)

    def parse_pitch(val):
        if not val or val == "Unknown": return 0.0, "0.0"
        match = re.search(r'\(?([\d\.]+)\s*mm\)?', val)
        if match: return float(match.group(1)), match.group(1)
        return 0.0, "0.0"

    pin_pitch, pin_pitch_str = parse_pitch(lead_spacing_raw)

    # Formatting
    if capacitance != "Unknown": capacitance = capacitance.replace("uF", "µF").replace(" ", "")
    if tolerance != "Unknown": tolerance = tolerance.replace("+-", "±")
    
    if voltage == "Unknown":
        voltage = ""
    else:
        voltage = voltage.replace(" ", "")

    symbol_name = f"{designator}_{capacitance}_{voltage}"
    if symbol_name.endswith("_"): symbol_name = symbol_name[:-1]

    footprint_name = f"C_D{diameter_str}mm_W{width_str}mm_P{pin_pitch_str}mm.kicad_mod"

    pad_size = 1.6
    try:
        with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
            pad_size = json.load(f).get("TH_DISC_CAP_PAD_SIZE", 1.6)
    except Exception:
        pass

    return {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": capacitance,
            "tolerance": tolerance,
            "voltage": voltage,
            "footprint": f"{fp_lib_name}:{footprint_name.replace('.kicad_mod', '')}",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {
            "diameter": diameter,
            "width": width,
            "pinPitch": pin_pitch,
            "padSize": pad_size
        },
        "footprint_name": footprint_name,
        "sym_lib_name": sym_lib_name,
        "fp_lib_name": fp_lib_name,
        "fp_template": "footprintTemplates/TH_CapacitorDiscTemplate.kicad_mod",
        "sym_template": "symbolTemplates/TH_CapacitorDiscSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s capacitor-disc generator")\n\t(generator_version "0.1")\n'
    }

if __name__ == '__main__':
    # Example usage (replace with actual values from gui.py)
    capacitance = "100 pF"
    voltage = "50 V"
    cat_id = "60"  # Example category ID for ceramic disc capacitors
    access_token = "YOUR_ACCESS_TOKEN"
    client_id = "YOUR_CLIENT_ID"

    results = search_tht_disc_capacitor(capacitance, voltage, cat_id, access_token, client_id)

    if results and results.get("ProductsCount", 0) > 0:
        print("Search Results:")
        for product in results["Products"]:
            mpn = product.get("ManufacturerProductNumber", "N/A")
            price = str(product.get("UnitPrice", "N/A"))
            stock = str(product.get("QuantityAvailable", "N/A"))
            desc = product.get("Description", {}).get("DetailedDescription", "N/A")

            print(f"  MPN: {mpn}")
            print(f"  Price: {price}")
            print(f"  Stock: {stock}")
            print(f"  Description: {desc}")
            print("-" * 20)
    elif results is None:
        print("API call failed.")
    else:
        print("No results found for the specified criteria.")