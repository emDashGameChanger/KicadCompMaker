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
