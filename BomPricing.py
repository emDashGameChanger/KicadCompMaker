"""Price a KiCad schematic's BOM against Digi-Key's current price breaks.

Collects every placed symbol that carries a Digi-Key part number (either the
"Digikey Part#" field our generators write, or the "Digi-Key_PN" field used by
Digi-Key's own KiCad library), groups them by part number, and fetches live
pricing for each. For every part it shows the cost at the quantity you need and
what each higher price break would cost in total - so you can see when buying
up to the next break is cheaper, the same, or only slightly more.

Every packaging of the product is compared (cut tape, bulk, reel, ...), and the
cheapest one that's in stock at the needed quantity is used. When that isn't
the part number in the schematic, the report says which one to order instead -
e.g. a Tape & Reel number with a 4000-piece minimum gets its Cut Tape twin.

--order writes a Digi-Key-ready order sheet (part number, quantity, refs) that
already takes every buy-up; --min-passive sets a floor on how many of each
resistor/capacitor value to order (spares, since they're cheap).

usage: python3 BomPricing.py <schematic.kicad_sch> [-n BOARDS] [--csv out.csv]
       [--order order.csv] [--min-passive 10]
       [--close-pct 10] [--close-abs 0.25] [--max-break 1000]
"""
import argparse
import concurrent.futures
import csv
import json
import os
import re
import sys
import time

import requests

DK_FIELDS = ("Digikey Part#", "Digi-Key_PN")
MPN_FIELDS = ("Manufacture Part#", "MPN")
SKIP_VALUES = {"", "~", "N/A", "n/a", "-"}

TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
DETAILS_URL = "https://api.digikey.com/products/v4/search/{}/productdetails"


# --- schematic parsing -------------------------------------------------------

def _block_end(t, i):
    """t[i] == '(' -> index just past the matching ')', honoring quoted strings."""
    depth, j, n = 0, i, len(t)
    while j < n:
        c = t[j]
        if c == '"':
            j += 1
            while t[j] != '"':
                j += 2 if t[j] == '\\' else 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError(f"unbalanced block at {i}")


def _props(block):
    return dict(re.findall(r'\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', block))


def _field(p, names):
    return next((p[f].strip() for f in names if p.get(f, "").strip() not in SKIP_VALUES), None)


def collect_bom(sch_path):
    """Returns ({dk_pn: {"refs": set, "mpn": str|None, "value": str}}, [refs in BOM with no DK PN]).

    Walks hierarchical sub-sheets (each file once). References come from each
    symbol's (instances ...) list, so a sheet placed several times contributes
    one ref per placement; multi-unit parts (e.g. a dual op-amp) count once.
    Symbols marked "exclude from BOM" or DNP are skipped."""
    parts, missing, seen_refs = {}, set(), set()
    todo, done = [os.path.abspath(sch_path)], set()
    while todo:
        path = todo.pop()
        if path in done:
            continue
        done.add(path)
        t = open(path, encoding="utf-8").read()
        for m in re.finditer(r'\n\t\(sheet\n', t):
            s = m.start() + 2
            p = _props(t[s:_block_end(t, s)])
            f = p.get("Sheetfile") or p.get("Sheet file")
            if f:
                todo.append(os.path.join(os.path.dirname(path), f))
        for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "[^"]+"\)', t):
            s = m.start() + 2
            blk = t[s:_block_end(t, s)]
            if "(in_bom no)" in blk or "(dnp yes)" in blk:
                continue
            p = _props(blk)
            refs = re.findall(r'\(reference "([^"]+)"\)', blk) or [p.get("Reference", "?")]
            dk = _field(p, DK_FIELDS)
            for r in refs:
                if r.startswith("#") or r in seen_refs:
                    continue  # power symbol, or another unit of a part already counted
                seen_refs.add(r)
                if dk:
                    e = parts.setdefault(dk, {"refs": set(), "mpn": None, "value": p.get("Value", "")})
                    e["refs"].add(r)
                    e["mpn"] = e["mpn"] or _field(p, MPN_FIELDS)
                else:
                    missing.add(r)
    return parts, sorted(missing, key=_ref_key)


def _ref_key(r):
    m = re.match(r'([A-Za-z_#]*)(\d*)', r)
    return (m.group(1), int(m.group(2) or 0), r)


# --- Digi-Key API ------------------------------------------------------------

def load_credentials():
    """Same lookup order as plugin.py: environment, then config.json beside this file."""
    cid, secret = os.environ.get("DIGIKEY_CLIENT_ID"), os.environ.get("DIGIKEY_CLIENT_SECRET")
    if cid and secret:
        return cid, secret
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
    if os.path.exists(path):
        c = json.load(open(path))
        if c.get("DIGIKEY_CLIENT_ID") and c.get("DIGIKEY_CLIENT_SECRET"):
            return c["DIGIKEY_CLIENT_ID"], c["DIGIKEY_CLIENT_SECRET"]
    sys.exit("No Digi-Key credentials: set DIGIKEY_CLIENT_ID/DIGIKEY_CLIENT_SECRET or fill config.json")


def get_token(client_id, client_secret):
    r = requests.post(TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret,
                                       "grant_type": "client_credentials"})
    r.raise_for_status()
    return r.json()["access_token"]


def _get_details(pn, headers, retries=7):
    url = DETAILS_URL.format(requests.utils.quote(pn, safe=""))
    for attempt in range(retries):
        r = requests.get(url, headers=headers)
        # Digi-Key's gateway reports its per-minute quota either as a plain 429
        # or as a 500 whose body says "SC-Quota ... ResponseCode 429".
        if r.status_code == 429 or (r.status_code == 500 and "Quota" in r.text):
            time.sleep(float(r.headers.get("Retry-After", 2 ** attempt)))  # up to ~2 min total
            continue
        if r.status_code == 404:
            return None, "not found on Digi-Key"
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:120]}"
        return r.json().get("Product"), None
    return None, "Digi-Key rate limit hit - try again in a few minutes"


def fetch_product(dk_pn, mpn, headers):
    """Returns (product_json, None) or (None, error). Falls back to the
    manufacturer part number when Digi-Key no longer knows the DK number."""
    product, err = _get_details(dk_pn, headers)
    if product is None and mpn and err == "not found on Digi-Key":
        product, _ = _get_details(mpn, headers)
        if product is None:
            err = f"not found on Digi-Key (by DK number or MPN {mpn})"
    return product, err if product is None else None


# --- pricing analysis --------------------------------------------------------

def cost_at(breaks, qty):
    """(order_qty, unit_price, total) for buying at least qty. The order qty is
    bumped up to the first break when qty is below it (minimum order)."""
    order = max(qty, breaks[0][0])
    unit = [p for q, p in breaks if q <= order][-1]
    return order, unit, round(order * unit, 2)


def pick_variation(dk_pn, product, need):
    """Chooses which packaging to price: the cheapest (at the needed qty) of the
    ones with enough stock, else the cheapest overall. Marketplace listings and
    variations without published pricing are ignored."""
    vs = []
    for v in product.get("ProductVariations", []):
        breaks = sorted((b["BreakQuantity"], b["UnitPrice"]) for b in v.get("StandardPricing") or [])
        if v.get("MarketPlace") or not breaks:
            continue
        order, unit, total = cost_at(breaks, need)
        vs.append({"use_dk": v["DigiKeyProductNumber"], "package": v.get("PackageType", {}).get("Name", ""),
                   "stock": v.get("QuantityAvailableforPackageType", 0), "breaks": breaks,
                   "order": order, "unit": unit, "total": total})
    if not vs:
        return None
    in_stock = [v for v in vs if v["stock"] >= v["order"]]
    best = min(in_stock or vs, key=lambda v: (v["total"], v["use_dk"].upper() != dk_pn.upper()))
    return best


def analyse(row, close_pct, close_abs, max_break):
    """Adds each higher break's total and its extra cost vs buying just what's needed."""
    total = row["total"]
    row["options"] = []
    for q, p in row["breaks"]:
        if q <= row["order"] or q > max(max_break, row["need"]):
            continue
        t = round(q * p, 2)
        extra = round(t - total, 2)
        if extra <= 0:
            verdict = "CHEAPER" if extra < 0 else "SAME"
        elif extra <= close_abs or (total and extra / total * 100 <= close_pct):
            verdict = "CLOSE"
        else:
            verdict = ""
        row["options"].append({"qty": q, "unit": p, "total": t, "extra": extra, "verdict": verdict})
    # the best buy-up is the largest break that's cheaper, the same, or close
    good = [o for o in row["options"] if o["verdict"]]
    row["suggest"] = good[-1] if good else None


def _is_passive(refs):
    """Fixed resistors and capacitors (R12, C3, C204A1) - not trimmers (RV), connectors, etc."""
    return all(re.match(r'[RC]\d', r) for r in refs)


def build_row(dk, entry, product, err, boards, close_pct, close_abs, max_break, min_passive=0):
    need = len(entry["refs"]) * boards
    if min_passive and _is_passive(entry["refs"]):
        need = max(need, min_passive)
    row = {"dk": dk, "refs": entry["refs"], "need": need, "mpn": entry["mpn"] or entry["value"], "mfr": "",
           "desc": "", "status": "", "problem": err, "suggest": None, "options": [], "breaks": []}
    if product is None:
        return row
    row.update(mpn=product.get("ManufacturerProductNumber", row["mpn"]),
               mfr=product.get("Manufacturer", {}).get("Name", ""),
               desc=product.get("Description", {}).get("ProductDescription", ""),
               status=product.get("ProductStatus", {}).get("Status", ""))
    v = pick_variation(dk, product, need)
    if v is None:
        row["problem"] = "no published pricing for any packaging"
        return row
    row.update(v)
    analyse(row, close_pct, close_abs, max_break)
    if row["order"] > max(need, max_break):
        row["problem"] = f"only sold {row['package']} with a {row['order']:,} minimum - pick another part"
    elif row["stock"] < row["order"]:
        row["problem"] = f"only {row['stock']:,} in stock"
    return row


# --- output ------------------------------------------------------------------

def _money(x):
    return f"${x:,.4f}".rstrip("0").rstrip(".") if x < 1 else f"${x:,.2f}"


def _signed(x):
    return f"{'+' if x >= 0 else '-'}${abs(x):.2f}"


def _refs_str(refs, width=60):
    s = ",".join(sorted(refs, key=_ref_key))
    return s if len(s) <= width else s[:width - 3] + "..."


def print_report(rows, missing, boards, close_pct, close_abs, show_breaks):
    print(f"Digi-Key pricing for {boards} board(s).  CLOSE = a higher price break costing at most "
          f"{close_pct:g}% or ${close_abs:.2f} more than the needed quantity.\n")
    for r in rows:
        print(f"{r['mpn'] or '?'}  [{r['dk']}]  {r['mfr']}")
        print(f"  {r['desc']}   refs: {_refs_str(r['refs'])}")
        if not r["breaks"]:
            print(f"  !! {r['problem']}\n")
            continue
        if r["use_dk"].upper() != r["dk"].upper():
            print(f"  >> order {r['use_dk']} ({r['package']}) instead of the schematic's {r['dk']}")
        notes = [n for n in (r["status"] if r["status"] != "Active" else "", r["problem"]) if n]
        print("  breaks: " + "  ".join(f"{q:,}@{_money(p)}" for q, p in r["breaks"]))
        bump = f" (min order {r['order']:,})" if r["order"] > r["need"] else ""
        print(f"  need {r['need']}{bump}: {r['order']:,} x {_money(r['unit'])} = ${r['total']:.2f}"
              + (f"   !! {'; '.join(notes)}" if notes else ""))
        for o in r["options"][:show_breaks]:
            pct = f", {o['extra'] / r['total'] * 100:+.0f}%" if r["total"] else ""
            flag = f"  <-- {o['verdict']}" if o["verdict"] else ""
            print(f"     buy {o['qty']:>6,}: ${o['total']:>8.2f}  ({_signed(o['extra'])}{pct}){flag}")
        print()

    ok = [r for r in rows if r["breaks"] and not r["problem"]]
    sugg = [r for r in ok if r["suggest"]]
    if sugg:
        print("Worth buying up:")
        for r in sugg:
            s = r["suggest"]
            print(f"  {r['mpn'][:22]:22s} need {r['need']:>4} -> buy {s['qty']:>5,}   "
                  f"${r['total']:.2f} -> ${s['total']:.2f}  ({s['verdict']}, {_signed(s['extra'])})")
        print()
    swaps = [r for r in rows if r["breaks"] and not r["problem"] and r["use_dk"].upper() != r["dk"].upper()]
    if swaps:
        print("Different Digi-Key number to order:")
        for r in swaps:
            print(f"  {r['mpn'][:22]:22s} {r['dk']:28s} -> {r['use_dk']} ({r['package']})")
        print()
    bad = [r for r in rows if r["problem"]]
    if bad:
        print("Problems (left out of the totals):")
        for r in bad:
            print(f"  {r['mpn'][:22]:22s} [{r['dk']}] {_refs_str(r['refs'], 30)}: {r['problem']}")
        print()
    total = sum(r["total"] for r in ok)
    print(f"Total at needed quantities ({len(ok)} parts):  ${total:,.2f}")
    if sugg:
        up = sum(r["suggest"]["total"] if r["suggest"] else r["total"] for r in ok)
        print(f"Total taking the buy-ups above:           ${up:,.2f}  ({_signed(up - total)})")
    if missing:
        print(f"\nIn BOM without a Digi-Key part number ({len(missing)}): {', '.join(missing)}")


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Refs", "Schematic DK PN", "Order DK PN", "Package", "MPN", "Manufacturer",
                    "Description", "Need", "Order Qty", "Unit", "Total", "Stock", "Status",
                    "Price Breaks", "Suggested Qty", "Suggested Total", "Suggested Extra",
                    "Verdict", "Problem"])
        for r in rows:
            s = r["suggest"] or {}
            w.writerow([" ".join(sorted(r["refs"], key=_ref_key)), r["dk"], r.get("use_dk", ""),
                        r.get("package", ""), r["mpn"], r["mfr"], r["desc"], r["need"],
                        r.get("order", ""), r.get("unit", ""), r.get("total", ""), r.get("stock", ""),
                        r["status"], " ".join(f"{q}@{p}" for q, p in r["breaks"]),
                        s.get("qty", ""), s.get("total", ""), s.get("extra", ""), s.get("verdict", ""),
                        r["problem"] or ""])


def write_order(path, rows):
    """Digi-Key order sheet: one line per part at the final quantity (buy-ups taken).
    Upload it at digikey.com -> BOM Manager / cart "Upload a file"."""
    ok = [r for r in rows if r["breaks"] and not r["problem"]]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Digi-Key Part Number", "Quantity", "Customer Reference",
                    "Manufacturer Part Number", "Unit Price", "Extended Price"])
        for r in ok:
            s = r["suggest"] or {"qty": r["order"], "unit": r["unit"], "total": r["total"]}
            w.writerow([r["use_dk"], s["qty"], " ".join(sorted(r["refs"], key=_ref_key)),
                        r["mpn"], s["unit"], f"{s['total']:.2f}"])
    return sum((r["suggest"] or r)["total"] for r in ok), len(ok)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("schematic", help="root .kicad_sch (sub-sheets are followed)")
    ap.add_argument("-n", "--boards", type=int, default=1, help="number of boards to build (default 1)")
    ap.add_argument("--close-pct", type=float, default=10.0,
                    help="flag a higher break as CLOSE if it costs at most this %% more (default 10)")
    ap.add_argument("--close-abs", type=float, default=0.25,
                    help="...or at most this many dollars more (default 0.25)")
    ap.add_argument("--max-break", type=int, default=1000,
                    help="ignore price breaks above this quantity (default 1000)")
    ap.add_argument("--show-breaks", type=int, default=3,
                    help="higher breaks to list per part (default 3)")
    ap.add_argument("--csv", help="also write the results to this CSV file")
    ap.add_argument("--order", help="write a Digi-Key order sheet (final quantities, buy-ups taken)")
    ap.add_argument("--min-passive", type=int, default=0,
                    help="order at least this many of each resistor/capacitor value (default 0 = only what's needed)")
    ap.add_argument("-j", "--workers", type=int, default=5, help="parallel API requests (default 5)")
    a = ap.parse_args()

    parts, missing = collect_bom(a.schematic)
    if not parts:
        sys.exit("No symbols with a Digi-Key part number found.")
    cid, secret = load_credentials()
    headers = {"X-DIGIKEY-Client-Id": cid, "authorization": f"Bearer {get_token(cid, secret)}",
               "X-DIGIKEY-Locale-Currency": "USD"}

    with concurrent.futures.ThreadPoolExecutor(a.workers) as ex:
        fetched = dict(zip(parts, ex.map(lambda pn: fetch_product(pn, parts[pn]["mpn"], headers), parts)))

    rows = [build_row(dk, e, *fetched[dk], a.boards, a.close_pct, a.close_abs, a.max_break,
                      a.min_passive)
            for dk, e in parts.items()]
    rows.sort(key=lambda r: _ref_key(min(r["refs"], key=_ref_key)))

    print_report(rows, missing, a.boards, a.close_pct, a.close_abs, a.show_breaks)
    if a.csv:
        write_csv(a.csv, rows)
        print(f"\nCSV written to {a.csv}")
    if a.order:
        total, n = write_order(a.order, rows)
        print(f"\nOrder sheet written to {a.order}: {n} lines, ${total:,.2f}")
        bad = [r for r in rows if r["problem"]]
        if bad:
            print(f"  left out (see Problems above): {', '.join(r['mpn'] or r['dk'] for r in bad)}")


if __name__ == "__main__":
    main()
