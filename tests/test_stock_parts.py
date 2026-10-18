"""The `part` batch type (stock-symbol copy), the _HS hand-solder symbol suffix,
the transistor search's client-side filter fallback, and API-error surfacing.
No network."""
import subprocess
import shutil

import pytest

import BatchImport
from BatchImport import BATCH_RESOLVERS, BatchSpecError, parse_batch_text
from DigikeyPartNumber import check_api_response
from SMD_Common import handsolder_suffix
from Stock_Parts import copy_stock_symbol, parse_sexpr, process_part
from TH_Transistor_Common import _matches_filters


def _resolve(line):
    spec = parse_batch_text(line)[0]
    return BATCH_RESOLVERS[spec.type_kw](spec)


def test_part_resolves():
    r = _resolve("part pn=TL072CDR symbol=Amplifier_Operational:TL072 "
                 "footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    assert r['search_args'] == ("TL072CDR",)
    assert r['process_args'][0]['symbol'] == "Amplifier_Operational:TL072"


@pytest.mark.parametrize("line, msg", [
    ("part pn=TL072CDR footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "symbol"),
    ("part pn=X symbol=Nope:TL072 footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "stock KiCad symbol"),
    ("part pn=X symbol=Amplifier_Operational:TL072 footprint=Package_SO:NoSuch", "stock KiCad footprint"),
])
def test_part_rejects_bad_fields(line, msg):
    with pytest.raises(BatchSpecError, match=msg):
        _resolve(line)


def test_copy_flattens_extends_and_sets_properties():
    # TL072 is `(extends "LM2904")` in the stock lib - the copy must stand alone
    text = copy_stock_symbol("Amplifier_Operational:TL072", "TL072CDR",
                             {"Value": "TL072CDR", "Digikey Part#": "296-1283-1-ND"})
    sym = parse_sexpr(text)
    assert sym[1] == "TL072CDR"
    assert not any(isinstance(c, list) and c[0] == "extends" for c in sym)
    units = [c[1] for c in sym if isinstance(c, list) and c[0] == "symbol"]
    assert units and all(u.startswith("TL072CDR_") for u in units)
    props = {c[1]: c[2] for c in sym if isinstance(c, list) and c[0] == "property"}
    assert props["Value"] == "TL072CDR"
    assert props["Digikey Part#"] == "296-1283-1-ND"
    assert "dual opamp" in props["ki_keywords"]  # inherited from the derived symbol


@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli not installed")
def test_copied_symbols_load_in_kicad(tmp_path):
    syms = [copy_stock_symbol(s, f"T{i}", {"Value": "x"}) for i, s in enumerate(
        ["Amplifier_Operational:TL072", "Amplifier_Audio:LM386", "Timer:TLC555xD", "4xxx:4013", "Device:LED"])]
    lib = tmp_path / "t.kicad_sym"
    lib.write_text('(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "t")\n' + "\n".join(syms) + "\n)")
    out = tmp_path / "svg"
    subprocess.run(["kicad-cli", "sym", "export", "svg", "-o", str(out), str(lib)],
                   check=True, capture_output=True)
    assert {p.name.split("_unit")[0] for p in out.iterdir()} == {f"T{i}" for i in range(5)}


def test_process_part_hs_suffix():
    product = {"ManufacturerProductNumber": "LTST-C171KRKT", "UnitPrice": 0.16,
               "Description": {"ProductDescription": "LED RED CLEAR 0805 SMD"}}
    hs = process_part(product, {"symbol": "Device:LED",
                                "footprint": "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder"})
    std = process_part(product, {"symbol": "Device:LED", "footprint": "LED_SMD:LED_0805_2012Metric"})
    assert hs["Symbol Data"]["symbol"] == "LTST-C171KRKT_HS"
    assert std["Symbol Data"]["symbol"] == "LTST-C171KRKT"
    assert '(symbol "LTST-C171KRKT_HS"' in hs["sym_text"]


@pytest.mark.parametrize("fp, suffix", [
    ("Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder", "_HS"),
    ("D_SOD-323_HandSoldering", "_HS"),
    ("D_SMA_Handsoldering", "_HS"),
    ("Resistor_SMD:R_0805_2012Metric", ""),
    ("", ""),
    (None, ""),
])
def test_handsolder_suffix(fp, suffix):
    assert handsolder_suffix(fp) == suffix


def test_matches_filters():
    product = {"Parameters": [{"ParameterId": 69, "ValueId": "409393"}]}
    assert _matches_filters(product, [{"ParameterId": 69, "FilterValues": [{"Id": "409393"}, {"Id": "409430"}]}])
    assert not _matches_filters(product, [{"ParameterId": 69, "FilterValues": [{"Id": "409430"}]}])


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


def test_check_api_response_raises_on_quota_fault():
    fault = {"fault": {"faultstring": "Execution of ServiceCallout SC-Quota failed. Reason: ResponseCode 429"}}
    with pytest.raises(RuntimeError, match="SC-Quota"):
        check_api_response(_Resp(500, fault))
    with pytest.raises(RuntimeError, match="429"):
        check_api_response(_Resp(429, {}))
    check_api_response(_Resp(200, {}))
    check_api_response(_Resp(400, {}))  # 400s are handled by the callers


def test_api_error_surfaces_in_batch():
    def boom(*a, **k):
        raise RuntimeError("Digi-Key API error 500: quota")
    original = BatchImport.BATCH_RESOLVERS['smd_resistor']

    def resolver(spec):
        r = original(spec)
        r['search_fn'] = boom
        return r
    BatchImport.BATCH_RESOLVERS['smd_resistor'] = resolver
    try:
        rows = BatchImport.run_batch("smd_resistor value=10k", "tok", "cid", None, lambda d: (True, "Generated: x"))
    finally:
        BatchImport.BATCH_RESOLVERS['smd_resistor'] = original
    assert rows[0]['status'] == 'api_error'
    assert "quota" in rows[0]['detail']
