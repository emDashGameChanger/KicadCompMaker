import re

# Digi-Key's real "Voltage - Rated" parameter is ParameterId 14 - the codebase
# previously used ParameterId 2079 everywhere (wrong id, matches nothing).
# Confirmed by querying the live Digi-Key v4 Product Search API directly
# (ceramic disc/film capacitor category, for 10nF and 10pF keyword searches).
# ValueId is Digi-Key's opaque internal code for that ParameterId 14 entry -
# FilterValues need this code, not the display text ("50V" etc won't match).
#
# Add more entries here if confirmed against the live API (e.g. the low-voltage
# 6.3V/10V/16V/63V ratings relevant to aluminum electrolytics weren't in the
# disc/film-range query that produced this table). Anything not in this table
# still works correctly via the client-side filtering fallback in the search
# functions - it's just less precise/efficient than a direct server-side filter.
VOLTAGE_VALUE_IDS = {
    "25V": "159247",
    "50V": "238738",
    "100V": "69629",
    "200V": "140848",
    "250V": "157291",
    "250VAC": "157312",
    "300VAC": "182808",
    "300VAC/440VAC": "482845",
    "400VAC": "213869",
    "440VAC": "219853",
    "450V": "221502",
    "500V": "237347",
    "500VAC": "237366",
    "630V": "260046",
    "760VAC": "278549",
    "1000V (1kV)": "68384",
    "1500V (1.5kV)": "99951",
    "2000V (2kV)": "140144",
    "3000V (3kV)": "182075",
    "6000V (6kV)": "255787",
}

_VOLTAGE_PATTERN = re.compile(r'([\d.]+)\s*(k?)\s*v', re.IGNORECASE)

# Numeric-volts -> ValueId, built from the plain "NV"/"N V (NkV)" entries above
# (skips the "...VAC" variants, which aren't reachable from the current GUI's
# plain-voltage options and would collide on the same leading number as their
# DC counterparts, e.g. 250V vs 250VAC).
_NUMERIC_TO_VALUE_ID = {}
for _name, _value_id in VOLTAGE_VALUE_IDS.items():
    if 'AC' in _name:
        continue
    _match = _VOLTAGE_PATTERN.match(_name)
    if _match:
        _num = float(_match.group(1))
        if _match.group(2):  # 'k' multiplier, e.g. "1000V (1kV)" - already plain volts
            pass
        _NUMERIC_TO_VALUE_ID[_num] = _value_id


def parse_voltage_volts(s):
    """Parses a voltage string ("50v", "6.3v", "1kV", "2kV", a Digi-Key
    ValueText like "50V", etc.) to a canonical float number of volts.
    Returns None if nothing numeric could be parsed."""
    if not s:
        return None
    match = _VOLTAGE_PATTERN.search(s.strip())
    if not match:
        return None
    val = float(match.group(1))
    if match.group(2):  # 'k' multiplier ("1kV" -> 1000)
        val *= 1000
    return val


def lookup_value_id(volts):
    """Numeric volts -> Digi-Key ValueId for ParameterId 14, or None if this
    voltage hasn't been confirmed against the live API yet."""
    if volts is None:
        return None
    return _NUMERIC_TO_VALUE_ID.get(volts)
