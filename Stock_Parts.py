"""Generic "any part by exact MPN" generator (batch type `part`): ICs, LEDs,
trimmers - anything with a fitting stock KiCad symbol and footprint. The
caller names both (symbol=Lib:Name, footprint=Lib:Name); Digi-Key supplies
the price / DK part# / datasheet, and the stock symbol is copied into
Parts_emDashGameChanger with those properties filled in."""
import os
import re
import requests

try:
    from .DigikeyPartNumber import pick_digikey_pn, check_api_response
    from .SMD_Common import URL, handsolder_suffix
except ImportError:
    from DigikeyPartNumber import pick_digikey_pn, check_api_response
    from SMD_Common import URL, handsolder_suffix

STOCK_SYMBOL_DIR = "/usr/share/kicad/symbols"
STOCK_FOOTPRINT_DIR = "/usr/share/kicad/footprints"
PARTS_LIB = "Parts_emDashGameChanger"


# --- minimal S-expression reader/writer (enough for .kicad_sym) --------------

class Q(str):
    """A quoted string atom (vs. a bare one like `yes` or `1.27`)."""


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse_sexpr(text):
    stack, cur = [], []
    for m in _TOKEN.finditer(text):
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done, cur = cur, stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            cur.append(Q(re.sub(r'\\(.)', r'\1', m.group(3))))
        elif m.group(4):
            cur.append(m.group(4))
    return cur[0]


def _atom(a):
    if isinstance(a, Q):
        return '"' + a.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return a


def write_sexpr(node, indent=1):
    if not any(isinstance(c, list) for c in node):
        return "\t" * indent + "(" + " ".join(_atom(c) for c in node) + ")"
    head = []
    for c in node:
        if isinstance(c, list):
            break
        head.append(_atom(c))
    lines = ["\t" * indent + "(" + " ".join(head)]
    for c in node[len(head):]:
        lines.append(write_sexpr(c, indent + 1) if isinstance(c, list) else "\t" * (indent + 1) + _atom(c))
    lines.append("\t" * indent + ")")
    return "\n".join(lines)


# --- stock symbol lookup -----------------------------------------------------

def _symbols(lib):
    path = os.path.join(STOCK_SYMBOL_DIR, f"{lib}.kicad_sym")
    if not os.path.exists(path):
        raise ValueError(f"No stock symbol library '{lib}'")
    with open(path, encoding="utf-8") as f:
        root = parse_sexpr(f.read())
    return {n[1]: n for n in root if isinstance(n, list) and n and n[0] == "symbol"}


def _child(node, key):
    return next((c for c in node if isinstance(c, list) and c and c[0] == key), None)


def _flatten(symbols, name):
    """Returns a copy of symbol `name`, with any (extends "Parent") resolved
    into the parent's graphics/pins plus this symbol's own properties - a
    derived symbol can't be copied on its own into another library."""
    if name not in symbols:
        raise ValueError(f"No stock symbol '{name}'")
    node = symbols[name]
    ext = _child(node, "extends")
    if not ext:
        return _deepcopy(node)
    base = _flatten(symbols, ext[1])
    parent = base[1]
    own = {c[1]: c for c in node if isinstance(c, list) and c[0] == "property"}
    out = []
    for c in base:
        if isinstance(c, list) and c[0] == "property":
            out.append(_deepcopy(own.pop(c[1], c)))
        elif isinstance(c, list) and c[0] == "symbol":
            sub = _deepcopy(c)
            sub[1] = Q(name + sub[1][len(parent):])
            out.append(sub)
        else:
            out.append(c)
    # properties only the derived symbol has go after the inherited ones
    last = max(i for i, c in enumerate(out) if isinstance(c, list) and c[0] == "property")
    out[last + 1:last + 1] = [_deepcopy(p) for p in own.values()]
    out[1] = Q(name)
    return out


def _deepcopy(node):
    return [_deepcopy(c) if isinstance(c, list) else c for c in node]


def copy_stock_symbol(lib_name, new_name, properties):
    """Stock symbol 'Lib:Name' -> .kicad_sym text for one top-level symbol
    named new_name, with `properties` (dict, ordered) set/added - new ones
    hidden, like the template-generated symbols."""
    lib, _, name = lib_name.partition(":")
    sym = _flatten(_symbols(lib), name)
    old = sym[1]
    sym[1] = Q(new_name)
    for c in sym:
        if isinstance(c, list) and c[0] == "symbol":
            c[1] = Q(new_name + c[1][len(old):])
    props = [c for c in sym if isinstance(c, list) and c[0] == "property"]
    by_key = {p[1]: p for p in props}
    insert_at = sym.index(props[-1]) + 1
    for key, value in properties.items():
        if key in by_key:
            by_key[key][2] = Q(value)
        else:
            sym.insert(insert_at, ["property", Q(key), Q(value), ["at", "0", "0", "0"],
                                   ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]])
            insert_at += 1
    return write_sexpr(sym)


def stock_footprint_exists(footprint):
    lib, _, name = footprint.partition(":")
    return os.path.exists(os.path.join(STOCK_FOOTPRINT_DIR, f"{lib}.pretty", f"{name}.kicad_mod"))


def stock_symbol_exists(symbol):
    lib, _, name = symbol.partition(":")
    try:
        return name in _symbols(lib)
    except ValueError:
        return False


# --- Digi-Key search / processing --------------------------------------------

def _norm_pn(pn):
    return re.sub(r'[^A-Z0-9]', '', (pn or "").upper())


def search_part(part_number, access_token, client_id, token_refresher=None):
    """Keyword search for one manufacturer part number. Products whose MPN is
    exactly part_number come first, then ones that merely start with it
    (packaging suffixes, e.g. /NOPB); everything else is dropped."""
    payload = {
        "Keywords": part_number,
        "Limit": 50,
        "Offset": 0,
        "MinimumQuantityAvailable": 1,
        "FilterOptionsRequest": {
            "MarketPlaceFilter": "ExcludeMarketPlace",
            "SearchOptions": ["NormallyStocking"],
        },
        "ExcludedContent": ["FilterOptions"],
        "SortOptions": {"Field": "Price", "SortOrder": "Ascending"},
    }
    headers = {
        "x-digikey-client-id": client_id,
        "content-type": "application/json",
        "authorization": f"Bearer {access_token}",
    }
    response = requests.post(URL, json=payload, headers=headers)
    if response.status_code == 401 and token_refresher:
        new_token = token_refresher()
        if new_token:
            headers["authorization"] = f"Bearer {new_token}"
            response = requests.post(URL, json=payload, headers=headers)
    check_api_response(response)
    results = response.json()
    want = _norm_pn(part_number)
    products = results.get("Products") or []
    exact = [p for p in products if _norm_pn(p.get("ManufacturerProductNumber")) == want]
    prefix = [p for p in products if p not in exact
              and _norm_pn(p.get("ManufacturerProductNumber")).startswith(want)]
    results["Products"] = exact + prefix
    results["ProductsCount"] = len(results["Products"])
    return results


def process_part(product_json, lib_config):
    """lib_config: {'symbol': 'Lib:Name', 'footprint': 'Lib:Name'}."""
    mpn = product_json.get("ManufacturerProductNumber", "Unknown")
    datasheet = product_json.get("DatasheetUrl", "")
    price = product_json.get("UnitPrice", 999.99)
    dk_pn = pick_digikey_pn(product_json)
    description = (product_json.get("Description") or {}).get("ProductDescription", "")
    footprint = lib_config["footprint"]

    symbol_name = re.sub(r'[^A-Za-z0-9_.-]', '_', mpn) + handsolder_suffix(footprint)
    processed_data = {
        "Symbol Data": {
            "symbol": symbol_name,
            "value": mpn,
            "footprint": footprint,
            "datasheet": datasheet,
            "dkPart": dk_pn,
            "mfrPart": mpn,
            "price": price,
        },
        "Footprint Data": {},
        "footprint_name": None,
        "skip_footprint_gen": True,
        "sym_lib_name": PARTS_LIB,
        "fp_lib_name": PARTS_LIB,
        "fp_template": None,
    }
    properties = {"Value": mpn, "Footprint": footprint}
    if datasheet:
        properties["Datasheet"] = datasheet
    if description:
        properties["Description"] = description
    properties.update({"Price": str(price), "Digikey Part#": dk_pn, "Manufacture Part#": mpn})
    try:
        processed_data["sym_text"] = copy_stock_symbol(lib_config["symbol"], symbol_name, properties)
    except (ValueError, OSError) as e:
        processed_data["error"] = str(e)
    return processed_data
