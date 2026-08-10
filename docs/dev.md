# KiCad Component Maker — Dev Notes

!!! abstract "TL;DR — next up"
    Implement the Film/Poly capacitor variant — the Dielectric Material (Polyester, Metallized) and Composition ParameterId/ValueId pairs are already known (see `notes.txt`); wire the dielectric-material parameter into the search and tweak the template naming to distinguish film/poly from disc.

**Status:** 🟢 active — Through Hole (resistors, aluminum electrolytic caps, disc/film caps) is feature-complete at 1.0, including batch import. Surface Mount and Diodes are still placeholder-only tabs in the GUI.

???+ note "Where I left off"
    Latest commit (`2efdaca`) fixed capacitor voltage search and parallelized batch API calls in `BatchImport.py` (`ThreadPoolExecutor`, `max_workers=5`) so multi-line batch jobs hit Digikey concurrently instead of serially. Before that, `6bb9636` added the whole batch-import tab (paste/load a `.txt` spec list, auto-pick cheapest in-stock match per line, summary report dialog) and resistor composition support (Metal Film / Carbon Film).

    Also just wired the project into the OS: `plugin.py` is symlinked to `~/.local/bin/kicadcompmaker` and there's now a `~/.local/share/applications/kicadcompmaker.desktop` launcher (Categories: Science;Electronics) so it can run standalone outside KiCad via the `if __name__ == "__main__"` entry point at the bottom of `plugin.py` (see the Architecture section below on why that path exists).

??? note "Architecture"
    - `plugin.py` — entry point / `DigikeyPlugin` (the `ActionPlugin`). Owns credential handling (`get_token`, `_ensure_credentials`), the worker/result glue for each tab (resistor, capacitor, batch), and `generate_library_files`, which writes/appends the generated symbol + footprint into the shared per-category libraries under `~/.local/share/kicad/9.0/{symbols,footprints}/`.
    - `gui.py` — all `wx` dialogs: `DigikeyDialog` (main tabbed search form), `ResultDialog` / `BatchResultDialog` (results + report), `CredentialsDialog`, `JsonViewDialog`, `ProgressCounterDialog`.
    - `TH_Resistors.py`, `TH_Radial_ElectrolyticCapacitors.py`, `TH_Disc_Capacitors.py` — one module per component type. Each exposes a `search_tht_*` (Digikey product search) and `process_*`/`process_disc_capacitor` (turns a chosen product JSON into symbol/footprint data, including procedurally generating footprint polygons for the electrolytic can silkscreen in `generate_capacitor_polygons`).
    - `DigikeyVoltageMap.py` — maps arbitrary voltage strings to Digikey's internal `ValueId`s for filtering (`parse_voltage_volts`, `lookup_value_id`).
    - `BatchImport.py` — batch-mode spec parser (`parse_batch_text`, `BatchSpec`) and runner (`run_batch`), independent of the GUI so it's testable/callable on its own.
    - `symbolTemplates/`, `footprintTemplates/` — Jinja2 templates `generate_library_files` renders into the final `.kicad_sym` / footprint output.
    - A generated `code_map.md` at the repo root has full file-by-file function/class listings if you need exact line numbers — regenerate it rather than trusting it as line numbers drift.

??? note "Decisions"
    - **Component = symbol + footprint + metadata, bundled.** A "component" isn't just a schematic symbol — it's generated together with its footprint, datasheet link, and ratings (voltage/power/tolerance/part number) so the user never has to separately hunt for a matching footprint. Part numbers on the generated symbol also mean BOM-plugin output can be uploaded straight back to Digikey for ordering.
    - **Shared per-category libraries, not one-file-per-part.** Generated parts are appended into existing `.kicad_sym` / `.pretty` libraries per category (e.g. all TH resistors → `R_TH_emDashGameChanger.kicad_sym`) rather than creating a new library file per component. Keeps the KiCad library list short and matches how users already organize libraries by category.
    - **Batch mode auto-picks cheapest in-stock match, no per-line picker.** The single-part GUI flow shows a results list to choose from; batch mode intentionally skips that and takes the cheapest in-stock hit automatically, since the point of batch mode is a non-interactive run over many lines. Report dialog afterward shows generated / already-existed / no-results / error per line so mistakes are still visible after the fact.
    - **Batch API calls run in parallel (`ThreadPoolExecutor`, `max_workers=5`).** Serial lookups were too slow for large batch files; 5 workers balances speed against Digikey rate limits. See `_search_job`/`run_batch` in `BatchImport.py`.
    - **Credentials live in a gitignored `config.json`, prompted for on first use.** `DIGIKEY_CLIENT_ID`/`DIGIKEY_CLIENT_SECRET` are never committed (`config.json` is in `.gitignore`); `CredentialsDialog` in `gui.py` collects them the first time the plugin runs and `plugin.py` persists them locally.
    - **`plugin.py` has a dual entry point.** It's a `pcbnew.ActionPlugin` when run inside KiCad, but stubs out `pcbnew` in a `try/except ImportError` at the top and has `if __name__ == "__main__": ... app.MainLoop()` at the bottom, so it can also run standalone (this is what the `~/.local/bin/kicadcompmaker` symlink + desktop launcher rely on). Same dual-import pattern (`from .gui import ...` vs `from gui import ...`) is used for the sibling modules so both the packaged-plugin and standalone-script cases resolve imports correctly.

??? note "Next steps"
    - Film/Poly capacitor variant: `notes.txt` already has the raw Digikey `ParameterId`/`ValueId` pairs needed for Dielectric Material (Polyester, Metallized = ParameterId 909 / ValueId 388558) and Composition (Metal Film / Carbon Film = ParameterId 174). Ceramic disc caps can reuse current search settings as-is; Film needs the dielectric material parameter added to the search and a naming-convention tweak in the templates to distinguish film/poly from disc.
    - Surface Mount: currently placeholder tabs only, no search/generation implemented for any SMD component type.
    - Diodes: not started (no search, no processor, no templates).
    - No automated tests currently exist for `BatchImport.py`'s parsing/resolution logic (`parse_batch_text`, `resolve_resistor`, `resolve_cap_*`) — would be the easiest module to unit test since it has no GUI/network dependency at parse time.
