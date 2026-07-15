    # KicadCompMaker
    Use the Digikey's API to make components for KiCad
    You will need a Digikey Client ID adn Client Secrete, the pluging will prompt you to enter those the first time you use it.
    When using the word "component" I'm referring to a schematic symbol with an associated footprint plus additional data like datasheets, voltage rating, power ratings, part numbers etc.
    When using a component you will not have to take the extra steps of finding an appropriate footprint to associate with the schematic symbol. Since these components have part numbers the output from the BOM plugin can be uploaded to digikey, making ordering easy.
  
    NOTE: There are tabs for Through hole and Surface Mount, Surface Mount has not been implemented. These have been implemented:
      Through Hole
        Resistors - these are for you normal carbon type resistors, or any having the same form factor
        Capacitors
          Aluminum Electrolytic Radial - These are for the can type that sometimes goes "pop". Both leads out the bottom
          Disc - Those ugly brown ones, and the prettier blue ones, leads out the bottom

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
      - Every line needs a "value" field - that's the only field that's always required.
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

    Not supported yet: Surface Mount and Diodes have no batch (or single-search) support at all yet - those tabs are
    just placeholders in the GUI.

    EXAMPLE FILE
      # resistors: value is the only thing you must set
      resistor value=1k
      resistor value=4.7k power="1/4 watt" tolerance=+-5%
      resistor value=10k composition="Carbon Film"

      # capacitors
      cap_alum value=100u type=Radial voltage=25v
      cap_film value=10n type=Film voltage=any
      cap_mica value=100pF
        
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
    
    You will need to add these to kicads libraries (symbol and footprint) paths.
      Open Kicad -> Preferences -> Manaage Symbol Libraries . . . -> Click the '+' to add -> use the following nicknames and paths:
        Nickname: CP_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/CP_TH_emDashGameChanger.kicad_sym
        Nickname: C_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/C_TH_emDashGameChanger.kicad_sym
        Nickname: R_TH_emDashGameChangerSym LibraryPath: ~/.local/share/kicad/9.0/symbols/R_TH_emDashGameChanger.kicad_sym
        
      Do the same for the footprints.
      Open Kicad -> Preferences -> Manaage Footprint Libraries . . . -> Click the '+' to add -> use the following nicknames and paths:
        Nickname: CP_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/CP_TH_emDashGameChanger.pretty
        Nickname: C_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/C_TH_emDashGameChanger.pretty
        Nickname: R_TH_emDashGameChanger LibraryPath: ~/.local/share/kicad/9.0/footprints/R_TH_emDashGameChanger.pretty
  
    To use:
      Open up the schematic editor, a circuit board icon will be at the right most position of the tool bar. Left click it and the importer will open. The first time it opens you will need to enter your Digikey Client ID and Client Secret. You can then select the type of component and paramerters. Once you have done that, left click OK. A list of of components will be presented, lowest price first. Select the one you want and left click OK. This will generate the component.
