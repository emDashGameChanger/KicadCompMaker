import requests
import re
import math

def process_resistor(product_json):
    # Extraction
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    
    # DigiKey PN Logic
    variations = product_json.get("ProductVariations", [])
    dk_pn = "N/A"
    # Priority: Cut Tape (2), Tape & Reel (1), then first available
    for v in variations:
        if v.get("PackageType", {}).get("Id") == 2:
            dk_pn = v.get("DigiKeyProductNumber")
            break
    if dk_pn == "N/A":
        for v in variations:
            if v.get("PackageType", {}).get("Id") == 1:
                dk_pn = v.get("DigiKeyProductNumber")
                break
    if dk_pn == "N/A" and variations:
        dk_pn = variations[0].get("DigiKeyProductNumber")

    # Parameters
    params = product_json.get("Parameters", [])
    resistance = "Unknown"
    tolerance = "Unknown"
    power = "Unknown"
    dims_raw = "Unknown"
    
    for p in params:
        pid = p.get("ParameterId")
        if pid == 2085: resistance = p.get("ValueId", "Unknown")
        elif pid == 3: tolerance = p.get("ValueText", "Unknown")
        elif pid == 2: power = p.get("ValueText", "Unknown")
        elif pid == 46: dims_raw = p.get("ValueText", "Unknown")

    # Processing
    om = "\u03A9"
    resistance = resistance.replace("Ohms", om)
    tol_clean = tolerance.replace("±", "").replace("+-", "").strip()
    power_clean = power.replace(" ", "")
    symbol_name = f"R_{resistance}_{power_clean}_{tol_clean}"
    
    diameter = 0.0
    length = 0.0
    pin_pitch = 0.0
    
    # Dimensions Regex
    match = re.search(r'([0-9]+\.[0-9]+)mm\sx\s([0-9]+\.[0-9]+)mm', dims_raw)
    if match:
        diameter = round(float(match.group(1)), 3)
        length = round(float(match.group(2)), 3)
        # Grid round up logic: math.ceil(length / 2.54) * 2.54
        pin_pitch = math.ceil(length / 2.54) * 2.54
        pin_pitch = round(pin_pitch, 2)
    
    footprint_name = f"R_L{length}mm_D{diameter}mm_P{pin_pitch}mm.kicad_mod"
    
    # Determine Library Names
    sym_lib_name = "R_TH_emDashGameChanger"
    fp_lib_name = "R_TH_emDashGameChanger"

    # Template Data Construction
    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": resistance,
            "tolerance": tolerance,
            "power": power,
            "footprint": f"{fp_lib_name}:{footprint_name.replace('.kicad_mod', '')}",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {
            "padSize": 1.4,
            "length": length,
            "diameter": diameter,
            "pinPitch": pin_pitch,
            "powerRating": power,
            "refOffsetX": 2.5,
            "refOffsetY": round(-((diameter / 2) + 1.0), 2),
            "valueOffsetX": 0.5,
            "valueOffsetY": round((diameter / 2) + 0.5, 2)
        },
        "footprint_name": footprint_name,
        "Raw Dimensions": dims_raw,
        "sym_lib_name": sym_lib_name,
        "fp_lib_name": fp_lib_name,
        "fp_template": "footprintTemplates/TH_ResistorTemplate.kicad_mod",
        "sym_template": "symbolTemplates/ResistorSymbolTemplate.txt"
    }
    
    return processed_data

def search_tht_resistor(resistance, power_idx, tolerance_idx, access_token, client_id, token_refresher=None):
    # Format Resistance Value
    res_val = resistance.strip()
    if res_val.lower().endswith('k'):
        res_str = f"{res_val[:-1]} kOhms"
    elif res_val.lower().endswith('m'):
        res_str = f"{res_val[:-1]} MOhms"
    else:
        res_str = f"{res_val} Ohms"

    # Power Mapping
    power_map = {
        0: "10879", # 1/8 watt
        1: "16543", # 1/4 watt
        2: "28682", # 1/2 watt
        3: "121219" # 1 watt
    }
    pwr_val = power_map.get(power_idx, "10879")

    # Tolerance Mapping
    tol_map = {
        0: "731",  # .1%
        1: "1131", # 1%
        2: "1684", # 2%
        3: "2503"  # 5%
    }
    tol_val = tol_map.get(tolerance_idx, "2503")

    url = "https://api.digikey.com/products/v4/search/keyword"
    payload = {
        "Keywords": "resistor",
        "Limit": 50,
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MinimumOrderQuantity": 1,
            "CategoryFilter": [{"id": "2"}],
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "ParameterFilterRequest": {
                "CategoryFilter": {"id": "53"},
                "ParameterFilters": [
                    {"ParameterID": 2085, "FilterValues": [{"Id": res_str}]},
                    {"ParameterId": 3, "FilterValues": [{"Id": tol_val}]},
                    {"ParameterId": 2, "FilterValues": [{"Id": pwr_val}]}
                ]
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