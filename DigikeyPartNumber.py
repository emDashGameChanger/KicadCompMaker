def pick_digikey_pn(product_json):
    """Picks the DigiKeyProductNumber from a product's ProductVariations.

    Prefers the lowest minimum order quantity (full reels are often 1000s -
    e.g. a reel-only BC1092TR-ND with a 60k MOQ), then CutTape (PackageType
    Id 2) on a tie. A variation with an unknown MOQ sorts last. Returns
    "N/A" if no variation has a part number."""
    variations = product_json.get("ProductVariations", [])
    orderable = sorted(
        (v for v in variations if v.get("DigiKeyProductNumber")),
        key=lambda v: (v.get("MinimumOrderQuantity") or float("inf"),
                       v.get("PackageType", {}).get("Id") != 2))
    if orderable:
        return orderable[0].get("DigiKeyProductNumber")
    return "N/A"


def check_api_response(response):
    """Raises on a Digi-Key quota/server failure (429, or a 5xx such as the
    500 "SC-Quota ... ResponseCode 429" fault) so callers report it as an API
    error instead of silently treating the empty body as "no results"."""
    if response.status_code == 429 or response.status_code >= 500:
        try:
            detail = response.json().get("fault", {}).get("faultstring") or response.text
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Digi-Key API error {response.status_code}: {detail[:200]}")
