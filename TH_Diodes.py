import requests
import re
import concurrent.futures
try:
    from .DigikeyPartNumber import pick_digikey_pn, check_api_response
    from .SMD_Common import handsolder_suffix
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn, check_api_response
    from SMD_Common import handsolder_suffix

# Package text (from ParameterId 16, "Package / Case") -> (stock KiCad footprint
# name in the Diode_THT library, body length mm, body diameter mm). Dimensions and
# footprint names come straight from KiCad's own Diode_THT.pretty files (the smallest
# available Horizontal-pitch variant for each package), not hand-derived.
DIODE_STOCK_FOOTPRINTS = {
    "DO-41":    ("D_DO-41_SOD81_P7.62mm_Horizontal", 5.2, 2.7),
    "DO-35":    ("D_DO-35_SOD27_P7.62mm_Horizontal", 4.0, 2.0),
    "DO-34":    ("D_DO-34_SOD68_P7.62mm_Horizontal", 3.04, 1.6),
    "DO-15":    ("D_DO-15_P10.16mm_Horizontal", 7.6, 3.6),
    "DO-201AD": ("D_DO-201AD_P12.70mm_Horizontal", 9.5, 5.2),
    "DO-201":   ("D_DO-201_P12.70mm_Horizontal", 9.5, 5.2),
    "DO-201AE": ("D_DO-201AE_P12.70mm_Horizontal", 9.5, 5.2),
    "DO-27":    ("D_DO-27_P12.70mm_Horizontal", 9.52, 5.33),
}

# Alternate JEDEC/vendor names DigiKey's "Package / Case" text uses for the same
# physical package as one of the keys above.
DIODE_PACKAGE_ALIASES = {
    "DO-204AL": "DO-41",
    "DO-204AH": "DO-35",
    "DO-204AC": "DO-15",
    "DO-213AB": "DO-34",
}

STOCK_FP_LIB = "Diode_THT"  # KiCad's own stock footprint library nickname

# Surface-mount counterpart: normalized package -> (stock Diode_SMD footprint,
# hand-solder variant or None). Pad 1 is the cathode on every one of these,
# matching DiodeSymbolTemplate's pin 1 = K. SMD packages never fall back to a
# generated footprint - an unmapped package is reported as an error instead.
SMD_DIODE_STOCK_FOOTPRINTS = {
    "SOD-123":     ("D_SOD-123", None),
    "SOD-123F":    ("D_SOD-123F", None),
    "SOD-323":     ("D_SOD-323", "D_SOD-323_HandSoldering"),
    "SOD-323F":    ("D_SOD-323F", None),
    "SOD-523":     ("D_SOD-523", None),
    "SOD-128":     ("D_SOD-128", None),
    "PowerDI-123": ("D_PowerDI-123", None),
    "SMA":         ("D_SMA", "D_SMA_Handsoldering"),
    "SMB":         ("D_SMB", "D_SMB_Handsoldering"),
    "SMC":         ("D_SMC", "D_SMC_Handsoldering"),
    "MiniMELF":    ("D_MiniMELF", "D_MiniMELF_Handsoldering"),
    "MELF":        ("D_MELF", "D_MELF_Handsoldering"),
}

# DigiKey's SMD "Package / Case" text leads with the JEDEC name, e.g.
# "DO-214AC, SMA", "DO-213AC, MINI-MELF, SOD-80", "SC-76, SOD-323".
SMD_DIODE_PACKAGE_ALIASES = {
    "DO-214AC": "SMA",
    "DO-214AA": "SMB",
    "DO-214AB": "SMC",
    "DO-213AC": "MiniMELF",
    "MINI-MELF": "MiniMELF",
    "SOD-80": "MiniMELF",
    "DO-213AB": "MELF",
    "POWERDI-123": "PowerDI-123",
}

SMD_STOCK_FP_LIB = "Diode_SMD"

# GUI Type selector idx -> (DigiKey leaf CategoryId or None, has Technology filter)
DIODE_TYPE_CATEGORIES = {
    0: (None, True),   # I don't care
    1: (280, True),    # Standard Diode (Single Diodes)
    2: (287, False),   # Zener (Single Zener Diodes)
    3: (299, True),    # Bridge Rectifier
    4: (286, False),   # Diode Array
    5: (295, False),   # Zener Array
    6: (284, False),   # RF Diode
    7: (282, False),   # Variable Capacitance (Varicap)
}

# GUI Package selector idx -> normalized package key
DIODE_PACKAGE_IDX = {
    1: "DO-41",
    2: "DO-35",
    3: "DO-15",
    4: "DO-201AD",
}

# GUI SMD Package selector idx -> normalized package key
SMD_DIODE_PACKAGE_IDX = {
    1: "SOD-123",
    2: "SOD-323",
    3: "SOD-523",
    4: "SMA",
    5: "SMB",
    6: "SMC",
    7: "MiniMELF",
}

THT_MOUNT_FILTER = [{"ParameterId": 69, "FilterValues": [{"Id": "411897"}]}]  # Through Hole
SMD_MOUNT_FILTER = [{"ParameterId": 69, "FilterValues": [{"Id": "409393"}, {"Id": "409430"}]}]  # Surface Mount (+ wettable flank)


def normalize_package(raw_text, smd=False):
    """Returns a key into DIODE_STOCK_FOOTPRINTS (or SMD_DIODE_STOCK_FOOTPRINTS
    when smd), or None if unrecognized."""
    if smd:
        text = (raw_text or "").upper().replace("\u2122", "")  # drop the TM in "PowerDI(TM) 123"
        text = re.sub(r'POWERDI\s*-?\s*123', 'POWERDI-123', text)
        for tok in re.findall(r'MINI-MELF|MELF|POWERDI-123|(?:DO|SOD|SC)-\d+[A-Z]*|\bSM[ABC]\b', text):
            tok = SMD_DIODE_PACKAGE_ALIASES.get(tok, tok)
            if tok in SMD_DIODE_STOCK_FOOTPRINTS:
                return tok
        return None
    for tok in re.findall(r'DO-\d+[A-Z]*', raw_text or ""):
        tok = DIODE_PACKAGE_ALIASES.get(tok, tok)
        if tok in DIODE_STOCK_FOOTPRINTS:
            return tok
    return None


def process_diode(product_json, lib_config=None):
    smd = bool((lib_config or {}).get("smd"))
    handsolder = (lib_config or {}).get("handsolder", True)
    # Extraction
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)

    # DigiKey PN Logic
    dk_pn = pick_digikey_pn(product_json)

    # Parameters
    params = product_json.get("Parameters", [])
    technology = "Unknown"
    vf = "Unknown"
    io = "Unknown"
    vr = "Unknown"
    pkg_raw = ""

    for p in params:
        pid = p.get("ParameterId")
        if pid == 570: technology = p.get("ValueText", "Unknown")
        elif pid == 2261: vf = p.get("ValueText", "Unknown")
        elif pid == 914: io = p.get("ValueText", "Unknown")
        elif pid == 2071: vr = p.get("ValueText", "Unknown")
        elif pid == 16: pkg_raw = p.get("ValueText", "")

    # Names - MPN-driven (search is part-number-first for diodes, unlike the
    # value-driven resistor/capacitor generators)
    symbol_name = "D_" + re.sub(r'[^A-Za-z0-9_-]', '_', mpn)

    package = normalize_package(pkg_raw, smd)
    error = None
    if smd:
        footprint_name = None
        footprint_data = {}
        skip_footprint_gen = True
        if package:
            fp_name, hand_name = SMD_DIODE_STOCK_FOOTPRINTS[package]
            if handsolder and hand_name:
                fp_name = hand_name
            footprint_field = f"{SMD_STOCK_FP_LIB}:{fp_name}"
            symbol_name += handsolder_suffix(fp_name)
        else:
            footprint_field = ""
            error = (f"No stock 2-terminal KiCad footprint for package '{pkg_raw or 'unknown'}' "
                     f"(multi-pin/array SMD diodes aren't supported).")
    elif package:
        fp_name, length, diameter = DIODE_STOCK_FOOTPRINTS[package]
        footprint_field = f"{STOCK_FP_LIB}:{fp_name}"
        skip_footprint_gen = True
        footprint_name = None
        footprint_data = {}
    else:
        # Fallback: unmatched package, generate a footprint the old way
        length, diameter = 5.2, 2.7  # DO-41-ish nominal fallback dimensions
        pad_size = round(diameter * 0.8, 2)
        drill = round(pad_size * 0.5, 2)
        pin_pitch = 7.62
        footprint_name = f"D_L{length}mm_D{diameter}mm_P{pin_pitch}mm.kicad_mod"
        footprint_field = f"D_TH_emDashGameChanger:{footprint_name.replace('.kicad_mod', '')}"
        skip_footprint_gen = False
        footprint_data = {
            "padSize": pad_size,
            "drill": drill,
            "length": length,
            "diameter": diameter,
            "pinPitch": pin_pitch,
        }

    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": mpn,
            "technology": technology,
            "vf": vf,
            "vr": vr,
            "io": io,
            "footprint": footprint_field,
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price
        },
        "Footprint Data": footprint_data,
        "footprint_name": footprint_name,
        "skip_footprint_gen": skip_footprint_gen,
        "sym_lib_name": "D_SMD_emDashGameChanger" if smd else "D_TH_emDashGameChanger",
        "fp_lib_name": "D_SMD_emDashGameChanger" if smd else "D_TH_emDashGameChanger",
        "fp_template": "footprintTemplates/TH_DiodeTemplate.kicad_mod",
        "sym_template": "symbolTemplates/DiodeSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s diode generator")\n\t(generator_version "0.1")\n'
    }
    if error:
        # generate_library_files refuses to write anything when this is set
        processed_data["error"] = error

    return processed_data


DIODE_TECH_MAP = {1: "400378", 2: "407938", 3: "729988"}  # Schottky/Standard/SiC Schottky

# Every true leaf under Diodes(2042), with whether it supports the Technology(570)
# parametric filter. DigiKey's API only populates a product's Parameters[] array when
# the request's ParameterFilterRequest is scoped to a leaf category with a non-empty
# ParameterFilters list - omitting it (or scoping to a non-leaf) returns Parameters: []
# for every product, and scoping to a leaf that doesn't match the keyword's actual
# category throws HTTP 400 rather than just 0 results. So any search that can't name a
# single known-correct leaf up front (a bare part-number search, or a "I don't care"
# Type browse) has to probe every leaf and merge what comes back, treating both empty
# results and 400s as "this leaf doesn't apply" rather than an error.
DIODE_ALL_LEAVES = [(cat_id, has_tech) for cat_id, has_tech in DIODE_TYPE_CATEGORIES.values() if cat_id is not None]

URL = "https://api.digikey.com/products/v4/search/keyword"


def _build_payload(keywords, filter_req, limit):
    return {
        "Keywords": keywords,
        "Limit": limit,
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MinimumOrderQuantity": 1,
            "CategoryFilter": [{"id": "2042"}],  # Diodes - broad outer filter, OK to be non-leaf
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "ParameterFilterRequest": filter_req,
            "SearchOptions": ["NormallyStocking"]
        },
        "ExcludedContent": ["FilterOptions"],
        "SortOptions": {"Field": "Price", "SortOrder": "Ascending"}
    }


def _post_search(keywords, filter_req, limit, access_token, client_id):
    headers = {
        "x-digikey-client-id": client_id,
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}"
    }
    return requests.post(URL, json=_build_payload(keywords, filter_req, limit), headers=headers)


def _search_leaves(keywords, leaves, access_token, client_id, token_refresher):
    """Query each (leaf_cat_id, filters) pair in parallel, treat 400s/empty results as
    'no match in this leaf', and return the merged product list. A single 401 anywhere
    triggers one token refresh, then a serial retry of just the leaves that failed."""

    def _run(leaf_filters, token):
        cat_id, filters = leaf_filters
        filter_req = {"CategoryFilter": {"id": str(cat_id)}, "ParameterFilters": filters}
        resp = _post_search(keywords, filter_req, 50, token, client_id)
        return leaf_filters, resp

    products = []
    to_retry = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(leaves)) as executor:
        futures = [executor.submit(_run, lf, access_token) for lf in leaves]
        for future in concurrent.futures.as_completed(futures):
            leaf_filters, resp = future.result()
            check_api_response(resp)
            if resp.status_code == 401:
                to_retry.append(leaf_filters)
            elif resp.status_code == 200:
                products.extend(resp.json().get("Products", []))
            # any other status (400 wrong-leaf, etc.) - skip, not an error

    if to_retry and token_refresher:
        new_token = token_refresher()
        if new_token:
            for leaf_filters in to_retry:
                _, resp = _run(leaf_filters, new_token)
                check_api_response(resp)
                if resp.status_code == 200:
                    products.extend(resp.json().get("Products", []))

    return products


def _dedupe_and_sort(products):
    seen = set()
    deduped = []
    for p in products:
        key = p.get("ManufacturerProductNumber")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    deduped.sort(key=lambda p: p.get("UnitPrice", 999.99))
    return deduped


def search_tht_diode(part_number, type_idx, tech_idx, pkg_idx, access_token, client_id, token_refresher=None):
    return search_diode(part_number, type_idx, tech_idx, pkg_idx, access_token, client_id, token_refresher)


def search_diode(part_number, type_idx, tech_idx, pkg_idx, access_token, client_id, token_refresher=None, smd=False):
    part_number = part_number.strip()
    mount_filter = SMD_MOUNT_FILTER if smd else THT_MOUNT_FILTER
    pkg_table = SMD_DIODE_PACKAGE_IDX if smd else DIODE_PACKAGE_IDX
    needs_pkg_filter = pkg_idx in pkg_table

    if part_number:
        # Part-number search: per explicit user instruction, Type/Technology/Package
        # filters are ignored - DigiKey's keyword match already disambiguates, and
        # extra parametric filters risk excluding legitimate variants. We still don't
        # know which leaf the part belongs to, so probe every leaf (Mounting Type
        # filter only) and merge - a wrong-leaf guess 400s rather than erroring the
        # whole search, since each leaf is queried independently.
        keywords = part_number
        leaves = [(cat_id, mount_filter) for cat_id, _ in DIODE_ALL_LEAVES]
        products = _search_leaves(keywords, leaves, access_token, client_id, token_refresher)
    else:
        keywords = "diode"
        cat_id, has_tech = DIODE_TYPE_CATEGORIES.get(type_idx, (None, True))
        if cat_id is None:
            # "I don't care" - probe every leaf, applying the Technology filter only
            # to the leaves that actually support ParameterId 570.
            leaves = []
            for leaf_id, leaf_has_tech in DIODE_ALL_LEAVES:
                filters = list(mount_filter)
                if leaf_has_tech and tech_idx in DIODE_TECH_MAP:
                    filters.append({"ParameterId": 570, "FilterValues": [{"Id": DIODE_TECH_MAP[tech_idx]}]})
                leaves.append((leaf_id, filters))
            products = _search_leaves(keywords, leaves, access_token, client_id, token_refresher)
        else:
            # A specific Type leaf is known up front - single request, no probing needed.
            filters = list(mount_filter)
            if has_tech and tech_idx in DIODE_TECH_MAP:
                filters.append({"ParameterId": 570, "FilterValues": [{"Id": DIODE_TECH_MAP[tech_idx]}]})
            filter_req = {"CategoryFilter": {"id": str(cat_id)}, "ParameterFilters": filters}
            resp = _post_search(keywords, filter_req, 50, access_token, client_id)
            if resp.status_code == 401 and token_refresher:
                new_token = token_refresher()
                if new_token:
                    resp = _post_search(keywords, filter_req, 50, new_token, client_id)
            check_api_response(resp)
            products = resp.json().get("Products", []) if resp.status_code == 200 else []

    products = _dedupe_and_sort(products)

    if needs_pkg_filter:
        target_pkg = pkg_table[pkg_idx]

        def _pkg_matches(p):
            for param in p.get("Parameters", []):
                if param.get("ParameterId") == 16:
                    return normalize_package(param.get("ValueText", ""), smd) == target_pkg
            return False
        products = [p for p in products if _pkg_matches(p)]

    return {"Products": products, "ProductsCount": len(products)}
