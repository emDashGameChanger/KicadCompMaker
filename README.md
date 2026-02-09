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
        
    To install (Linux Mint 22):
    In the terminal navigate to the folder you want to install into, for KiCad 9:
    cd ~/.local/share/kicad/9.0/plugins
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
