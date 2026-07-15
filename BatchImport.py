import shlex
from dataclasses import dataclass, field

try:
    from .gui import (RES_COMP_OPTS, RES_PWR_OPTS, RES_TOL_OPTS,
                       CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS,
                       CAP_FILM_TYPE_OPTS, CAP_FILM_VOL_OPTS)
    from .TH_Resistors import search_tht_resistor, process_resistor
    from .TH_Radial_ElectrolyticCapacitors import search_tht_capacitor, process_capacitor
    from .TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor
except ImportError:
    from gui import (RES_COMP_OPTS, RES_PWR_OPTS, RES_TOL_OPTS,
                      CAP_ALUM_TYPE_OPTS, CAP_ALUM_VOL_OPTS,
                      CAP_FILM_TYPE_OPTS, CAP_FILM_VOL_OPTS)
    from TH_Resistors import search_tht_resistor, process_resistor
    from TH_Radial_ElectrolyticCapacitors import search_tht_capacitor, process_capacitor
    from TH_Disc_Capacitors import search_tht_disc_capacitor, process_disc_capacitor

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


BATCH_RESOLVERS = {
    'resistor': resolve_resistor,
    'cap_alum': resolve_cap_alum,
    'cap_film': resolve_cap_film,
    'cap_mica': resolve_cap_mica,
}


def run_batch(batch_text, access_token, client_id, token_refresher, generate_library_files):
    """Runs every spec in batch_text through the existing search/process/generate
    pipeline, auto-picking the top (cheapest, in-stock) Digi-Key result per line.
    Returns a list of row dicts: {line_no, type, value, status, detail}.
    status is one of: generated, duplicate, no_results, parse_error,
    validation_error, api_error, process_error, gen_error.
    A failure on one line never aborts the rest of the batch."""
    specs = parse_batch_text(batch_text)
    rows = []

    for spec in specs:
        row = {
            'line_no': spec.line_no,
            'type': spec.type_kw or '(unknown)',
            'value': spec.fields.get('value', ''),
            'status': '',
            'detail': '',
        }

        if '_parse_error' in spec.fields:
            row['status'] = 'parse_error'
            row['detail'] = spec.fields['_parse_error']
            rows.append(row)
            continue

        resolver = BATCH_RESOLVERS.get(spec.type_kw)
        if resolver is None:
            row['status'] = 'parse_error'
            row['detail'] = f"Unrecognized type keyword: {spec.type_kw!r}"
            rows.append(row)
            continue

        try:
            resolved = resolver(spec)
        except BatchSpecError as e:
            row['status'] = 'validation_error'
            row['detail'] = str(e)
            rows.append(row)
            continue

        row['type'] = resolved['display_type']
        row['value'] = resolved['display_value']

        try:
            results = resolved['search_fn'](
                *resolved['search_args'], access_token, client_id, token_refresher,
                **resolved['search_kwargs'])
        except Exception as e:
            row['status'] = 'api_error'
            row['detail'] = str(e)
            rows.append(row)
            continue

        if results is None:
            row['status'] = 'api_error'
            row['detail'] = 'API call failed (auth issue)'
            rows.append(row)
            continue
        if results.get('ProductsCount', 0) == 0 or not results.get('Products'):
            row['status'] = 'no_results'
            row['detail'] = 'No matching products'
            rows.append(row)
            continue

        top_product = results['Products'][0]

        try:
            processed = resolved['process_fn'](top_product, *resolved['process_args'])
        except Exception as e:
            row['status'] = 'process_error'
            row['detail'] = str(e)
            rows.append(row)
            continue

        try:
            success, msg = generate_library_files(processed)
        except Exception as e:
            row['status'] = 'gen_error'
            row['detail'] = str(e)
            rows.append(row)
            continue

        if not success:
            row['status'] = 'gen_error'
            row['detail'] = msg
        elif msg.startswith("Already exists:"):
            row['status'] = 'duplicate'
            row['detail'] = msg
        else:
            row['status'] = 'generated'
            row['detail'] = msg
        rows.append(row)

    return rows
