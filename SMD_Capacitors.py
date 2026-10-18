import re

try:
    from .DigikeyPartNumber import pick_digikey_pn
    from .DigikeyVoltageMap import parse_voltage_volts, lookup_value_id
    from .TH_Disc_Capacitors import format_capacitance, _product_voltage_volts
    from .SMD_Common import (CHIP_PACKAGE_VALUE_IDS, MLCC_MOUNT_IDS, SMD_MOUNT_IDS,
                             TANTALUM_PACKAGE_VALUE_IDS, chip_footprint, chip_size_from_package,
                             tantalum_footprint, alum_footprint, parse_mm, search_leaf,
                             get_param, clean_symbol_token, handsolder_suffix)
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn
    from DigikeyVoltageMap import parse_voltage_volts, lookup_value_id
    from TH_Disc_Capacitors import format_capacitance, _product_voltage_volts
    from SMD_Common import (CHIP_PACKAGE_VALUE_IDS, MLCC_MOUNT_IDS, SMD_MOUNT_IDS,
                            TANTALUM_PACKAGE_VALUE_IDS, chip_footprint, chip_size_from_package,
                            tantalum_footprint, alum_footprint, parse_mm, search_leaf,
                            get_param, clean_symbol_token, handsolder_suffix)

CERAMIC_CATEGORY_ID = "60"
TANTALUM_CATEGORY_ID = "59"
ALUMINUM_CATEGORY_ID = "58"

# Temperature Coefficient (ParameterId 17) label -> ValueId. Labels match
# gui.SMD_CAP_DIELECTRIC_OPTS.
MLCC_DIELECTRIC_VALUE_IDS = {"C0G/NP0": "324183", "X5R": "422407", "X7R": "422415", "X7S": "422418", "Y5V": "423168"}

_POLARIZED_PREAMBLE = '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s capacitor generator")\n\t(generator_version "0.1")\n'


def eng_capacitance(text):
    """Digi-Key capacitance text -> compact engineering form for symbol names:
    "0.1 µF" -> "100nF", "4700 pF" -> "4.7nF", "10 µF" -> "10uF"."""
    m = re.match(r'\s*([\d.]+)\s*([pnuµm]?)F', text or "")
    if not m:
        return clean_symbol_token(text or "")
    scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0}[m.group(2)]
    farads = float(m.group(1)) * scale
    for unit, mult in (("uF", 1e-6), ("nF", 1e-9), ("pF", 1e-12)):
        if farads >= mult * 0.999:
            return f"{round(farads / mult, 3):g}{unit}"
    return f"{round(farads / 1e-12, 3):g}pF"


def _voltage_text_2079(voltage):
    """'16v' / '6.3V' -> '16 V' / '6.3 V' - ParameterId 2079 (tantalum and
    aluminum "Voltage - Rated") uses the display text itself as its ValueId."""
    volts = parse_voltage_volts(voltage or "")
    return (f"{volts:g} V", volts) if volts is not None else (None, None)


def _volts_2079(product_json):
    return parse_voltage_volts(get_param(product_json, 2079, ""))


def _base_fields(product_json):
    return (product_json.get("ManufacturerProductNumber", "Unknown"),
            product_json.get("DatasheetUrl", ""),
            product_json.get("UnitPrice", 999.99),
            pick_digikey_pn(product_json))


def _voltage_display(volts, raw):
    if volts is not None:
        return f"{volts:g}V"
    return raw.replace(" ", "") if raw and raw != "Unknown" else ""


# --- Ceramic MLCC ---------------------------------------------------------

def search_smd_mlcc(capacitance, size, voltage, dielectric, access_token, client_id, token_refresher=None):
    filters = [
        {"ParameterID": 2049, "FilterValues": [{"Id": format_capacitance(capacitance)}]},
        {"ParameterId": 69, "FilterValues": [{"Id": i} for i in MLCC_MOUNT_IDS]},
    ]
    if size in CHIP_PACKAGE_VALUE_IDS:
        filters.append({"ParameterId": 16, "FilterValues": [{"Id": CHIP_PACKAGE_VALUE_IDS[size]}]})
    if dielectric in MLCC_DIELECTRIC_VALUE_IDS:
        filters.append({"ParameterId": 17, "FilterValues": [{"Id": MLCC_DIELECTRIC_VALUE_IDS[dielectric]}]})

    # Same approach as the THT disc search: server-side filter when the
    # ParameterId 14 ValueId is known, otherwise filter client-side.
    target_volts = parse_voltage_volts(voltage or "")
    needs_client_filter = False
    if target_volts is not None:
        value_id = lookup_value_id(target_volts)
        if value_id:
            filters.append({"ParameterId": 14, "FilterValues": [{"Id": value_id}]})
        else:
            needs_client_filter = True

    results = search_leaf("capacitor", "3", CERAMIC_CATEGORY_ID, filters,
                          access_token, client_id, token_refresher)
    if needs_client_filter:
        products = [p for p in results.get("Products", []) if _product_voltage_volts(p) == target_volts]
        results["Products"] = products
        results["ProductsCount"] = len(products)
    return results


def process_smd_mlcc(product_json, lib_config=None):
    handsolder = (lib_config or {}).get("handsolder", True)
    mpn, datasheet, price, dk_pn = _base_fields(product_json)

    capacitance = get_param(product_json, 2049)
    tolerance = get_param(product_json, 3).replace("+-", "±")
    voltage = _voltage_display(_product_voltage_volts(product_json), get_param(product_json, 14))
    dielectric = get_param(product_json, 17, "")
    pkg_raw = get_param(product_json, 16, "")

    size = chip_size_from_package(pkg_raw)
    footprint = chip_footprint("C", size, handsolder) if size else None

    cap = eng_capacitance(capacitance)
    parts = [size or "SMD", cap, voltage, clean_symbol_token(dielectric.split(",")[0]).replace("/", "")]
    symbol_name = "C_" + "_".join(p for p in parts if p) + handsolder_suffix(footprint)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": cap,
            "tolerance": tolerance,
            "voltage": voltage,
            "footprint": footprint or "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "C_SMD_emDashGameChanger",
        "fp_lib_name": "C_SMD_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/TH_CapacitorDiscSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s capacitor-mlcc generator")\n\t(generator_version "0.1")\n',
    }
    if not footprint:
        processed_data["error"] = f"No stock KiCad chip-capacitor footprint for package '{pkg_raw or 'unknown'}'."
    return processed_data


# --- Tantalum -------------------------------------------------------------

def tantalum_case_metric(case_label):
    """GUI/batch case label ("B (3528)", "B", "3528") -> EIA metric code, or None."""
    if not case_label:
        return None
    m = re.search(r'(\d{4})', case_label)
    if m:
        return m.group(1)
    letter = case_label.strip().upper()[:1]
    return {"A": "3216", "B": "3528", "C": "6032", "D": "7343", "E": "7360"}.get(letter)


def search_smd_tantalum(capacitance, voltage, case, access_token, client_id, token_refresher=None):
    filters = [
        {"ParameterID": 2049, "FilterValues": [{"Id": format_capacitance(capacitance)}]},
        {"ParameterId": 69, "FilterValues": [{"Id": i} for i in SMD_MOUNT_IDS]},
    ]
    volt_text, _ = _voltage_text_2079(voltage)
    if volt_text:
        filters.append({"ParameterId": 2079, "FilterValues": [{"Id": volt_text}]})
    metric = tantalum_case_metric(case)
    if metric in TANTALUM_PACKAGE_VALUE_IDS:
        filters.append({"ParameterId": 16, "FilterValues": [{"Id": i} for i in TANTALUM_PACKAGE_VALUE_IDS[metric]]})
    return search_leaf("capacitor", "3", TANTALUM_CATEGORY_ID, filters,
                       access_token, client_id, token_refresher)


def process_smd_tantalum(product_json, lib_config=None):
    handsolder = (lib_config or {}).get("handsolder", True)
    mpn, datasheet, price, dk_pn = _base_fields(product_json)

    capacitance = get_param(product_json, 2049)
    tolerance = get_param(product_json, 3).replace("+-", "±")
    voltage = _voltage_display(_volts_2079(product_json), get_param(product_json, 2079))
    pkg_raw = get_param(product_json, 16, "")
    height = parse_mm(get_param(product_json, 1500, ""))
    size_code = get_param(product_json, 987, "")

    footprint, letter = tantalum_footprint(pkg_raw, height, size_code, handsolder)
    cap = eng_capacitance(capacitance)
    symbol_name = "CP_Tant_" + "_".join(p for p in (letter or "X", cap, voltage) if p) + handsolder_suffix(footprint)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": cap,
            "tolerance": tolerance,
            "voltage": voltage,
            "footprint": footprint or "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "CP_SMD_emDashGameChanger",
        "fp_lib_name": "CP_SMD_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/CapacitorPolarizedSymbolTemplate.txt",
        "sym_preamble": _POLARIZED_PREAMBLE,
    }
    if not footprint:
        processed_data["error"] = f"No stock KiCad molded-tantalum footprint for package '{pkg_raw or 'unknown'}'."
    return processed_data


# --- SMD aluminum electrolytic --------------------------------------------

def search_smd_aluminum(capacitance, voltage, access_token, client_id, token_refresher=None):
    filters = [
        {"ParameterID": 2049, "FilterValues": [{"Id": format_capacitance(capacitance)}]},
        {"ParameterId": 69, "FilterValues": [{"Id": i} for i in SMD_MOUNT_IDS]},
    ]
    volt_text, _ = _voltage_text_2079(voltage)
    if volt_text:
        filters.append({"ParameterId": 2079, "FilterValues": [{"Id": volt_text}]})
    return search_leaf("capacitor", "3", ALUMINUM_CATEGORY_ID, filters,
                       access_token, client_id, token_refresher)


def process_smd_aluminum(product_json, lib_config=None):
    mpn, datasheet, price, dk_pn = _base_fields(product_json)

    capacitance = get_param(product_json, 2049)
    tolerance = get_param(product_json, 3).replace("+-", "±")
    voltage = _voltage_display(_volts_2079(product_json), get_param(product_json, 2079))
    dia_raw = get_param(product_json, 46, "")
    height_raw = get_param(product_json, 1500, "")

    footprint, can = alum_footprint(parse_mm(dia_raw), parse_mm(height_raw))
    cap = eng_capacitance(capacitance)
    symbol_name = "CP_Elec_" + "_".join(p for p in (cap, voltage, can) if p)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": cap,
            "tolerance": tolerance,
            "voltage": voltage,
            "footprint": footprint or "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "CP_SMD_emDashGameChanger",
        "fp_lib_name": "CP_SMD_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/CapacitorPolarizedSymbolTemplate.txt",
        "sym_preamble": _POLARIZED_PREAMBLE,
    }
    if not footprint:
        processed_data["error"] = (f"No stock KiCad CP_Elec footprint close to this can "
                                   f"({dia_raw or '?'} x {height_raw or '?'}).")
    return processed_data
