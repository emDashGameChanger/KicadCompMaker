import re

try:
    from .TH_Transistor_Common import (
        build_pinout_confirm, pick_default_numbers, mount_filter, search_leaf,
        dedupe_and_sort, filter_by_package, digikey_pn, get_param,
        TRANSISTOR_PACKAGE_IDX, SMD_TRANSISTOR_PACKAGE_IDX,
    )
except ImportError:
    from TH_Transistor_Common import (
        build_pinout_confirm, pick_default_numbers, mount_filter, search_leaf,
        dedupe_and_sort, filter_by_package, digikey_pn, get_param,
        TRANSISTOR_PACKAGE_IDX, SMD_TRANSISTOR_PACKAGE_IDX,
    )

BJT_CATEGORY_ID = "276"  # Single Bipolar Transistors (leaf under Bipolar (BJT))

# GUI Polarity selector idx -> Digikey ValueId for ParameterId 74 (Transistor Type)
BJT_POLARITY_VALUE_ID = {1: "380569", 2: "388182"}  # NPN, PNP


def process_bjt(product_json, lib_config=None):
    smd = bool((lib_config or {}).get("smd"))
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

    sym_lib_name = "Q_SMD_emDashGameChanger" if smd else "Q_TH_emDashGameChanger"
    default_numbers = pick_default_numbers(
        pkg_raw, smd,
        tht_default={"E": "1", "B": "2", "C": "3"},
        smd_default={"B": "1", "E": "2", "C": "3"},
        smd_tab_default={"B": "1", "C": "2", "E": "3"},
    )

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
        "sym_lib_name": sym_lib_name,
        "fp_lib_name": sym_lib_name,
        "fp_template": None,
        "sym_template": "symbolTemplates/TransistorBJTSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s transistor generator")\n\t(generator_version "0.1")\n',
        # Consumed by plugin._confirm_transistor_pinout before generate_library_files
        # is called - never trusted as final without a human approving/editing it.
        "pinout_confirm": build_pinout_confirm(
            "BJT", ["E", "B", "C"],
            # Documented placeholder guesses (THT: common small-signal TO-92
            # E-B-C lead order, e.g. 2N3904; SMD: SOT-23 B-E-C, e.g. MMBT3904;
            # tab packages B-C-E) - shown to the human as "unconfirmed", never
            # auto-applied.
            default_numbers, pkg_raw, mpn, datasheet, smd,
        ),
    }
    return processed_data


def search_tht_bjt(part_number, polarity_idx, pkg_idx, access_token, client_id, token_refresher=None, smd=False):
    part_number = part_number.strip()
    filters = mount_filter(smd)
    if not part_number and polarity_idx in BJT_POLARITY_VALUE_ID:
        filters.append({"ParameterId": 74, "FilterValues": [{"Id": BJT_POLARITY_VALUE_ID[polarity_idx]}]})

    keywords = part_number if part_number else "transistor"
    products = search_leaf(keywords, BJT_CATEGORY_ID, filters, 50, access_token, client_id, token_refresher)
    products = dedupe_and_sort(products)

    pkg_table = SMD_TRANSISTOR_PACKAGE_IDX if smd else TRANSISTOR_PACKAGE_IDX
    if pkg_idx in pkg_table:
        products = filter_by_package(products, pkg_table[pkg_idx], smd)

    return {"Products": products, "ProductsCount": len(products)}
