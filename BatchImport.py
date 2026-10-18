import shlex
import concurrent.futures
from dataclasses import dataclass, field

try:
    from .gui import (RES_COMP_OPTS, RES_PWR_OPTS, RES_TOL_OPTS,
                      CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS,
                      CAP_FILM_TYPE_OPTS, CAP_FILM_VOL_OPTS,
                      DIODE_TYPE_RADIO_OPTS, DIODE_TYPE_PICK_OPTS, DIODE_TECH_OPTS, DIODE_PKG_OPTS,
                      TRANSISTOR_PKG_OPTS, BJT_POLARITY_OPTS, FET_POLARITY_OPTS,
                      SMD_RES_SIZE_OPTS, SMD_RES_TOL_OPTS, SMD_RES_PWR_OPTS,
                      SMD_CAP_SIZE_OPTS, SMD_CAP_VOL_OPTS, SMD_CAP_DIELECTRIC_OPTS,
                      SMD_TANT_CASE_OPTS, SMD_DIODE_PKG_OPTS, SMD_TRANSISTOR_PKG_OPTS,
                      SMD_RES_SIZE_DEFAULT, SMD_RES_TOL_DEFAULT, SMD_CAP_SIZE_DEFAULT)
    from .TH_Resistors import search_tht_resistor, process_resistor
    from .TH_Radial_ElectrolyticCapacitors import search_tht_capacitor, process_capacitor
    from .TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor
    from .TH_Diodes import search_diode, process_diode
    from .TH_Transistors_BJT import search_tht_bjt, process_bjt
    from .TH_Transistors_JFET import search_tht_jfet, process_jfet
    from .TH_Transistors_MOSFET import search_tht_mosfet, process_mosfet
    from .TH_Transistor_Common import apply_pinout
    from .SMD_Resistors import search_smd_resistor, process_smd_resistor
    from .SMD_Capacitors import (search_smd_mlcc, process_smd_mlcc, search_smd_tantalum,
                                    process_smd_tantalum, search_smd_aluminum, process_smd_aluminum)
    from .Stock_Parts import search_part, process_part, stock_symbol_exists, stock_footprint_exists
except ImportError:
    from gui import (RES_COMP_OPTS, RES_PWR_OPTS, RES_TOL_OPTS,
                      CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS,
                      CAP_FILM_TYPE_OPTS, CAP_FILM_VOL_OPTS,
                      DIODE_TYPE_RADIO_OPTS, DIODE_TYPE_PICK_OPTS, DIODE_TECH_OPTS, DIODE_PKG_OPTS,
                      TRANSISTOR_PKG_OPTS, BJT_POLARITY_OPTS, FET_POLARITY_OPTS,
                      SMD_RES_SIZE_OPTS, SMD_RES_TOL_OPTS, SMD_RES_PWR_OPTS,
                      SMD_CAP_SIZE_OPTS, SMD_CAP_VOL_OPTS, SMD_CAP_DIELECTRIC_OPTS,
                      SMD_TANT_CASE_OPTS, SMD_DIODE_PKG_OPTS, SMD_TRANSISTOR_PKG_OPTS,
                      SMD_RES_SIZE_DEFAULT, SMD_RES_TOL_DEFAULT, SMD_CAP_SIZE_DEFAULT)
    from TH_Resistors import search_tht_resistor, process_resistor
    from TH_Radial_ElectrolyticCapacitors import search_tht_capacitor, process_capacitor
    from TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor
    from TH_Diodes import search_diode, process_diode
    from TH_Transistors_BJT import search_tht_bjt, process_bjt
    from TH_Transistors_JFET import search_tht_jfet, process_jfet
    from TH_Transistors_MOSFET import search_tht_mosfet, process_mosfet
    from TH_Transistor_Common import apply_pinout
    from SMD_Resistors import search_smd_resistor, process_smd_resistor
    from SMD_Capacitors import (search_smd_mlcc, process_smd_mlcc, search_smd_tantalum,
                                    process_smd_tantalum, search_smd_aluminum, process_smd_aluminum)
    from Stock_Parts import search_part, process_part, stock_symbol_exists, stock_footprint_exists

# (cat_id, lib_config) per capacitor tab key - shared source of truth between the
# interactive GUI search path (plugin.py) and the batch path below. Copy lib_config
# before mutating it (e.g. is_film) since this dict is shared/module-level.
CAP_TAB_CONFIGS = {
    'alum': ('58', {'designator': 'CP', 'sym_lib': 'CP_TH_emDashGameChanger', 'proc': 'alum'}),
    'film': ('60', {'designator': 'C', 'sym_lib': 'C_TH_emDashGameChanger', 'proc': 'disc'}),
    'mica': ('61', {'designator': 'C', 'sym_lib': 'C_TH_emDashGameChanger', 'proc': 'disc'}),
}

_VOLTAGE_ALIASES = {"any", "dontcare", "no filter"}


class BatchSpecError(Exception):
    pass


@dataclass
class BatchSpec:
    line_no: int
    raw_line: str
    type_kw: str
    fields: dict = field(default_factory=dict)


def _match_option(value, opts):
    """Case/whitespace-insensitive exact match against an option-label list.
    Returns the matching index, or None if nothing matches."""
    norm = value.strip().lower()
    for i, opt in enumerate(opts):
        if opt.strip().lower() == norm:
            return i
    return None


def _match_label(value, opts):
    """Like _match_option, but a label such as "DPAK (TO-252)" or "B (3528)" also
    matches on either part alone ("DPAK", "TO-252", "B", "3528")."""
    idx = _match_option(value, opts)
    if idx is not None:
        return idx
    norm = value.strip().lower()
    for i, opt in enumerate(opts):
        head, _, tail = opt.partition(' (')
        if norm in (head.strip().lower(), tail.rstrip(')').strip().lower()):
            return i
    return None


def _option_field(spec, name, opts, default_idx=0, matcher=_match_option):
    """Resolves an optional option-label field to its index (default_idx when absent)."""
    if name not in spec.fields:
        return default_idx
    idx = matcher(spec.fields[name], opts)
    if idx is None:
        raise BatchSpecError(f"Unrecognized {name}: {spec.fields[name]!r} (expected one of: {', '.join(opts)})")
    return idx


_YES = {"yes", "y", "true", "1", "on"}
_NO = {"no", "n", "false", "0", "off"}


def _handsolder(spec):
    value = spec.fields.get('handsolder', 'yes').strip().lower()
    if value in _YES:
        return True
    if value in _NO:
        return False
    raise BatchSpecError(f"Unrecognized handsolder: {spec.fields['handsolder']!r} (expected yes/no)")


def _resolve_voltage(value, vol_opts):
    """Returns the exact string to pass as the `voltage` arg to
    search_tht_capacitor/search_tht_disc_capacitor: a matched preset, the
    literal "I don't care" (via alias), or the raw value as a custom
    voltage passthrough (mirrors the GUI's Custom Voltage textbox override)."""
    norm = value.strip().lower()
    if norm in _VOLTAGE_ALIASES or norm == "i don't care":
        return "I don't care"
    idx = _match_option(value, vol_opts)
    if idx is not None:
        return vol_opts[idx]
    return value.strip()


def parse_batch_text(text):
    """Tokenizes each non-blank/non-comment line via shlex. Never raises -
    malformed lines are returned as a BatchSpec with fields['_parse_error']
    set, so run_batch can report them per-line instead of aborting."""
    specs = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        try:
            tokens = shlex.split(stripped, posix=True)
        except ValueError as e:
            specs.append(BatchSpec(line_no, raw_line, type_kw='', fields={'_parse_error': str(e)}))
            continue
        if not tokens:
            continue
        type_kw = tokens[0].lower()
        fields = {}
        parse_error = None
        for tok in tokens[1:]:
            if '=' not in tok:
                parse_error = f"Malformed field token (expected key=value): {tok!r}"
                break
            k, _, v = tok.partition('=')
            fields[k.strip().lower()] = v
        if parse_error:
            fields['_parse_error'] = parse_error
        specs.append(BatchSpec(line_no, raw_line, type_kw=type_kw, fields=fields))
    return specs


def resolve_resistor(spec):
    if 'value' not in spec.fields:
        raise BatchSpecError("Missing required field 'value'")
    value = spec.fields['value']

    comp_idx = _match_option(spec.fields.get('composition', RES_COMP_OPTS[0]), RES_COMP_OPTS)
    if comp_idx is None:
        raise BatchSpecError(f"Unrecognized composition: {spec.fields.get('composition')!r}")

    pwr_idx = _match_option(spec.fields.get('power', RES_PWR_OPTS[0]), RES_PWR_OPTS)
    if pwr_idx is None:
        raise BatchSpecError(f"Unrecognized power: {spec.fields.get('power')!r}")

    tol_idx = _match_option(spec.fields.get('tolerance', RES_TOL_OPTS[0]), RES_TOL_OPTS)
    if tol_idx is None:
        raise BatchSpecError(f"Unrecognized tolerance: {spec.fields.get('tolerance')!r}")

    return {
        'search_fn': search_tht_resistor,
        'search_args': (value, pwr_idx, tol_idx, comp_idx),
        'search_kwargs': {},
        'process_fn': process_resistor,
        'process_args': (),
        'display_type': 'resistor',
        'display_value': value,
    }


def _resolve_cap_common(spec, key, type_opts, vol_opts):
    if 'value' not in spec.fields:
        raise BatchSpecError("Missing required field 'value'")
    value = spec.fields['value'].replace('u', 'µ')  # mirrors on_search_click's cap_val normalization

    type_idx = 0
    if 'type' in spec.fields:
        type_idx = _match_option(spec.fields['type'], type_opts)
        if type_idx is None:
            raise BatchSpecError(f"Unrecognized type: {spec.fields['type']!r}")

    voltage = _resolve_voltage(spec.fields.get('voltage', vol_opts[0]), vol_opts)

    cat_id, base_lib_config = CAP_TAB_CONFIGS[key]
    lib_config = dict(base_lib_config)
    if key == 'film' and type_idx == 1:
        lib_config['is_film'] = True

    return value, type_idx, voltage, cat_id, lib_config


def resolve_cap_alum(spec):
    value, type_idx, voltage, cat_id, lib_config = _resolve_cap_common(
        spec, 'alum', CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS)
    return {
        'search_fn': search_tht_capacitor,
        'search_args': (value, voltage, type_idx, cat_id),
        'search_kwargs': {},
        'process_fn': process_capacitor,
        'process_args': (lib_config,),
        'display_type': 'cap_alum',
        'display_value': value,
    }


def resolve_cap_film(spec):
    value, type_idx, voltage, cat_id, lib_config = _resolve_cap_common(
        spec, 'film', CAP_FILM_TYPE_OPTS, CAP_FILM_VOL_OPTS)
    # 'film' tab's cat_id is '60', matching plugin.py's existing
    # `if cat_id == '60': search_tht_disc_capacitor(...)` branch.
    return {
        'search_fn': search_tht_disc_capacitor,
        'search_args': (value, voltage, cat_id),
        'search_kwargs': {'type_idx': type_idx},
        'process_fn': process_disc_capacitor,
        'process_args': (lib_config,),
        'display_type': 'cap_film',
        'display_value': value,
    }


def resolve_cap_mica(spec):
    value, type_idx, voltage, cat_id, lib_config = _resolve_cap_common(
        spec, 'mica', CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS)
    # Preserve existing production quirk exactly: mica's cat_id is '61' (not
    # '60'), so it is searched via search_tht_capacitor (radial-style
    # Axial/Radial filter) but processed via process_disc_capacitor (chosen
    # by lib_config['proc'] == 'disc'). This is what the interactive GUI
    # already does today (plugin.py's cat_id == '60' branch) - do not "fix" it.
    return {
        'search_fn': search_tht_capacitor,
        'search_args': (value, voltage, type_idx, cat_id),
        'search_kwargs': {},
        'process_fn': process_disc_capacitor,
        'process_args': (lib_config,),
        'display_type': 'cap_mica',
        'display_value': value,
    }


# --- Diodes / transistors (part-number-first) -------------------------------

DIODE_TYPE_OPTS = DIODE_TYPE_RADIO_OPTS + DIODE_TYPE_PICK_OPTS  # combined type index, as in the GUI


def _resolve_diode(spec, smd):
    pn = spec.fields.get('pn', '').strip()
    type_idx = _option_field(spec, 'type', DIODE_TYPE_OPTS)
    tech_idx = _option_field(spec, 'tech', DIODE_TECH_OPTS)
    pkg_idx = _option_field(spec, 'package', SMD_DIODE_PKG_OPTS if smd else DIODE_PKG_OPTS)
    if not pn and not (type_idx or tech_idx or pkg_idx):
        raise BatchSpecError("Need 'pn' (or at least one of type/tech/package)")
    lib_config = {'smd': True, 'handsolder': _handsolder(spec)} if smd else None
    return {
        'search_fn': search_diode,
        'search_args': (pn, type_idx, tech_idx, pkg_idx),
        'search_kwargs': {'smd': smd},
        'process_fn': process_diode,
        'process_args': (lib_config,),
        'display_type': 'smd_diode' if smd else 'diode',
        'display_value': pn or '(filters)',
    }


def resolve_diode(spec):
    return _resolve_diode(spec, smd=False)


def resolve_smd_diode(spec):
    return _resolve_diode(spec, smd=True)


# family -> (search, process, polarity options, terminal letters)
TRANSISTOR_FAMILIES = {
    'bjt': (search_tht_bjt, process_bjt, BJT_POLARITY_OPTS, "EBC"),
    'jfet': (search_tht_jfet, process_jfet, FET_POLARITY_OPTS, "GDS"),
    'mosfet': (search_tht_mosfet, process_mosfet, FET_POLARITY_OPTS, "GDS"),
}


def parse_pins(value, terminals):
    """'BEC' -> {'1': 'B', '2': 'E', '3': 'C'} - terminal letters in pin order.
    Must use every one of the family's terminals exactly once."""
    letters = value.strip().upper().replace('-', '').replace(',', '').replace(' ', '')
    if sorted(letters) != sorted(terminals):
        raise BatchSpecError(
            f"pins={value!r} must list each of {', '.join(terminals)} exactly once, in pin order 1..{len(terminals)}")
    return {str(i): t for i, t in enumerate(letters, start=1)}


def _resolve_transistor(spec, family, smd):
    search_fn, process_fn, polarity_opts, terminals = TRANSISTOR_FAMILIES[family]
    pn = spec.fields.get('pn', '').strip()
    polarity_idx = _option_field(spec, 'polarity', polarity_opts)
    pkg_idx = _option_field(spec, 'package', SMD_TRANSISTOR_PKG_OPTS if smd else TRANSISTOR_PKG_OPTS,
                            matcher=_match_label)
    if not pn and not (polarity_idx or pkg_idx):
        raise BatchSpecError("Need 'pn' (or at least one of polarity/package)")
    pins = parse_pins(spec.fields['pins'], terminals) if 'pins' in spec.fields else None
    footprint = spec.fields.get('footprint', '').strip() or None
    if footprint and ':' in footprint:
        footprint = footprint.split(':', 1)[1]  # accept "Lib:Name" too
    return {
        'search_fn': search_fn,
        'search_args': (pn, polarity_idx, pkg_idx),
        'search_kwargs': {'smd': smd},
        'process_fn': process_fn,
        'process_args': ({'smd': smd},),
        'display_type': f"smd_{family}" if smd else family,
        'display_value': pn or '(filters)',
        'pins': pins,
        'footprint': footprint,
    }


def _transistor_resolver(family, smd):
    return lambda spec: _resolve_transistor(spec, family, smd)


# --- SMD resistors / capacitors ---------------------------------------------

def _required_value(spec):
    if 'value' not in spec.fields:
        raise BatchSpecError("Missing required field 'value'")
    return spec.fields['value']


def resolve_smd_resistor(spec):
    value = _required_value(spec)
    size = SMD_RES_SIZE_OPTS[_option_field(spec, 'size', SMD_RES_SIZE_OPTS, SMD_RES_SIZE_DEFAULT)]
    tol = SMD_RES_TOL_OPTS[_option_field(spec, 'tolerance', SMD_RES_TOL_OPTS, SMD_RES_TOL_DEFAULT)]
    pwr = SMD_RES_PWR_OPTS[_option_field(spec, 'power', SMD_RES_PWR_OPTS)]
    return {
        'search_fn': search_smd_resistor,
        'search_args': (value, size, tol, pwr),
        'search_kwargs': {},
        'process_fn': process_smd_resistor,
        'process_args': ({'handsolder': _handsolder(spec)},),
        'display_type': 'smd_resistor',
        'display_value': value,
    }


def _smd_cap_voltage(spec):
    return _resolve_voltage(spec.fields.get('voltage', SMD_CAP_VOL_OPTS[0]), SMD_CAP_VOL_OPTS)


def resolve_smd_cap(spec):
    value = _required_value(spec)
    size = SMD_CAP_SIZE_OPTS[_option_field(spec, 'size', SMD_CAP_SIZE_OPTS, SMD_CAP_SIZE_DEFAULT)]
    dielectric = SMD_CAP_DIELECTRIC_OPTS[_option_field(spec, 'dielectric', SMD_CAP_DIELECTRIC_OPTS,
                                                       matcher=_match_label_dielectric)]
    return {
        'search_fn': search_smd_mlcc,
        'search_args': (value, size, _smd_cap_voltage(spec), dielectric),
        'search_kwargs': {},
        'process_fn': process_smd_mlcc,
        'process_args': ({'handsolder': _handsolder(spec)},),
        'display_type': 'smd_cap',
        'display_value': value,
    }


def _match_label_dielectric(value, opts):
    """'C0G', 'NP0' and 'C0G/NP0' all pick the C0G/NP0 option."""
    idx = _match_option(value, opts)
    if idx is not None:
        return idx
    norm = value.strip().lower()
    for i, opt in enumerate(opts):
        if norm in opt.lower().split('/'):
            return i
    return None


def resolve_smd_tant(spec):
    value = _required_value(spec)
    case = SMD_TANT_CASE_OPTS[_option_field(spec, 'case', SMD_TANT_CASE_OPTS, matcher=_match_label)]
    return {
        'search_fn': search_smd_tantalum,
        'search_args': (value, _smd_cap_voltage(spec), case),
        'search_kwargs': {},
        'process_fn': process_smd_tantalum,
        'process_args': ({'handsolder': _handsolder(spec)},),
        'display_type': 'smd_tant',
        'display_value': value,
    }


def resolve_smd_alum(spec):
    value = _required_value(spec)
    return {
        'search_fn': search_smd_aluminum,
        'search_args': (value, _smd_cap_voltage(spec)),
        'search_kwargs': {},
        'process_fn': process_smd_aluminum,
        'process_args': ({},),
        'display_type': 'smd_alum',
        'display_value': value,
    }


def resolve_part(spec):
    """Any part by exact MPN onto a named stock symbol + footprint (ICs, LEDs,
    trimmers...): part pn=TL072CDR symbol=Amplifier_Operational:TL072
    footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"""
    pn = spec.fields.get('pn', '').strip()
    symbol = spec.fields.get('symbol', '').strip()
    footprint = spec.fields.get('footprint', '').strip()
    missing = [k for k, v in (('pn', pn), ('symbol', symbol), ('footprint', footprint)) if not v]
    if missing:
        raise BatchSpecError(f"Missing required field(s): {', '.join(missing)}")
    if not stock_symbol_exists(symbol):
        raise BatchSpecError(f"No stock KiCad symbol {symbol!r} (expected Lib:Name)")
    if not stock_footprint_exists(footprint):
        raise BatchSpecError(f"No stock KiCad footprint {footprint!r} (expected Lib:Name)")
    return {
        'search_fn': search_part,
        'search_args': (pn,),
        'search_kwargs': {},
        'process_fn': process_part,
        'process_args': ({'symbol': symbol, 'footprint': footprint},),
        'display_type': 'part',
        'display_value': pn,
    }


BATCH_RESOLVERS = {
    'resistor': resolve_resistor,
    'cap_alum': resolve_cap_alum,
    'cap_film': resolve_cap_film,
    'cap_mica': resolve_cap_mica,
    'diode': resolve_diode,
    'bjt': _transistor_resolver('bjt', smd=False),
    'jfet': _transistor_resolver('jfet', smd=False),
    'mosfet': _transistor_resolver('mosfet', smd=False),
    'smd_resistor': resolve_smd_resistor,
    'smd_cap': resolve_smd_cap,
    'smd_tant': resolve_smd_tant,
    'smd_alum': resolve_smd_alum,
    'smd_diode': resolve_smd_diode,
    'smd_bjt': _transistor_resolver('bjt', smd=True),
    'smd_jfet': _transistor_resolver('jfet', smd=True),
    'smd_mosfet': _transistor_resolver('mosfet', smd=True),
    'part': resolve_part,
}


def record_generate(row, success, msg):
    """Maps a generate_library_files (success, msg) result onto a report row."""
    if not success:
        row['status'] = 'gen_error'
    elif msg.startswith("Already exists:"):
        row['status'] = 'duplicate'
    else:
        row['status'] = 'generated'
    row['detail'] = msg


def _prepare_transistor(row, resolved, processed):
    """Applies a batch pins=/footprint= to a processed transistor. Returns True
    when it is ready to generate; otherwise marks the row (needs_pinout - the
    plugin then asks a human via PinoutConfirmDialog - or validation_error)."""
    pc = processed.get("pinout_confirm") or {}
    candidates = pc.get("footprint_candidates", [])
    footprint = resolved.get('footprint')
    if footprint:
        if footprint not in candidates:
            row['status'] = 'validation_error'
            row['detail'] = (f"footprint={footprint!r} isn't a stock candidate for package "
                             f"{pc.get('package_raw', '?')!r}; candidates: {', '.join(candidates) or 'none'}")
            return False
        pc["footprint_resolved"] = footprint
    else:
        footprint = pc.get("footprint_resolved")

    pins = resolved.get('pins')
    if pins and footprint:
        apply_pinout(processed, pins, footprint)
        return True

    if pins:
        # Seed the dialog with the pins the user gave; they only still have to pick the footprint.
        pc["default_numbers"] = {t: n for n, t in pins.items()}
    row['status'] = 'needs_pinout'
    if not pins:
        row['detail'] = "No pins= given - confirm the pinout in the dialog."
    else:
        row['detail'] = f"Footprint ambiguous ({', '.join(candidates) or 'none'}) - pick one in the dialog."
    row['processed'] = processed
    return False


def _search_job(job, access_token, client_id, token_refresher):
    """Runs just the network search call for one resolved spec. Safe to call
    concurrently - touches no shared state besides the (thread-safe) requests
    call itself. Returns (spec, resolved, products_or_None, error_or_None),
    where error is a (status, detail) tuple."""
    spec, resolved = job
    try:
        results = resolved['search_fn'](
            *resolved['search_args'], access_token, client_id, token_refresher,
            **resolved['search_kwargs'])
    except Exception as e:
        return spec, resolved, None, ('api_error', str(e))

    if results is None:
        return spec, resolved, None, ('api_error', 'API call failed (auth issue)')
    if results.get('ProductsCount', 0) == 0 or not results.get('Products'):
        return spec, resolved, None, ('no_results', 'No matching products')
    return spec, resolved, results['Products'], None


def _process_best(resolved, products):
    """Processes the cheapest product that maps cleanly onto a stock footprint
    (no 'error', and for transistors at least one footprint candidate) - e.g.
    MMBT3904's cheapest listing is a DFN variant with no stock footprint, while
    the SOT-23 one is a few cents more. Falls back to the cheapest product."""
    first = None
    for product in products:
        processed = resolved['process_fn'](product, *resolved['process_args'])
        if first is None:
            first = processed
        pc = processed.get("pinout_confirm")
        if not processed.get("error") and (pc is None or pc.get("footprint_candidates")):
            return processed
    return first


def run_batch(batch_text, access_token, client_id, token_refresher, generate_library_files, max_workers=5):
    """Runs every spec in batch_text through the existing search/process/generate
    pipeline, auto-picking the cheapest in-stock Digi-Key result per line that
    maps onto a stock footprint (see _process_best).
    Returns a list of row dicts: {line_no, type, value, status, detail}.
    status is one of: generated, duplicate, no_results, parse_error,
    validation_error, api_error, process_error, gen_error, needs_pinout.
    needs_pinout rows (transistors without a usable pins=/footprint=) also
    carry 'processed' - the caller must get a human-confirmed pinout, apply it
    (TH_Transistor_Common.apply_pinout) and generate, then record_generate().
    A failure on one line never aborts the rest of the batch.

    The Digi-Key search calls for different lines run concurrently (up to
    max_workers at a time) since they're independent network I/O. The
    process/generate step (which appends to shared .kicad_sym/.kicad_mod
    library files and is NOT safe to run concurrently) always runs on this
    thread, one line at a time, in original line order - see the comment
    below on why executor.map makes that automatic without any locking."""
    specs = parse_batch_text(batch_text)
    rows_by_line = {}
    search_jobs = []  # (spec, resolved) for specs that resolved OK, in original order

    for spec in specs:
        row = {
            'line_no': spec.line_no,
            'type': spec.type_kw or '(unknown)',
            'value': spec.fields.get('value', spec.fields.get('pn', '')),
            'status': '',
            'detail': '',
        }

        if '_parse_error' in spec.fields:
            row['status'] = 'parse_error'
            row['detail'] = spec.fields['_parse_error']
            rows_by_line[spec.line_no] = row
            continue

        resolver = BATCH_RESOLVERS.get(spec.type_kw)
        if resolver is None:
            row['status'] = 'parse_error'
            row['detail'] = f"Unrecognized type keyword: {spec.type_kw!r}"
            rows_by_line[spec.line_no] = row
            continue

        try:
            resolved = resolver(spec)
        except BatchSpecError as e:
            row['status'] = 'validation_error'
            row['detail'] = str(e)
            rows_by_line[spec.line_no] = row
            continue

        row['type'] = resolved['display_type']
        row['value'] = resolved['display_value']
        rows_by_line[spec.line_no] = row
        search_jobs.append((spec, resolved))

    if search_jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            search_fn = lambda job: _search_job(job, access_token, client_id, token_refresher)
            # executor.map submits every job up front (so the searches overlap in
            # background threads) but yields results back in the same order the
            # jobs were submitted in - so this loop, which does the file-writing
            # process/generate step, still runs single-threaded and in original
            # line order, even though the slow network part happened concurrently.
            for spec, resolved, products, error in executor.map(search_fn, search_jobs):
                row = rows_by_line[spec.line_no]

                if error:
                    row['status'], row['detail'] = error
                    continue

                try:
                    processed = _process_best(resolved, products)
                except Exception as e:
                    row['status'] = 'process_error'
                    row['detail'] = str(e)
                    continue

                if 'pins' in resolved and not _prepare_transistor(row, resolved, processed):
                    continue

                try:
                    record_generate(row, *generate_library_files(processed))
                except Exception as e:
                    row['status'] = 'gen_error'
                    row['detail'] = str(e)

    return [rows_by_line[spec.line_no] for spec in specs]
