    # KicadCompMaker
    Use the Digikey's API to make components for KiCad
    You will need a Digikey Client ID adn Client Secrete, the pluging will prompt you to enter those the first time you use it.
    When using the word "component" I'm referring to a schematic symbol with an associated footprint plus additional data like datasheets, voltage rating, power ratings, part numbers etc.
    When using a component you will not have to take the extra steps of finding an appropriate footprint to associate with the schematic symbol. Since these components have part numbers the output from the BOM plugin can be uploaded to digikey, making ordering easy.
  
    These have been implemented:
      Through Hole
        Resistors - these are for you normal carbon type resistors, or any having the same form factor
        Capacitors
          Aluminum Electrolytic Radial - These are for the can type that sometimes goes "pop". Both leads out the bottom
          Disc - Those ugly brown ones, and the prettier blue ones, leads out the bottom
        Diodes - search by part number (or type/technology/package), uses KiCad's stock footprints
        Transistors - BJT, JFET, MOSFET, search by part number, uses KiCad's stock footprints
      Surface Mount
        Resistors - chip resistors 0201 - 2512
        Capacitors
          Ceramic (MLCC) - chip sizes 0201 - 2220, filter by voltage and dielectric (C0G/NP0, X5R, X7R ...)
          Tantalum - molded case A/B/C/D/E (and the low profile variants, picked from the part's height)
          Aluminium Electrolytic - SMD cans, matched to the nearest stock CP_Elec_<diameter>x<height> footprint
        Diodes - SOD-123/323/523, SMA/SMB/SMC, MiniMELF and more
        Transistors - BJT, JFET, MOSFET in SOT-23/323/523, SOT-89, SOT-223, DPAK, D2PAK

    Every surface mount part (and every THT diode/transistor) points at one of KiCad's own stock footprints
    (Resistor_SMD, Capacitor_SMD, Capacitor_Tantalum_SMD, Diode_SMD, Package_TO_SOT_SMD ...), nothing new is generated
    for the footprint. If a part's package has no stock footprint you'll get an error instead of a wrong footprint.

    Hand-solder pads: the "Hand-solder pads" checkbox on the Surface Mount tab picks KiCad's _HandSolder /
    _Handsoldering footprint variant wherever one exists (chip R/C, tantalum, most diodes). It is on by default.
    The symbol name doesn't include it, so if the same part was already generated with the other choice it is
    reported as already existing - delete it from the library first if you want to switch.

    Transistors: Digikey doesn't say which pin is which, so before a transistor is generated a dialog shows the
    footprint and asks you to assign every pin (check the datasheet!). The pre-filled guess is only a guess.

    Batch Import:
    There is a third tab, "Batch Import", for when you have a list of parts to add instead of one at a time. Type or paste
    a list into the text box (or use "Load from File..." to load a .txt file), one part spec per line, then click Search.
    Each line is looked up on Digikey and the cheapest in-stock match is generated automatically - no per-part picker.
    When it's done you'll get a report showing what happened for each line (generated, already existed, no results, or an error).

    FILE FORMAT
      - Plain .txt file, or just typed/pasted into the text box.
      - One part spec per line: <type> field=value field=value ...
      - Blank lines are ignored.
      - Lines starting with # are comments and are ignored.
      - Field names and the type keyword are not case-sensitive.
      - If a value contains a space, quote it: power="1/4 watt"
      - Unknown/misspelled field names are silently ignored (they don't cause an error, they just have no effect).
      - Resistor and capacitor lines need a "value" field. Diode and transistor lines need a "pn" (part number)
        field, or at least one of their filter fields.
      - Any field you leave out just uses its default (same default the GUI itself starts with).

    SUPPORTED TYPES AND THEIR FIELDS

      resistor  ->  through-hole resistor
        value        (required)  e.g. 4.7k, 10k, 220, 1M
        composition  (optional)  Metal Film | Carbon Film            default: Metal Film
        power        (optional)  1/8 watt | 1/4 watt | 1/2 watt | 1 watt   default: 1/8 watt
        tolerance    (optional)  +- .1% | +-1% | +-2% | +-5% | +-10% | +-20%   default: +- .1%

      cap_alum  ->  aluminum electrolytic (radial/axial can) capacitor
        value    (required)  e.g. 10u, 100u, 220u
        type     (optional)  Axial | Radial                      default: Axial
        voltage  (optional)  6.3v | 10v | 16v | 25v | 50v | 63v | 100v, OR any other voltage
                              (e.g. 35v) as a custom value, OR any / dontcare to skip
                              voltage filtering entirely        default: 6.3v

      cap_film  ->  disc ceramic or film capacitor
        value    (required)  e.g. 100n, 10n, 1u
        type     (optional)  Disc | Film                         default: Disc
        voltage  (optional)  25v | 50v | 100v | 500v | 1kV | 2kV, OR a custom voltage,
                              OR any / dontcare to skip voltage filtering   default: 25v

      cap_mica  ->  mica/PTFE capacitor
        value    (required)  e.g. 47n, 100pF
        type     (optional)  Axial | Radial                      default: Axial
        voltage  (optional)  6.3v | 10v | 16v | 25v | 50v | 63v | 100v, OR a custom voltage,
                              OR any / dontcare to skip voltage filtering   default: 6.3v

      diode  ->  through-hole diode          smd_diode  ->  surface mount diode
        pn         (required*)  e.g. 1N4148, SS14
        type       (optional)  I don't care | Standard Diode | Zener | Bridge Rectifier | Diode Array |
                                Zener Array | RF Diode | Variable Capacitance (Varicap)   default: I don't care
        tech       (optional)  I don't care | Schottky | Standard | SiC Schottky         default: I don't care
        package    (optional)  diode: DO-41 | DO-35 | DO-15 | DO-201AD
                                smd_diode: SOD-123 | SOD-323 | SOD-523 | SMA | SMB | SMC | MiniMELF
        handsolder (smd_diode only, optional)  yes | no                                    default: yes

      bjt | jfet | mosfet  ->  through-hole transistor
      smd_bjt | smd_jfet | smd_mosfet  ->  surface mount transistor
        pn         (required*)  e.g. 2N3904, MMBT3904, BSS138
        polarity   (optional)  bjt: NPN | PNP     jfet/mosfet: N-Channel | P-Channel
        package    (optional)  THT: TO-92 | TO-18 | TO-39 | TO-220 | TO-126 | TO-247
                                SMD: SOT-23 | SOT-323 | SOT-523 | SOT-89 | SOT-223 | DPAK | D2PAK
        pins       (optional)  the terminal on each pin, in pin order 1, 2, 3 - e.g. pins=BEC means
                                pin 1 = Base, pin 2 = Emitter, pin 3 = Collector. bjt uses B/E/C,
                                jfet and mosfet use G/D/S. CHECK THE DATASHEET.
        footprint  (optional)  pick the stock footprint when the package has more than one,
                                e.g. footprint=TO-252-2 or footprint=TO-92_Inline
        Without pins (or when the footprint is ambiguous) the part is still searched, and when the batch
        finishes the pin assignment dialog opens for it - nothing is generated until you confirm it there.

      smd_resistor  ->  chip resistor
        value      (required)  e.g. 4.7k, 10k, 220, 1M
        size       (optional)  0201 | 0402 | 0603 | 0805 | 1206 | 1210 | 2010 | 2512   default: 0603
        tolerance  (optional)  0.1% | 0.5% | 1% | 5% | I don't care                 default: 1%
        power      (optional)  1/20W | 1/16W | 1/10W | 1/8W | 1/4W | 1/2W | 1W       default: I don't care
        handsolder (optional)  yes | no                                              default: yes

      smd_cap  ->  ceramic chip capacitor (MLCC)
        value      (required)  e.g. 100n, 22p, 10u
        size       (optional)  0201 | 0402 | 0603 | 0805 | 1206 | 1210 | 1812 | 2220   default: 0603
        voltage    (optional)  6.3v | 10v | 16v | 25v | 35v | 50v | 100v, a custom voltage, or any   default: any
        dielectric (optional)  C0G (or NP0) | X5R | X7R | X7S | Y5V                 default: I don't care
        handsolder (optional)  yes | no                                              default: yes

      smd_tant  ->  molded tantalum capacitor
        value      (required)  e.g. 10u, 47u
        voltage    (optional)  as smd_cap                                           default: any
        case       (optional)  A | B | C | D | E (or the metric code: 3216 | 3528 | 6032 | 7343 | 7360)   default: any
        handsolder (optional)  yes | no                                              default: yes

      smd_alum  ->  SMD aluminium electrolytic can
        value      (required)  e.g. 47u, 100u
        voltage    (optional)  as smd_cap                                           default: any

      part  ->  any other part by exact manufacturer part number (ICs, LEDs, trimmers...)
        pn         (required)  e.g. TL072CDR, LM386MX-1/NOPB
        symbol     (required)  a stock KiCad symbol, e.g. symbol=Amplifier_Operational:TL072
        footprint  (required)  a stock KiCad footprint, e.g. footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm
        The stock symbol is copied into Parts_emDashGameChanger with the Digi-Key price/part#/datasheet.

      * or at least one of the filter fields

    Surface mount symbols on a HandSolder footprint get an _HS suffix (e.g. R_0805_10k_1%_HS),
    so the hand-solder and standard versions of a part can live in the same library.

    Batch picks the cheapest in-stock part whose package maps onto a stock KiCad footprint.

    EXAMPLE FILE
      # resistors: value is the only thing you must set
      resistor value=1k
      resistor value=4.7k power="1/4 watt" tolerance=+-5%
      resistor value=10k composition="Carbon Film"

      # capacitors
      cap_alum value=100u type=Radial voltage=25v
      cap_film value=10n type=Film voltage=any
      cap_mica value=100pF

      # through-hole semiconductors
      diode pn=1N4148
      bjt pn=2N3904 pins=EBC footprint=TO-92_Inline

      # surface mount (see batch_test_smd.txt for more)
      smd_resistor value=10k size=0805 tolerance=1%
      smd_cap value=100n size=0603 voltage=50v dielectric=X7R
      smd_tant value=10u voltage=16v case=B
      smd_alum value=47u voltage=25v
      smd_diode pn=SS14
      smd_bjt pn=MMBT3904 pins=BEC
      smd_mosfet pn=BSS138           <- no pins, so you'll be asked when the batch finishes
      part pn=TL072CDR symbol=Amplifier_Operational:TL072 footprint=Package_SO:SOIC-8_3.9x4.9mm_P1.27mm

    To install (Linux Mint 22):
    In the terminal navigate to the folder you want to install into, for KiCad 9:
    cd ~/.local/share/kicad/9.0/scripting/plugins/
    git clone https://github.com/emDashGameChanger/KicadCompMaker
    
    When a component is generated they will go:
      Footprints
        Through hole Capacitors Polarized Electrolytics - ~/.local/share/kicad/9.0/footprints/CP_TH_emDashGameChanger.pretty
        Through hole Capacitors Disc - ~/.local/share/kicad/9.0/footprints/C_TH_emDashGameChanger.pretty
        Through hole Resistors - ~/.local/share/kicad/9.0/footprints/R_TH_emDashGameChanger.pretty
      Symbols
        Through hole Capacitors Polarized Electrolytics - ~/.local/share/kicad/9.0/symbols/CP_TH_emDashGameChanger.kicad_sym
        Through hole Capacitors Disc - ~/.local/share/kicad/9.0/symbols/C_TH_emDashGameChanger.kicad_sym
        Through hole Resistors - ~/.local/share/kicad/9.0/symbols/R_TH_emDashGameChanger.kicad_sym
        Through hole Diodes - ~/.local/share/kicad/9.0/symbols/D_TH_emDashGameChanger.kicad_sym
        Through hole Transistors - ~/.local/share/kicad/9.0/symbols/Q_TH_emDashGameChanger.kicad_sym
        Surface mount Resistors - ~/.local/share/kicad/9.0/symbols/R_SMD_emDashGameChanger.kicad_sym
        Surface mount Ceramic Capacitors - ~/.local/share/kicad/9.0/symbols/C_SMD_emDashGameChanger.kicad_sym
        Surface mount Tantalum/Aluminium Capacitors - ~/.local/share/kicad/9.0/symbols/CP_SMD_emDashGameChanger.kicad_sym
        Surface mount Diodes - ~/.local/share/kicad/9.0/symbols/D_SMD_emDashGameChanger.kicad_sym
        Parts (batch type part) - ~/.local/share/kicad/9.0/symbols/Parts_emDashGameChanger.kicad_sym
        Surface mount Transistors - ~/.local/share/kicad/9.0/symbols/Q_SMD_emDashGameChanger.kicad_sym
      Diodes, transistors and all surface mount parts use KiCad's stock footprint libraries, so they have no
      footprint library of their own.
    
    You will need to add these to kicads libraries (symbol and footprint) paths.
      Open Kicad -> Preferences -> Manaage Symbol Libraries . . . -> Click the '+' to add -> use the following nicknames and paths:
        Nickname: CP_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/CP_TH_emDashGameChanger.kicad_sym
        Nickname: C_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/C_TH_emDashGameChanger.kicad_sym
        Nickname: R_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/R_TH_emDashGameChanger.kicad_sym
        Nickname: D_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/D_TH_emDashGameChanger.kicad_sym
        Nickname: Q_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/Q_TH_emDashGameChanger.kicad_sym
        Nickname: R_SMD_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/R_SMD_emDashGameChanger.kicad_sym
        Nickname: C_SMD_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/C_SMD_emDashGameChanger.kicad_sym
        Nickname: CP_SMD_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/CP_SMD_emDashGameChanger.kicad_sym
        Nickname: D_SMD_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/D_SMD_emDashGameChanger.kicad_sym
        Nickname: Q_SMD_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/Q_SMD_emDashGameChanger.kicad_sym
        (a library file only exists once you've generated at least one part of that kind)
        
      Do the same for the footprints.
      Open Kicad -> Preferences -> Manaage Footprint Libraries . . . -> Click the '+' to add -> use the following nicknames and paths:
        Nickname: CP_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/CP_TH_emDashGameChanger.pretty
        Nickname: C_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/C_TH_emDashGameChanger.pretty
        Nickname: R_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/R_TH_emDashGameChanger.pretty
  
    To use:
      Open up the schematic editor, a circuit board icon will be at the right most position of the tool bar. Left click it and the importer will open. The first time it opens you will need to enter your Digikey Client ID and Client Secret. You can then select the type of component and paramerters. Once you have done that, left click OK. A list of of components will be presented, lowest price first. Select the one you want and left click OK. This will generate the component.
