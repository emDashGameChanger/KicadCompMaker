import re

try:
    from .TH_Transistor_Common import (
        match_stock_footprint, search_leaf, dedupe_and_sort, filter_by_package,
        digikey_pn, get_param, TRANSISTOR_PACKAGE_IDX, STOCK_FP_LIB,
    )
except ImportError:
    from TH_Transistor_Common import (
        match_stock_footprint, search_leaf, dedupe_and_sort, filter_by_package,
        digikey_pn, get_param, TRANSISTOR_PACKAGE_IDX, STOCK_FP_LIB,
    )

MOSFET_CATEGORY_ID = "278"  # Single FETs, MOSFETs - also holds GaNFET/SiCFET, hence the
# Technology=MOSFET filter below to exclude those.

# GUI Polarity selector idx -> Digikey ValueId for ParameterId 606 (FET Type)
MOSFET_POLARITY_VALUE_ID = {1: "378999", 2: "385103"}  # N-Channel, P-Channel
MOSFET_TECHNOLOGY_VALUE_ID = "377049"  # MOSFET (Metal Oxide)


def process_mosfet(product_json, lib_config=None):
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    dk_pn = digikey_pn(product_json)

    params = product_json.get("Parameters", [])
    is_pchannel = get_param(params, 606, "").strip().upper().startswith("P")
    vdss = get_param(params, 2068)
    id_max = get_param(params, 608)
    rds_on = get_param(params, 612)
    vgs_th = get_param(params, 1236)
    pkg_raw = get_param(params, 16, "")

    symbol_name = "Q_" + re.sub(r'[^A-Za-z0-9_-]', '_', mpn)
    fp_match = match_stock_footprint(pkg_raw)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": mpn,
            "is_pchannel": is_pchannel,
            "vdss": vdss,
            "id_max": id_max,
            "rds_on": rds_on,
            "vgs_th": vgs_th,
            # Footprint + pin numbers are placeholders until a human confirms
            # them via gui.PinoutConfirmDialog - see pinout_confirm below.
            "footprint": "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price,
            "pin_g_number": "1",
            "pin_d_number": "2",
            "pin_s_number": "3",
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "Q_TH_emDashGameChanger",
        "fp_lib_name": "Q_TH_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/TransistorMOSFETSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s transistor generator")\n\t(generator_version "0.1")\n',
        # Consumed by plugin._confirm_and_generate_transistor before generate_library_files
        # is called - never trusted as final without a human approving/editing it.
        "pinout_confirm": {
            "family": "MOSFET",
            "terminals": ["G", "D", "S"],
            # Documented placeholder guess (common small-signal G-D-S lead order,
            # e.g. 2N7000-style TO-92 parts) - shown to the human as "unconfirmed",
            # never auto-applied.
            "default_numbers": {"G": "1", "D": "2", "S": "3"},
            "package_raw": pkg_raw,
            "footprint_lib": STOCK_FP_LIB,
            "footprint_candidates": fp_match["candidates"],
            "footprint_resolved": fp_match["footprint"],
            "mpn": mpn,
            "datasheet": datasheet,
        },
    }
    return processed_data


def search_tht_mosfet(part_number, polarity_idx, pkg_idx, access_token, client_id, token_refresher=None):
    part_number = part_number.strip()
    mount_filter = [{"ParameterId": 69, "FilterValues": [{"Id": "411897"}]}]  # Through Hole

    # Part-number search: per the established convention (see TH_Diodes.py), Type/
    # Technology/Polarity filters are ignored - DigiKey's keyword match already
    # disambiguates, and extra parametric filters risk excluding legitimate variants.
    filters = list(mount_filter)
    if not part_number:
        filters.append({"ParameterId": 570, "FilterValues": [{"Id": MOSFET_TECHNOLOGY_VALUE_ID}]})  # MOSFET (Metal Oxide)
        if polarity_idx in MOSFET_POLARITY_VALUE_ID:
            filters.append({"ParameterId": 606, "FilterValues": [{"Id": MOSFET_POLARITY_VALUE_ID[polarity_idx]}]})

    keywords = part_number if part_number else "mosfet"
    products = search_leaf(keywords, MOSFET_CATEGORY_ID, filters, 50, access_token, client_id, token_refresher)
    products = dedupe_and_sort(products)

    if pkg_idx in TRANSISTOR_PACKAGE_IDX:
        products = filter_by_package(products, TRANSISTOR_PACKAGE_IDX[pkg_idx])

    return {"Products": products, "ProductsCount": len(products)}
