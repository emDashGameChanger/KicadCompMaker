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

BJT_CATEGORY_ID = "276"  # Single Bipolar Transistors (leaf under Bipolar (BJT))

# GUI Polarity selector idx -> Digikey ValueId for ParameterId 74 (Transistor Type)
BJT_POLARITY_VALUE_ID = {1: "380569", 2: "388182"}  # NPN, PNP


def process_bjt(product_json, lib_config=None):
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    dk_pn = digikey_pn(product_json)

    params = product_json.get("Parameters", [])
    is_pnp = get_param(params, 74, "").strip().upper() == "PNP"
    hfe = get_param(params, 891)
    vceo = get_param(params, 2103)
    ic = get_param(params, 2101)
    pkg_raw = get_param(params, 16, "")

    symbol_name = "Q_" + re.sub(r'[^A-Za-z0-9_-]', '_', mpn)
    fp_match = match_stock_footprint(pkg_raw)

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": mpn,
            "is_pnp": is_pnp,
            "hfe": hfe,
            "vceo": vceo,
            "ic": ic,
            # Footprint + pin numbers are placeholders until a human confirms
            # them via gui.PinoutConfirmDialog - see pinout_confirm below.
            "footprint": "",
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price,
            "pin_b_number": "2",
            "pin_c_number": "3",
            "pin_e_number": "1",
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": "Q_TH_emDashGameChanger",
        "fp_lib_name": "Q_TH_emDashGameChanger",
        "fp_template": None,
        "sym_template": "symbolTemplates/TransistorBJTSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s transistor generator")\n\t(generator_version "0.1")\n',
        # Consumed by plugin._confirm_transistor_pinout before generate_library_files
        # is called - never trusted as final without a human approving/editing it.
        "pinout_confirm": {
            "family": "BJT",
            "terminals": ["E", "B", "C"],
            # Documented placeholder guess (common small-signal TO-92 E-B-C lead
            # order, e.g. 2N3904) - shown to the human as "unconfirmed", never
            # auto-applied.
            "default_numbers": {"E": "1", "B": "2", "C": "3"},
            "package_raw": pkg_raw,
            "footprint_lib": STOCK_FP_LIB,
            "footprint_candidates": fp_match["candidates"],
            "footprint_resolved": fp_match["footprint"],
            "mpn": mpn,
            "datasheet": datasheet,
        },
    }
    return processed_data


def search_tht_bjt(part_number, polarity_idx, pkg_idx, access_token, client_id, token_refresher=None):
    part_number = part_number.strip()
    mount_filter = [{"ParameterId": 69, "FilterValues": [{"Id": "411897"}]}]  # Through Hole

    filters = list(mount_filter)
    if not part_number and polarity_idx in BJT_POLARITY_VALUE_ID:
        filters.append({"ParameterId": 74, "FilterValues": [{"Id": BJT_POLARITY_VALUE_ID[polarity_idx]}]})

    keywords = part_number if part_number else "transistor"
    products = search_leaf(keywords, BJT_CATEGORY_ID, filters, 50, access_token, client_id, token_refresher)
    products = dedupe_and_sort(products)

    if pkg_idx in TRANSISTOR_PACKAGE_IDX:
        products = filter_by_package(products, TRANSISTOR_PACKAGE_IDX[pkg_idx])

    return {"Products": products, "ProductsCount": len(products)}
