"""Batch parsing/resolution for every type, pins= validation and the
needs_pinout flow, with the Digi-Key search stubbed out. No network."""
import pytest

import BatchImport
from BatchImport import (BATCH_RESOLVERS, BatchSpecError, parse_batch_text, parse_pins, run_batch)


def _resolve(line):
    spec = parse_batch_text(line)[0]
    return BATCH_RESOLVERS[spec.type_kw](spec)


@pytest.mark.parametrize("line", [
    "resistor value=10k",
    "cap_alum value=10u voltage=25v",
    "cap_film value=100n",
    "cap_mica value=100p",
    "diode pn=1N4148",
    "diode type=Zener package=DO-35",
    "bjt pn=2N3904 pins=EBC",
    "jfet pn=J201",
    "mosfet pn=2N7000 pins=SGD",
    "smd_resistor value=10k size=0603 tolerance=1% power=1/10W handsolder=no",
    "smd_cap value=100n size=0603 voltage=50v dielectric=X7R",
    "smd_cap value=10p dielectric=C0G",
    "smd_tant value=10u voltage=16v case=B",
    "smd_tant value=10u case=3528",
    "smd_alum value=47u voltage=25v",
    "smd_diode pn=SS14",
    "smd_bjt pn=MMBT3904 pins=BEC",
    "smd_jfet pn=MMBFJ201 pins=DSG",
    "smd_mosfet pn=IRLR024N package=DPAK pins=GDS footprint=TO-252-2",
])
def test_every_type_resolves(line):
    resolved = _resolve(line)
    assert callable(resolved['search_fn']) and callable(resolved['process_fn'])


@pytest.mark.parametrize("line,msg", [
    ("smd_resistor size=0603", "value"),
    ("smd_resistor value=1k size=0604", "size"),
    ("smd_cap value=1u handsolder=maybe", "handsolder"),
    ("smd_bjt pn=MMBT3904 pins=BEE", "pins"),
    ("mosfet pn=2N7000 pins=GD", "pins"),
    ("smd_diode", "pn"),
    ("bjt package=TO-999", "package"),
])
def test_validation_errors(line, msg):
    with pytest.raises(BatchSpecError, match=msg):
        _resolve(line)


def test_resolved_args():
    r = _resolve("smd_resistor value=4k7")
    assert r['search_args'] == ("4k7", "0603", "1%", "I don't care")  # GUI defaults
    assert r['process_args'] == ({'handsolder': True},)
    assert _resolve("smd_tant value=1u case=C")['search_args'][2] == "C (6032)"
    assert _resolve("smd_cap value=1u dielectric=NP0")['search_args'][3] == "C0G/NP0"
    assert _resolve("smd_cap value=1u voltage=4v")['search_args'][2] == "4v"  # custom passthrough
    assert _resolve("smd_mosfet package=D2PAK")['search_args'] == ('', 0, 7)
    assert _resolve("diode type=RF\\ Diode")['search_args'][1] == 6
    t = _resolve("smd_mosfet pn=X footprint=Package_TO_SOT_SMD:TO-252-2")
    assert t['footprint'] == "TO-252-2" and t['pins'] is None


def test_parse_pins():
    assert parse_pins("bec", "EBC") == {'1': 'B', '2': 'E', '3': 'C'}
    assert parse_pins("G-S-D", "GDS") == {'1': 'G', '2': 'S', '3': 'D'}


# --- run_batch with stubbed search ------------------------------------------

def _transistor_product(pkg):
    return {
        "ManufacturerProductNumber": "FAKE1", "DatasheetUrl": "", "UnitPrice": 0.1,
        "ProductVariations": [{"DigiKeyProductNumber": "FAKE1-ND", "MinimumOrderQuantity": 1}],
        "Parameters": [{"ParameterId": 16, "ValueText": pkg}],
    }


@pytest.fixture
def stub_search(monkeypatch):
    pkgs = {}

    def fake(pn, polarity_idx, pkg_idx, token, client_id, refresher=None, smd=False):
        return {"ProductsCount": 1, "Products": [_transistor_product(pkgs[pn])]}

    for fam in ('bjt', 'jfet', 'mosfet'):
        _, process_fn, pol, terms = BatchImport.TRANSISTOR_FAMILIES[fam]
        monkeypatch.setitem(BatchImport.TRANSISTOR_FAMILIES, fam, (fake, process_fn, pol, terms))
    for kw in ('bjt', 'mosfet', 'smd_bjt', 'smd_mosfet'):
        fam, smd = kw.replace('smd_', ''), kw.startswith('smd_')
        monkeypatch.setitem(BATCH_RESOLVERS, kw, BatchImport._transistor_resolver(fam, smd))
    return pkgs


def test_run_batch_pinout_flow(stub_search):
    stub_search.update({
        "A": "TO-236-3, SC-59, SOT-23-3",             # single candidate
        "B": "TO-236-3, SC-59, SOT-23-3",
        "C": "TO-252-3, DPak (2 Leads + Tab), SC-63",  # two candidates
        "D": "TO-252-3, DPak (2 Leads + Tab), SC-63",
        "E": "TO-252-3, DPak (2 Leads + Tab), SC-63",
    })
    generated = []

    def gen(processed):
        generated.append(processed)
        return True, f"Generated: {processed['Symbol Data']['symbol']}"

    rows = run_batch(
        "smd_bjt pn=A pins=BEC\n"
        "smd_bjt pn=B\n"
        "smd_mosfet pn=C pins=GDS\n"
        "smd_mosfet pn=D pins=GDS footprint=TO-252-2\n"
        "smd_mosfet pn=E pins=GDS footprint=SOT-23\n",
        "tok", "cid", None, gen)
    status = [r['status'] for r in rows]
    assert status == ['generated', 'needs_pinout', 'needs_pinout', 'generated', 'validation_error']

    sym_a = generated[0]["Symbol Data"]
    assert (sym_a["pin_b_number"], sym_a["pin_e_number"], sym_a["pin_c_number"]) == ("1", "2", "3")
    assert sym_a["footprint"] == "Package_TO_SOT_SMD:SOT-23"
    assert generated[1]["Symbol Data"]["footprint"] == "Package_TO_SOT_SMD:TO-252-2"

    # Pins given but footprint ambiguous: the dialog is pre-seeded with them.
    pc = rows[2]['processed']['pinout_confirm']
    assert pc['default_numbers'] == {'G': '1', 'D': '2', 'S': '3'}
    assert 'processed' in rows[1]
