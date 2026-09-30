import requests
import re
import concurrent.futures
try:
    from .DigikeyPartNumber import pick_digikey_pn
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn

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


def normalize_package(raw_text):
    """Returns a key into DIODE_STOCK_FOOTPRINTS, or None if unrecognized."""
    for tok in re.findall(r'DO-\d+[A-Z]*', raw_text or ""):
        tok = DIODE_PACKAGE_ALIASES.get(tok, tok)
        if tok in DIODE_STOCK_FOOTPRINTS:
            return tok
    return None


def process_diode(product_json):
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

    package = normalize_package(pkg_raw)
    if package:
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
        "sym_lib_name": "D_TH_emDashGameChanger",
        "fp_lib_name": "D_TH_emDashGameChanger",
        "fp_template": "footprintTemplates/TH_DiodeTemplate.kicad_mod",
        "sym_template": "symbolTemplates/DiodeSymbolTemplate.txt",
        "sym_preamble": '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "emDashGameChanger\'s diode generator")\n\t(generator_version "0.1")\n'
    }

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
    part_number = part_number.strip()
    mount_filter = [{"ParameterId": 69, "FilterValues": [{"Id": "411897"}]}]  # Through Hole
    needs_pkg_filter = pkg_idx in DIODE_PACKAGE_IDX

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
            products = resp.json().get("Products", []) if resp.status_code == 200 else []

    products = _dedupe_and_sort(products)

    if needs_pkg_filter:
        target_pkg = DIODE_PACKAGE_IDX[pkg_idx]

        def _pkg_matches(p):
            for param in p.get("Parameters", []):
                if param.get("ParameterId") == 16:
                    return normalize_package(param.get("ValueText", "")) == target_pkg
            return False
        products = [p for p in products if _pkg_matches(p)]

    return {"Products": products, "ProductsCount": len(products)}
