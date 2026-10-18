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

JFET_CATEGORY_ID = "288"  # JFET leaf under Single Transistors

# GUI Polarity selector idx -> Digikey ValueId for ParameterId 606 (FET Type)
JFET_POLARITY_VALUE_ID = {1: "378999", 2: "385103"}  # N-Channel, P-Channel


def process_jfet(product_json, lib_config=None):
    smd = bool((lib_config or {}).get("smd"))
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    dk_pn = digikey_pn(product_json)

    params = product_json.get("Parameters", [])
    is_pchannel = get_param(params, 606, "").strip().upper().startswith("P")
    vgs_off = get_param(params, 2270)
    idss = get_param(params, 2272)
    rds_on = get_param(params, 2189)
    pkg_raw = get_param(params, 16, "")

    symbol_name = "J_" + re.sub(r'[^A-Za-z0-9_-]', '_', mpn)

    sym_lib_name = "Q_SMD_emDashGameChanger" if smd else "Q_TH_emDashGameChanger"
    default_numbers = pick_default_numbers(
        pkg_raw, smd,
        tht_default={"G": "1", "D": "2", "S": "3"},
        smd_default={"D": "1", "S": "2", "G": "3"},
        smd_tab_default=None,
    )

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": mpn,
            "is_pchannel": is_pchannel,
            "vgs_off": vgs_off,
            "idss": idss,
            "rds_on": rds_on,
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
        "sym_lib_name": sym_lib_name,
        "fp_lib_name": sym_lib_name,
        "fp_template": None,
        "sym_template": "symbolTemplates/TransistorJFETSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s transistor generator")\n\t(generator_version "0.1")\n',
        # Consumed by plugin._confirm_and_generate_transistor before generate_library_files
        # is called - never trusted as final without a human approving/editing it.
        "pinout_confirm": build_pinout_confirm(
            "JFET", ["G", "D", "S"],
            # Documented placeholder guesses (THT: common small-signal G-D-S
            # lead order, e.g. J201/2N5457-style TO-92 parts; SMD: SOT-23 D-S-G,
            # e.g. MMBFJ201) - shown to the human as "unconfirmed", never
            # auto-applied.
            default_numbers, pkg_raw, mpn, datasheet, smd,
        ),
    }
    return processed_data


def search_tht_jfet(part_number, polarity_idx, pkg_idx, access_token, client_id, token_refresher=None, smd=False):
    part_number = part_number.strip()
    filters = mount_filter(smd)
    if not part_number and polarity_idx in JFET_POLARITY_VALUE_ID:
        filters.append({"ParameterId": 606, "FilterValues": [{"Id": JFET_POLARITY_VALUE_ID[polarity_idx]}]})

    keywords = part_number if part_number else "jfet"
    products = search_leaf(keywords, JFET_CATEGORY_ID, filters, 50, access_token, client_id, token_refresher)
    products = dedupe_and_sort(products)

    pkg_table = SMD_TRANSISTOR_PACKAGE_IDX if smd else TRANSISTOR_PACKAGE_IDX
    if pkg_idx in pkg_table:
        products = filter_by_package(products, pkg_table[pkg_idx], smd)

    return {"Products": products, "ProductsCount": len(products)}
