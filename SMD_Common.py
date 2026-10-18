"""Shared tables/helpers for the surface-mount generators (SMD_Resistors,
SMD_Capacitors). Every SMD part reuses a stock KiCad footprint by reference -
nothing here generates footprint files, it only picks the right stock name."""
import re
import requests
try:
    from .DigikeyPartNumber import check_api_response
except ImportError:
    from DigikeyPartNumber import check_api_response

URL = "https://api.digikey.com/products/v4/search/keyword"

# Mounting Type (ParameterId 69) ValueIds - confirmed against the live API.
SMD_MOUNT_IDS = ["409393", "409430"]   # Surface Mount, Surface Mount + Wettable Flank
MLCC_MOUNT_IDS = ["409416", "409417"]  # Surface Mount MLCC, MLCC Epoxy (ceramic caps only)

# Package / Case (ParameterId 16) ValueIds for EIA chip sizes - shared by chip
# resistors and MLCCs (same text, same id in both categories).
CHIP_PACKAGE_VALUE_IDS = {
    "0201": "39078",
    "0402": "39158",
    "0603": "39246",
    "0805": "39329",
    "1206": "83711",
    "1210": "84460",
    "1812": "114786",
    "2010": "140956",
    "2220": "148110",
    "2512": "735156",
}

# EIA size -> (stock name, HandSolder variant). The pad dimensions baked into
# the HandSolder names differ per size AND per lib, so they're listed rather
# than built from a pattern (tests/test_smd_footprints.py checks they exist).
CHIP_FOOTPRINTS = {
    "R": ("Resistor_SMD", {
        "0201": ("R_0201_0603Metric", "R_0201_0603Metric_Pad0.64x0.40mm_HandSolder"),
        "0402": ("R_0402_1005Metric", "R_0402_1005Metric_Pad0.72x0.64mm_HandSolder"),
        "0603": ("R_0603_1608Metric", "R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"),
        "0805": ("R_0805_2012Metric", "R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"),
        "1206": ("R_1206_3216Metric", "R_1206_3216Metric_Pad1.30x1.75mm_HandSolder"),
        "1210": ("R_1210_3225Metric", "R_1210_3225Metric_Pad1.30x2.65mm_HandSolder"),
        "1812": ("R_1812_4532Metric", "R_1812_4532Metric_Pad1.30x3.40mm_HandSolder"),
        "2010": ("R_2010_5025Metric", "R_2010_5025Metric_Pad1.40x2.65mm_HandSolder"),
        "2512": ("R_2512_6332Metric", "R_2512_6332Metric_Pad1.40x3.35mm_HandSolder"),
    }),
    "C": ("Capacitor_SMD", {
        "0201": ("C_0201_0603Metric", "C_0201_0603Metric_Pad0.64x0.40mm_HandSolder"),
        "0402": ("C_0402_1005Metric", "C_0402_1005Metric_Pad0.74x0.62mm_HandSolder"),
        "0603": ("C_0603_1608Metric", "C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"),
        "0805": ("C_0805_2012Metric", "C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"),
        "1206": ("C_1206_3216Metric", "C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"),
        "1210": ("C_1210_3225Metric", "C_1210_3225Metric_Pad1.33x2.70mm_HandSolder"),
        "1812": ("C_1812_4532Metric", "C_1812_4532Metric_Pad1.57x3.40mm_HandSolder"),
        "2220": ("C_2220_5750Metric", "C_2220_5750Metric_Pad1.97x5.40mm_HandSolder"),
    }),
}

# Molded tantalum: EIA metric code -> [(Kemet case letter, body height mm)],
# straight from the stock Capacitor_Tantalum_SMD names
# (CP_EIA-<metric>-<height*10>_Kemet-<letter>).
TANTALUM_CASES = {
    "2012": [("R", 1.2)],
    "3216": [("I", 1.0), ("S", 1.2), ("A", 1.8)],
    "3528": [("T", 1.2), ("B", 2.1)],
    "6032": [("U", 1.5), ("C", 2.8)],
    "7343": [("W", 1.5), ("V", 2.0), ("D", 3.1), ("Y", 4.0), ("X", 4.3)],
    "7360": [("E", 3.8)],
}
TANTALUM_FP_LIB = "Capacitor_Tantalum_SMD"
# The "standard" (full-height) case letter per metric code - the fallback when
# neither the size code nor the height pins down a variant.
TANTALUM_STANDARD_CASE = {"2012": "R", "3216": "A", "3528": "B", "6032": "C", "7343": "D", "7360": "E"}

# Package / Case ValueIds in the Tantalum leaf (59) for the standard molded cases.
TANTALUM_PACKAGE_VALUE_IDS = {
    "3216": ["83711"],             # 1206 (3216 Metric) - case A
    "3528": ["94862", "94863"],    # 1411 (3528 Metric) [, 1210] - case B
    "6032": ["150796"],            # 2312 (6032 Metric) - case C
    "7343": ["166804"],            # 2917 (7343 Metric) - case D
    "7360": ["166868"],            # 2924 (7360 Metric) - case E
}

# Stock SMD aluminum electrolytic can footprints (Capacitor_SMD:CP_Elec_<D>x<H>),
# as (diameter mm, height mm). Vendor-specific variants (_Nichicon, CAP-XX) are
# deliberately left out.
ALUM_CAN_SIZES = [
    (3.0, 5.3), (3.0, 5.4),
    (4.0, 3.0), (4.0, 3.9), (4.0, 4.5), (4.0, 5.3), (4.0, 5.4), (4.0, 5.7), (4.0, 5.8),
    (5.0, 3.0), (5.0, 3.9), (5.0, 4.4), (5.0, 4.5), (5.0, 5.3), (5.0, 5.4), (5.0, 5.7),
    (5.0, 5.8), (5.0, 5.9),
    (6.3, 3.0), (6.3, 3.9), (6.3, 4.5), (6.3, 4.9), (6.3, 5.2), (6.3, 5.3), (6.3, 5.4),
    (6.3, 5.7), (6.3, 5.8), (6.3, 5.9), (6.3, 7.7), (6.3, 9.9),
    (8.0, 5.4), (8.0, 6.2), (8.0, 6.5), (8.0, 6.7), (8.0, 6.9), (8.0, 10.0), (8.0, 10.5),
    (8.0, 11.9),
    (10.0, 7.7), (10.0, 7.9), (10.0, 10.0), (10.0, 10.5), (10.0, 12.5), (10.0, 12.6),
    (10.0, 14.3),
    (16.0, 17.5), (16.0, 22.0),
    (18.0, 17.5), (18.0, 22.0),
]
ALUM_FP_LIB = "Capacitor_SMD"


def _fmt_mm(v):
    """6.3 -> "6.3", 10.0 -> "10" (KiCad's CP_Elec naming)."""
    return f"{v:g}"


def parse_mm(text):
    """First "<n>mm" value in a Digi-Key dimension string, e.g.
    '0.248" Dia (6.30mm)' -> 6.3. Returns None if none found."""
    m = re.search(r'([\d.]+)\s*mm', text or "")
    return float(m.group(1)) if m else None


def chip_size_from_package(raw_text):
    """'0603 (1608 Metric)' -> '0603'; None if it isn't a plain EIA chip size."""
    m = re.match(r'\s*(\d{4})\s*\(\d{4}\s*Metric\)', raw_text or "")
    return m.group(1) if m else None


def chip_footprint(prefix, size, handsolder=True):
    """('R'|'C', '0603', handsolder) -> 'Resistor_SMD:R_0603_1608Metric[...]',
    or None if KiCad has no stock footprint for that size."""
    lib, table = CHIP_FOOTPRINTS[prefix]
    entry = table.get(size)
    if not entry:
        return None
    return f"{lib}:{entry[1] if handsolder else entry[0]}"


def handsolder_suffix(footprint):
    """'_HS' when the footprint is a stock hand-solder pad variant, else ''.
    Symbol names otherwise don't encode the pad choice, so without this the
    hand-solder and standard variants of one part collide on dedup."""
    return "_HS" if "handsolder" in (footprint or "").lower() else ""


def tantalum_metric_code(raw_text):
    """'1411 (3528 Metric)' -> '3528'; None if not found."""
    m = re.search(r'\((\d{4})\s*Metric\)', raw_text or "")
    return m.group(1) if m else None


def tantalum_footprint(package_raw, height_mm=None, size_code=None, handsolder=True):
    """Picks a stock Kemet-style molded tantalum footprint from the product's
    Package/Case text (EIA metric code), preferring the manufacturer size code
    letter when it's one of that code's Kemet letters, else the shortest stock
    body at least as tall as the part, else the standard case. Returns
    (footprint 'Lib:Name', case letter) or (None, None)."""
    metric = tantalum_metric_code(package_raw)
    cases = TANTALUM_CASES.get(metric)
    if not cases:
        return None, None
    letter, height = None, None
    code = (size_code or "").strip().upper()
    for l, h in cases:
        if code == l:
            letter, height = l, h
            break
    if letter is None and height_mm is not None:
        taller = [(l, h) for l, h in cases if h + 0.05 >= height_mm]
        if taller:
            letter, height = min(taller, key=lambda c: c[1])
    if letter is None:
        letter, height = next(c for c in cases if c[0] == TANTALUM_STANDARD_CASE[metric])
    name = f"CP_EIA-{metric}-{int(round(height * 10)):02d}_Kemet-{letter}"
    if handsolder:
        name += "_HandSolder"
    return f"{TANTALUM_FP_LIB}:{name}", letter


def alum_footprint(diameter_mm, height_mm):
    """Nearest stock CP_Elec_<D>x<H> for an SMD aluminum can: same diameter
    (within 0.5mm), then the closest height (within 0.6mm). Returns
    (footprint 'Lib:Name', "<D>x<H>") or (None, None) when nothing is close
    enough - a mismatched can footprint is worse than no footprint."""
    if diameter_mm is None or height_mm is None:
        return None, None
    same_dia = [(d, h) for d, h in ALUM_CAN_SIZES if abs(d - diameter_mm) <= 0.5]
    if not same_dia:
        return None, None
    d, h = min(same_dia, key=lambda c: (abs(c[0] - diameter_mm), abs(c[1] - height_mm)))
    if abs(h - height_mm) > 0.6:
        return None, None
    size = f"{_fmt_mm(d)}x{_fmt_mm(h)}"
    return f"{ALUM_FP_LIB}:CP_Elec_{size}", size


def search_leaf(keywords, outer_cat, leaf_cat, filters, access_token, client_id, token_refresher=None):
    """Single keyword search scoped to one leaf category (retrying once on 401).
    Returns the decoded JSON - a non-200 response comes back without
    "Products", which callers treat as no results."""
    payload = {
        "Keywords": keywords,
        "Limit": 50,  # Digi-Key's hard cap
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MinimumOrderQuantity": 1,
            "CategoryFilter": [{"id": str(outer_cat)}],
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "ParameterFilterRequest": {
                "CategoryFilter": {"id": str(leaf_cat)},
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
    response = requests.post(URL, json=payload, headers=headers)
    if response.status_code == 401 and token_refresher:
        new_token = token_refresher()
        if new_token:
            headers["authorization"] = f"Bearer {new_token}"
            response = requests.post(URL, json=payload, headers=headers)
    check_api_response(response)
    return response.json()


def get_param(product_json, parameter_id, default="Unknown"):
    for p in product_json.get("Parameters", []):
        if p.get("ParameterId") == parameter_id:
            return p.get("ValueText", default)
    return default


def clean_symbol_token(text):
    """Text fragment -> something safe inside a KiCad symbol name (same style
    as the THT generators: "10kΩ", "1/10W", "1%", "100nF", "16V")."""
    text = text.replace("µ", "u").replace("±", "")
    return re.sub(r'[\s"():,;]', '', text)
