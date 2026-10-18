"""Every stock footprint name the SMD/diode/transistor tables can emit must
exist in the installed KiCad library, and real Digi-Key package strings must
map to the right one. No network."""
import os

import pytest

from SMD_Common import (CHIP_FOOTPRINTS, TANTALUM_CASES, TANTALUM_FP_LIB, ALUM_CAN_SIZES, ALUM_FP_LIB,
                        chip_footprint, chip_size_from_package, tantalum_footprint, alum_footprint, _fmt_mm)
from TH_Diodes import SMD_DIODE_STOCK_FOOTPRINTS, SMD_STOCK_FP_LIB, normalize_package
from TH_Transistor_Common import (SMD_TRANSISTOR_STOCK_FOOTPRINTS, SMD_STOCK_FP_LIB as Q_LIB,
                                  normalize_package_family, match_stock_footprint)
from SMD_Capacitors import eng_capacitance

FP_ROOT = "/usr/share/kicad/footprints"
pytestmark = pytest.mark.skipif(not os.path.isdir(FP_ROOT), reason="KiCad footprint library not installed")


def _exists(lib, name):
    return os.path.exists(os.path.join(FP_ROOT, f"{lib}.pretty", f"{name}.kicad_mod"))


def _all_names():
    for lib, table in CHIP_FOOTPRINTS.values():
        for std, hand in table.values():
            yield lib, std
            yield lib, hand
    for metric, cases in TANTALUM_CASES.items():
        for letter, height in cases:
            name = f"CP_EIA-{metric}-{int(round(height * 10)):02d}_Kemet-{letter}"
            yield TANTALUM_FP_LIB, name
            yield TANTALUM_FP_LIB, name + "_HandSolder"
    for d, h in ALUM_CAN_SIZES:
        yield ALUM_FP_LIB, f"CP_Elec_{_fmt_mm(d)}x{_fmt_mm(h)}"
    for std, hand in SMD_DIODE_STOCK_FOOTPRINTS.values():
        yield SMD_STOCK_FP_LIB, std
        if hand:
            yield SMD_STOCK_FP_LIB, hand
    for names in SMD_TRANSISTOR_STOCK_FOOTPRINTS.values():
        for name in names:
            yield Q_LIB, name


@pytest.mark.parametrize("lib,name", sorted(set(_all_names())))
def test_stock_footprint_exists(lib, name):
    assert _exists(lib, name), f"{lib}:{name} missing"


@pytest.mark.parametrize("raw,size", [
    ("0603 (1608 Metric)", "0603"), ("0402 (1005 Metric)", "0402"), ("2512 (6332 Metric)", "2512"),
    ("Nonstandard", None), ("", None),
])
def test_chip_size(raw, size):
    assert chip_size_from_package(raw) == size


def test_chip_footprint_variants():
    assert chip_footprint("R", "0805", False) == "Resistor_SMD:R_0805_2012Metric"
    assert chip_footprint("C", "0603", True) == "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
    assert chip_footprint("C", "2512") is None


@pytest.mark.parametrize("pkg,height,code,expected", [
    ("1411 (3528 Metric)", None, "B", "CP_EIA-3528-21_Kemet-B_HandSolder"),
    ("1411 (3528 Metric)", 1.2, "", "CP_EIA-3528-12_Kemet-T_HandSolder"),
    ("2917 (7343 Metric)", None, "", "CP_EIA-7343-31_Kemet-D_HandSolder"),
    ("1206 (3216 Metric)", 1.6, "A", "CP_EIA-3216-18_Kemet-A_HandSolder"),
])
def test_tantalum_footprint(pkg, height, code, expected):
    fp, _ = tantalum_footprint(pkg, height, code, handsolder=True)
    assert fp == f"{TANTALUM_FP_LIB}:{expected}"


def test_tantalum_unknown_package():
    assert tantalum_footprint("Radial", None, None) == (None, None)


def test_alum_footprint():
    assert alum_footprint(6.3, 5.4) == ("Capacitor_SMD:CP_Elec_6.3x5.4", "6.3x5.4")
    assert alum_footprint(6.3, 5.5) == ("Capacitor_SMD:CP_Elec_6.3x5.4", "6.3x5.4")
    assert alum_footprint(12.5, 13.5) == (None, None)
    assert alum_footprint(None, 5) == (None, None)


@pytest.mark.parametrize("raw,pkg", [
    ("SOD-123", "SOD-123"),
    ("SC-76, SOD-323", "SOD-323"),
    ("DO-214AC, SMA", "SMA"),
    ("DO-214AA, SMB", "SMB"),
    ("DO-214AB, SMC", "SMC"),
    ("DO-213AC, MINI-MELF, SOD-80", "MiniMELF"),
    ("TO-236-3, SC-59, SOT-23-3", None),  # 3-pin diode in a SOT-23: no 2-pad stock footprint
])
def test_smd_diode_package(raw, pkg):
    assert normalize_package(raw, smd=True) == pkg


@pytest.mark.parametrize("raw,family", [
    ("TO-236-3, SC-59, SOT-23-3", "SOT-23"),
    ("SC-70, SOT-323", "SOT-323"),
    ("TO-243AA", "SOT-89"),
    ("TO-261-4, TO-261AA", "SOT-223"),
    ("TO-252-3, DPak (2 Leads + Tab), SC-63", "TO-252"),
    ("TO-263-3, D²Pak (2 Leads + Tab), TO-263AB", "TO-263"),
    ("SOT-23-6", None),
    ("6-TSSOP, SC-88, SOT-363", None),
])
def test_smd_transistor_family(raw, family):
    assert normalize_package_family(raw, smd=True) == family


def test_smd_transistor_footprint_resolution():
    assert match_stock_footprint("TO-236-3, SC-59, SOT-23-3", smd=True)["footprint"] == "SOT-23"
    ambiguous = match_stock_footprint("TO-252-3, DPak (2 Leads + Tab), SC-63", smd=True)
    assert ambiguous["footprint"] is None and len(ambiguous["candidates"]) == 2


@pytest.mark.parametrize("text,out", [
    ("0.1 µF", "100nF"), ("4700 pF", "4.7nF"), ("10 µF", "10uF"), ("1000 pF", "1nF"), ("22 pF", "22pF"),
    ("1500 µF", "1500uF"),
])
def test_eng_capacitance(text, out):
    assert eng_capacitance(text) == out
