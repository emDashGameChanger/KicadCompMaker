import os
import re
import requests
import wx
try:
    from .DigikeyPartNumber import pick_digikey_pn
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn

# Stock KiCad THT transistor footprint library. Package/Case text (ParameterId 16)
# -> list of candidate stock footprint names in that library. A package family maps
# to more than one entry when KiCad ships multiple mechanically-different stock
# variants for it (e.g. TO-220-3 Vertical vs Horizontal_TabDown vs Horizontal_TabUp) -
# those aren't interchangeable, so an exact match is only auto-resolved when the list
# has exactly one candidate; otherwise a human must pick (see gui.PinoutConfirmDialog).
TRANSISTOR_STOCK_FOOTPRINTS = {
    "TO-92":  ["TO-92", "TO-92_Wide", "TO-92_Inline", "TO-92L"],
    "TO-18":  ["TO-18-3", "TO-18-3_Window"],
    "TO-39":  ["TO-39-3", "TO-39-3_Window"],
    "TO-220": ["TO-220-3_Vertical", "TO-220-3_Horizontal_TabDown", "TO-220-3_Horizontal_TabUp"],
    "TO-126": ["TO-126-3_Vertical", "TO-126-3_Horizontal_TabDown", "TO-126-3_Horizontal_TabUp"],
    "TO-247": ["TO-247-3_Vertical", "TO-247-3_Horizontal_TabDown", "TO-247-3_Horizontal_TabUp"],
    "TO-251": ["TO-251-3_Vertical", "TO-251-3-1EP_Horizontal_TabDown"],
}

# Alternate JEDEC/vendor names Digikey's "Package / Case" text uses for the same
# physical package as one of the keys above.
TRANSISTOR_PACKAGE_ALIASES = {
    "TO-226":   "TO-92",
    "TO-226AA": "TO-92",
    "TO-205":   "TO-39",
    "TO-205AD": "TO-39",
}

STOCK_FP_LIB = "Package_TO_SOT_THT"  # KiCad's own stock footprint library nickname
STOCK_FP_DIR = "/usr/share/kicad/footprints/Package_TO_SOT_THT.pretty"

# GUI Package selector idx -> normalized package family key
TRANSISTOR_PACKAGE_IDX = {
    1: "TO-92",
    2: "TO-18",
    3: "TO-39",
    4: "TO-220",
    5: "TO-126",
    6: "TO-247",
}

URL = "https://api.digikey.com/products/v4/search/keyword"


def normalize_package_family(raw_text):
    """Extracts a TO-\\d+/SOT-\\d+ family token from Digikey's free-text
    Package/Case value, resolving known aliases (e.g. TO-226AA -> TO-92).
    Returns None if nothing recognizable is found."""
    for tok in re.findall(r'(?:TO|SOT)-\d+[A-Z]*', raw_text or ""):
        tok = TRANSISTOR_PACKAGE_ALIASES.get(tok, tok)
        base_match = re.match(r'((?:TO|SOT)-\d+)', tok)
        base = base_match.group(1) if base_match else tok
        if base in TRANSISTOR_STOCK_FOOTPRINTS:
            return base
    return None


def match_stock_footprint(raw_text):
    """Returns {"footprint": str|None, "candidates": [names]}. A single
    unambiguous candidate is auto-resolved (footprint == candidates[0]); zero or
    multiple candidates mean a human must disambiguate before generation."""
    family = normalize_package_family(raw_text)
    if family:
        candidates = list(TRANSISTOR_STOCK_FOOTPRINTS.get(family, []))
    else:
        # Generic fallback for families we haven't curated: list whatever stock
        # footprints share the same "TO-<n>-" prefix, straight off disk, so
        # coverage isn't capped by this file's hand-picked entries.
        m = re.search(r'((?:TO|SOT)-\d+)-', raw_text or "")
        candidates = []
        if m:
            prefix = m.group(1) + "-"
            try:
                candidates = sorted(
                    f[:-len(".kicad_mod")] for f in os.listdir(STOCK_FP_DIR)
                    if f.startswith(prefix) and f.endswith(".kicad_mod")
                )
            except OSError:
                candidates = []

    if len(candidates) == 1:
        return {"footprint": candidates[0], "candidates": candidates}
    return {"footprint": None, "candidates": candidates}


def _sexp_parse(text):
    """Minimal S-expression parser for .kicad_mod files - just enough to walk
    pad/fp_line/fp_arc/fp_rect blocks, not a general KiCad file writer/editor."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    pos = [0]

    def parse():
        pos[0] += 1  # consume '('
        lst = []
        while tokens[pos[0]] != ')':
            if tokens[pos[0]] == '(':
                lst.append(parse())
            else:
                tok = tokens[pos[0]]
                if tok.startswith('"') and tok.endswith('"'):
                    tok = tok[1:-1]
                lst.append(tok)
                pos[0] += 1
        pos[0] += 1  # consume ')'
        return lst

    return parse()


def parse_footprint_geometry(footprint_name, fp_dir=STOCK_FP_DIR):
    """Parses a stock .kicad_mod file down to just what's needed to draw a pin-
    numbering preview: pad centers/numbers and F.Fab outline lines/arcs/rects.
    Returns {"pads": [{"number","x","y"}], "outline": [{"type",...}]}."""
    path = os.path.join(fp_dir, footprint_name + ".kicad_mod")
    with open(path) as f:
        tree = _sexp_parse(f.read())

    pads = []
    outline = []

    def walk(node):
        if not isinstance(node, list) or not node:
            return
        tag = node[0]
        if tag == "pad" and len(node) > 1:
            at = next((n for n in node if isinstance(n, list) and n and n[0] == "at"), None)
            if at:
                pads.append({"number": node[1], "x": float(at[1]), "y": float(at[2])})
        elif tag in ("fp_line", "fp_arc", "fp_rect", "fp_circle"):
            layer = next((n[1] for n in node if isinstance(n, list) and n and n[0] == "layer"), None)
            if layer == "F.Fab":
                shape = {"type": tag}
                for n in node:
                    if isinstance(n, list) and n and n[0] in ("start", "end", "mid", "center"):
                        shape[n[0]] = (float(n[1]), float(n[2]))
                    elif isinstance(n, list) and n and n[0] == "radius":
                        shape["radius"] = float(n[1])
                outline.append(shape)
        for child in node:
            if isinstance(child, list):
                walk(child)

    walk(tree)
    return {"pads": pads, "outline": outline}


def render_footprint_preview(footprint_name, size=(260, 200), fp_dir=STOCK_FP_DIR):
    """Renders a rough top-down diagram of a stock footprint's pad numbering -
    not an actual KiCad render, just pad positions/numbers plus its F.Fab
    outline, scaled to fit. Purpose is narrow: let a human visually compare
    'which physical pin is #1/2/3 in KiCad' against a datasheet's own pictorial
    pinout diagram, since the datasheet virtually never states it as text.
    Returns a wx.Bitmap, or None if the footprint file can't be parsed."""
    try:
        geo = parse_footprint_geometry(footprint_name, fp_dir)
    except (OSError, IndexError, ValueError):
        return None
    pads = geo["pads"]
    if not pads:
        return None

    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    for shape in geo["outline"]:
        for key in ("start", "end", "mid", "center"):
            if key in shape:
                xs.append(shape[key][0])
                ys.append(shape[key][1])
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    margin_mm = 2.5
    span_x = max(max_x - min_x, 1.0) + margin_mm * 2
    span_y = max(max_y - min_y, 1.0) + margin_mm * 2

    w, h = size
    scale = min((w - 20) / span_x, (h - 20) / span_y)

    def to_px(pt):
        x, y = pt
        return ((x - min_x + margin_mm) * scale + 10, (y - min_y + margin_mm) * scale + 10)

    bmp = wx.Bitmap(w, h)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(255, 255, 255)))
    dc.Clear()

    dc.SetPen(wx.Pen(wx.Colour(130, 130, 130), 1))
    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    for shape in geo["outline"]:
        t = shape["type"]
        if t == "fp_rect" and "start" in shape and "end" in shape:
            (x1, y1), (x2, y2) = to_px(shape["start"]), to_px(shape["end"])
            dc.DrawRectangle(int(min(x1, x2)), int(min(y1, y2)), int(abs(x2 - x1)), int(abs(y2 - y1)))
        elif t == "fp_line" and "start" in shape and "end" in shape:
            (x1, y1), (x2, y2) = to_px(shape["start"]), to_px(shape["end"])
            dc.DrawLine(int(x1), int(y1), int(x2), int(y2))
        elif t == "fp_arc" and all(k in shape for k in ("start", "mid", "end")):
            p1, p2, p3 = to_px(shape["start"]), to_px(shape["mid"]), to_px(shape["end"])
            dc.DrawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            dc.DrawLine(int(p2[0]), int(p2[1]), int(p3[0]), int(p3[1]))
        elif t == "fp_circle" and "center" in shape and "radius" in shape:
            cx, cy = to_px(shape["center"])
            dc.DrawCircle(int(cx), int(cy), max(1, int(shape["radius"] * scale)))

    dc.SetPen(wx.Pen(wx.Colour(0, 0, 0), 2))
    dc.SetBrush(wx.Brush(wx.Colour(255, 214, 130)))
    dc.SetFont(wx.Font(9, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    r_px = max(5, int(0.9 * scale))
    for pad in pads:
        px, py = to_px((pad["x"], pad["y"]))
        dc.DrawCircle(int(px), int(py), r_px)
        label = pad["number"]
        tw, th = dc.GetTextExtent(label)
        dc.DrawText(label, int(px - tw / 2), int(py - th / 2))

    dc.SelectObject(wx.NullBitmap)
    return bmp


def build_payload(keywords, filter_req, limit):
    return {
        "Keywords": keywords,
        "Limit": limit,
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MinimumOrderQuantity": 1,
            "CategoryFilter": [{"id": "2045"}],  # Transistors - broad outer filter, OK to be non-leaf
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "ParameterFilterRequest": filter_req,
            "SearchOptions": ["NormallyStocking"]
        },
        "ExcludedContent": ["FilterOptions"],
        "SortOptions": {"Field": "Price", "SortOrder": "Ascending"}
    }


def post_search(keywords, filter_req, limit, access_token, client_id):
    headers = {
        "x-digikey-client-id": client_id,
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}"
    }
    return requests.post(URL, json=build_payload(keywords, filter_req, limit), headers=headers)


def search_leaf(keywords, category_id, filters, limit, access_token, client_id, token_refresher):
    """Query a single known leaf category, retrying once on 401."""
    filter_req = {"CategoryFilter": {"id": str(category_id)}, "ParameterFilters": filters}
    resp = post_search(keywords, filter_req, limit, access_token, client_id)
    if resp.status_code == 401 and token_refresher:
        new_token = token_refresher()
        if new_token:
            resp = post_search(keywords, filter_req, limit, new_token, client_id)
    return resp.json().get("Products", []) if resp.status_code == 200 else []


def dedupe_and_sort(products):
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


def filter_by_package(products, target_family):
    def _matches(p):
        for param in p.get("Parameters", []):
            if param.get("ParameterId") == 16:
                return normalize_package_family(param.get("ValueText", "")) == target_family
        return False
    return [p for p in products if _matches(p)]


def digikey_pn(product_json):
    """Shared DigiKeyProductNumber resolution - see DigikeyPartNumber.pick_digikey_pn."""
    return pick_digikey_pn(product_json)


def get_param(params, parameter_id, default="Unknown"):
    for p in params:
        if p.get("ParameterId") == parameter_id:
            return p.get("ValueText", default)
    return default
