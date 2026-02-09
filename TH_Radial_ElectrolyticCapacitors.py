import requests
import re
import math

def generate_capacitor_polygons(diameter=5.0, pitch=2.0):
    # Radius + line thickness adjustment
    r = (diameter / 2) + 0.12
    
    # Line width adjustment for fence post problem
    line_width = 0.1
    h = line_width / 2

    # Keep-out square parameters
    ko_size = 1.56
    ko_center_x = pitch / 2
    
    # Keep-out boundaries (adjusted to prevent line thickness encroachment)
    ko_x_min = (ko_center_x - (ko_size / 2)) - h
    ko_x_max = (ko_center_x + (ko_size / 2)) + h
    ko_y_limit = (ko_size / 2) + h
    
    n_steps = 15

    def get_arc_points(y_start, y_end, steps):
        points = []
        step_size = (y_end - y_start) / steps
        for i in range(steps + 1):
            y = y_start + (i * step_size)
            x_sq = r*r - y*y
            # Safety check for sqrt
            val = max(0, x_sq)
            x = math.sqrt(val)
            points.append((x, y))
        return points

    # 1. RED POLYGON (Middle outer block)
    red_arc = get_arc_points(-ko_y_limit, ko_y_limit, n_steps)
    red_poly = red_arc + [(ko_x_max, ko_y_limit), (ko_x_max, -ko_y_limit)]

    # 2. GREEN POLYGONS (Top and Bottom segments)
    top_green_arc = get_arc_points(-r, -ko_y_limit, n_steps)
    top_green_poly = top_green_arc + [(0, -ko_y_limit), (0, -r)]
    
    bot_green_arc = get_arc_points(ko_y_limit, r, n_steps)
    bot_green_poly = bot_green_arc + [(0, r), (0, ko_y_limit)]

    # 3. BLUE RECTANGLE (Left of the keep-out)
    blue_poly = [
        (0, -ko_y_limit),
        (ko_x_min, -ko_y_limit),
        (ko_x_min, ko_y_limit),
        (0, ko_y_limit)
    ]

    return {"red": red_poly, "green_top": top_green_poly, "green_bottom": bot_green_poly, "blue": blue_poly}

def format_kicad_poly(points, layer="F.SilkS"):
    xy_str = " ".join([f"(xy {p[0]:.4f} {p[1]:.4f})" for p in points])
    return f"(fp_poly (pts {xy_str}) (stroke (width 0.1) (type solid)) (fill solid) (layer \"{layer}\"))"

def process_capacitor(product_json, lib_config=None):
    if lib_config is None:
        lib_config = {}
    designator = lib_config.get("designator", "CP")
    sym_lib_name = lib_config.get("sym_lib", "CP_TH_emDashGameChanger")
    fp_lib_name = lib_config.get("fp_lib", "CP_TH_emDashGameChanger")

    # Extraction
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    
    # DigiKey PN Logic
    variations = product_json.get("ProductVariations", [])
    dk_pn = "N/A"
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
    capacitance = "Unknown"
    tolerance = "Unknown"
    voltage = "Unknown"
    lead_spacing = "Unknown"
    diameter_raw = "Unknown"
    height_raw = "Unknown"
    
    for p in params:
        pid = p.get("ParameterId")
        if pid == 2049: capacitance = p.get("ValueText", "Unknown")
        elif pid == 3: tolerance = p.get("ValueText", "Unknown")
        elif pid == 2079: voltage = p.get("ValueText", "Unknown")
        elif pid == 508: lead_spacing = p.get("ValueText", "Unknown")
        elif pid == 46: diameter_raw = p.get("ValueText", "Unknown")
        elif pid == 1500: height_raw = p.get("ValueText", "Unknown")

    # Parsing Dimensions
    def parse_dim(val):
        if not val or val == "Unknown": return 0.0, "0.0"
        match = re.search(r'\(?(\d+\.?\d*)\s*mm\)?', val)
        if match:
            return float(match.group(1)), match.group(1)
        return 0.0, "0.0"

    diameter, diameter_str = parse_dim(diameter_raw)
    lead_spacing_mm, lead_spacing_str = parse_dim(lead_spacing)
    height, height_str = parse_dim(height_raw)

    # Formatting
    if capacitance != "Unknown":
        capacitance = capacitance.replace("uF", "µF")
    
    if tolerance != "Unknown":
        tolerance = tolerance.replace("+-", "±")

    # Names
    cap_clean = capacitance.replace("µ", "u").replace(" ", "")
    vol_clean = voltage.replace(" ", "")
    symbol_name = f"{designator}_{cap_clean}_{vol_clean}"
    footprint_name = f"CP_D{diameter_str}mm_P{lead_spacing_str}mm_H{height_str}mm.kicad_mod"

    # Polygons
    polys = generate_capacitor_polygons(diameter, lead_spacing_mm)

    processed_data = {
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
            "pinPitch": lead_spacing_mm,
            "height": height,
            "poly_red": format_kicad_poly(polys['red']),
            "poly_green_top": format_kicad_poly(polys['green_top']),
            "poly_green_bottom": format_kicad_poly(polys['green_bottom']),
            "poly_blue": format_kicad_poly(polys['blue']),
            # Silk Screen Plus Sign Center (x = -radius, y = -radius/2)
            "plus_center_x": -(diameter / 2),
            "plus_center_y": -(diameter / 3)
        },
        "footprint_name": footprint_name,
        "sym_lib_name": sym_lib_name,
        "fp_lib_name": fp_lib_name,
        "fp_template": "footprintTemplates/TH_CapacitorRadialTemplate.kicad_mod",
        "sym_template": "symbolTemplates/CapacitorPolarizedSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s capcitor-through hole-radial generator")\n\t(generator_version "0.1")\n'
    }
    
    return processed_data

def search_tht_capacitor(capacitance, voltage, type_idx, cat_id, access_token, client_id, token_refresher=None):
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

    # Type Mapping (0=Axial, 1=Radial)
    type_id = "317190" if type_idx == 0 else "392320"
    
    filters = [
        {"ParameterID": 2049, "FilterValues": [{"Id": cap_str}]},
        {"ParameterId": 16, "FilterValues": [{"Id": type_id}]}
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