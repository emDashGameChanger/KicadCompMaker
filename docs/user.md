# KiCad Component Maker

Generates ready-to-use KiCad components — schematic symbol **and** matching footprint, plus datasheet link, ratings, and part number — straight from Digikey's catalog. No more hunting down a matching footprint by hand, and since every part carries a real Digikey part number, the BOM plugin's output can be uploaded straight back to Digikey to order.

## Overview

A "component" here means a schematic symbol bundled with its footprint and metadata (datasheet, voltage/power/tolerance ratings, part number) — generated together so they always match.

**Currently supported (Through Hole):**

| Type | Notes |
|---|---|
| Resistors | Any standard carbon/metal-film form factor |
| Aluminum Electrolytic Capacitors | The can type, radial or axial, both leads out the bottom |
| Disc / Film Capacitors | The classic brown or blue disc ceramics, leads out the bottom |

!!! note "Not yet supported"
    Surface Mount and Diodes have tabs in the GUI, but no search/generation behind them yet.

## Usage

### Install

For KiCad 9 on Linux:

```bash
cd ~/.local/share/kicad/9.0/scripting/plugins/
git clone https://github.com/emDashGameChanger/KicadCompMaker
```

Open KiCad's schematic editor — a new icon appears at the right end of the toolbar. Click it to launch the importer.

### First use: Digikey credentials

The first time you run it, you'll be prompted for a **Digikey Client ID** and **Client Secret**. These are saved locally and reused after that.

### Generating a single component

1. Click the toolbar icon to open the importer.
2. Pick a tab (Resistor, Aluminum Electrolytic, Disc/Film) and fill in the parameters.
3. Click **OK** — you'll get a list of matching parts, cheapest first.
4. Select the one you want and click **OK** again to generate it.

### Batch import

For adding many parts at once, use the **Batch Import** tab: type or paste a list into the text box (or **Load from File...** to load a `.txt` file), one part spec per line, then click **Search**.

Each line is looked up on Digikey and the **cheapest in-stock match is generated automatically** — no per-part picker. When it's done, you get a report showing what happened per line: generated, already existed, no results, or error.

**File format:**

- Plain `.txt` file, or typed/pasted directly into the text box.
- One part spec per line: `<type> field=value field=value ...`
- Blank lines are ignored; lines starting with `#` are comments.
- Type keyword and field names are case-insensitive.
- Quote values containing spaces: `power="1/4 watt"`.
- Unknown/misspelled field names are silently ignored.
- Every line needs a `value` field — the only field that's always required.
- Any field left out falls back to the same default the GUI itself starts with.

**Supported types and fields:**

=== "resistor"
    Through-hole resistor.

    | Field | Required | Options | Default |
    |---|---|---|---|
    | `value` | yes | e.g. `4.7k`, `10k`, `220`, `1M` | — |
    | `composition` | no | `Metal Film`, `Carbon Film` | Metal Film |
    | `power` | no | `1/8 watt`, `1/4 watt`, `1/2 watt`, `1 watt` | 1/8 watt |
    | `tolerance` | no | `+- .1%`, `+-1%`, `+-2%`, `+-5%`, `+-10%`, `+-20%` | +- .1% |

=== "cap_alum"
    Aluminum electrolytic (radial/axial can) capacitor.

    | Field | Required | Options | Default |
    |---|---|---|---|
    | `value` | yes | e.g. `10u`, `100u`, `220u` | — |
    | `type` | no | `Axial`, `Radial` | Axial |
    | `voltage` | no | `6.3v`, `10v`, `16v`, `25v`, `50v`, `63v`, `100v`, any custom voltage, or `any`/`dontcare` to skip filtering | 6.3v |

=== "cap_film"
    Disc ceramic or film capacitor.

    | Field | Required | Options | Default |
    |---|---|---|---|
    | `value` | yes | e.g. `100n`, `10n`, `1u` | — |
    | `type` | no | `Disc`, `Film` | Disc |
    | `voltage` | no | `25v`, `50v`, `100v`, `500v`, `1kV`, `2kV`, any custom voltage, or `any`/`dontcare` to skip filtering | 25v |

=== "cap_mica"
    Mica/PTFE capacitor.

    | Field | Required | Options | Default |
    |---|---|---|---|
    | `value` | yes | e.g. `47n`, `100pF` | — |
    | `type` | no | `Axial`, `Radial` | Axial |
    | `voltage` | no | `6.3v`, `10v`, `16v`, `25v`, `50v`, `63v`, `100v`, any custom voltage, or `any`/`dontcare` to skip filtering | 6.3v |

**Example file:**

```
# resistors: value is the only thing you must set
resistor value=1k
resistor value=4.7k power="1/4 watt" tolerance=+-5%
resistor value=10k composition="Carbon Film"

# capacitors
cap_alum value=100u type=Radial voltage=25v
cap_film value=10n type=Film voltage=any
cap_mica value=100pF
```

### Adding the generated libraries to KiCad

Generated components go into shared per-category libraries:

| Category | Footprint library | Symbol library |
|---|---|---|
| TH Polarized Electrolytic Caps | `~/.local/share/kicad/9.0/footprints/CP_TH_emDashGameChanger.pretty` | `~/.local/share/kicad/9.0/symbols/CP_TH_emDashGameChanger.kicad_sym` |
| TH Disc Capacitors | `~/.local/share/kicad/9.0/footprints/C_TH_emDashGameChanger.pretty` | `~/.local/share/kicad/9.0/symbols/C_TH_emDashGameChanger.kicad_sym` |
| TH Resistors | `~/.local/share/kicad/9.0/footprints/R_TH_emDashGameChanger.pretty` | `~/.local/share/kicad/9.0/symbols/R_TH_emDashGameChanger.kicad_sym` |

Add each one to KiCad once:

1. **Symbol libraries:** KiCad → Preferences → Manage Symbol Libraries... → **+** to add, using the nicknames/paths above (e.g. nickname `R_TH_emDashGameChangerSym`, path `~/.local/share/kicad/9.0/symbols/R_TH_emDashGameChanger.kicad_sym`).
2. **Footprint libraries:** KiCad → Preferences → Manage Footprint Libraries... → **+** to add the same way (e.g. nickname `R_TH_emDashGameChanger`, path `~/.local/share/kicad/9.0/footprints/R_TH_emDashGameChanger.pretty`).

Once added, newly generated parts in that category just show up — no need to re-add the library each time.
