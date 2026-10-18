try:
    from .DigikeyPartNumber import pick_digikey_pn
    from .TH_Resistors import format_resistance
    from .SMD_Common import (CHIP_PACKAGE_VALUE_IDS, chip_footprint, chip_size_from_package,
                             search_leaf, get_param, clean_symbol_token, handsolder_suffix)
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn
    from TH_Resistors import format_resistance
    from SMD_Common import (CHIP_PACKAGE_VALUE_IDS, chip_footprint, chip_size_from_package,
                            search_leaf, get_param, clean_symbol_token, handsolder_suffix)

SMD_RESISTOR_CATEGORY_ID = "52"  # Chip Resistor - Surface Mount (THT is 53)

# Option label -> Digi-Key ValueId. Labels match gui.SMD_RES_*_OPTS; anything
# not in these maps ("I don't care") skips that filter.
SMD_RES_TOL_VALUE_IDS = {"0.1%": "731", "0.5%": "976", "1%": "1131", "2%": "1684", "5%": "2503"}  # ParameterId 3
SMD_RES_PWR_VALUE_IDS = {  # ParameterId 2
    "1/20W": "7524", "1/16W": "7854", "1/10W": "14064", "1/8W": "10879",
    "1/4W": "16543", "1/2W": "28682", "1W": "121219",
}


def search_smd_resistor(resistance, size, tolerance, power, access_token, client_id, token_refresher=None):
    filters = [{"ParameterID": 2085, "FilterValues": [{"Id": format_resistance(resistance)}]}]
    if size in CHIP_PACKAGE_VALUE_IDS:
        filters.append({"ParameterId": 16, "FilterValues": [{"Id": CHIP_PACKAGE_VALUE_IDS[size]}]})
    if tolerance in SMD_RES_TOL_VALUE_IDS:
        filters.append({"ParameterId": 3, "FilterValues": [{"Id": SMD_RES_TOL_VALUE_IDS[tolerance]}]})
    if power in SMD_RES_PWR_VALUE_IDS:
        filters.append({"ParameterId": 2, "FilterValues": [{"Id": SMD_RES_PWR_VALUE_IDS[power]}]})
    return search_leaf("resistor", "2", SMD_RESISTOR_CATEGORY_ID, filters,
                       access_token, client_id, token_refresher)


def process_smd_resistor(product_json, lib_config=None):
    handsolder = (lib_config or {}).get("handsolder", True)
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    dk_pn = pick_digikey_pn(product_json)

    resistance = "Unknown"
    for p in product_json.get("Parameters", []):
        if p.get("ParameterId") == 2085:
            resistance = p.get("ValueId", "Unknown")  # e.g. "10 kOhms" - same field THT uses
    resistance = resistance.replace("Ohms", "Ω")
    tolerance = get_param(product_json, 3)
    power = get_param(product_json, 2)
    pkg_raw = get_param(product_json, 16, "")

    size = chip_size_from_package(pkg_raw)
    footprint = chip_footprint("R", size, handsolder) if size else None
    error = None
    if not footprint:
        error = f"No stock KiCad chip-resistor footprint for package '{pkg_raw or 'unknown'}'."

    symbol_name = "R_" + "_".join(clean_symbol_token(t) for t in (size or "SMD", resistance, tolerance))
    symbol_name += handsolder_suffix(footprint)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": resistance,
            "tolerance": tolerance,
            "power": power,
            "footprint": footprint or "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "R_SMD_emDashGameChanger",
        "fp_lib_name": "R_SMD_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/ResistorSymbolTemplate.txt",
    }
    if error:
        processed_data["error"] = error
    return processed_data
