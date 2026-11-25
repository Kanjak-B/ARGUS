# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ARGUS is a prototype that documents a network's topology: it collects LLDP neighbors from Cisco IOS devices over SSH and exports JSON, Excel and a Graphviz PNG. `README.md` covers setup, configuration variables and known limitations. Comments, console output, documentation and commit messages are in French (`ssh_compat.py` is in English).

## Commands

PowerShell, from the repo root:

```powershell
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"      # dependencies live in pyproject.toml

argus serve                  # web app on 127.0.0.1:8000 (API docs at /docs)
python -m argus.generator    # one-shot documentation run
python -m argus.monitor      # monitoring loop

ruff check .
ruff format .                # CI runs `ruff format --check .`
python -m unittest discover -s tests -v
python -m unittest tests.test_argus.ChangeDetectionTests.test_lost_link   # single test
```

Frontend, from `frontend/`:

```powershell
npm install
npm run dev                  # Vite dev server, proxies /api to `argus serve`
npm run build                # type check + build into frontend/dist, served by FastAPI
```

CI (`.github/workflows/ci.yml`) runs the Python checks on 3.10 and 3.13, and builds the frontend. There are no frontend tests or linter: after a UI change, check it in a browser, since a passing build says nothing about rendering. Tests need no device. Both `argus` commands ping and SSH into the devices listed in `.env`. PNG export needs the Graphviz `dot` binary on `PATH`.

## Architecture

ARGUS is moving from command-line tools to a web app. Both start with `app.bootstrap` (settings, logging, SSH compatibility) and collect with `collector.collect_topology(settings, ips)`.

- **Web app** (`argus serve`): `web.create_app` (FastAPI) + `scanner.Scanner` (background thread) + `db.Database` (SQLite). The inventory lives in the database. The scanner collects, diffs with `changes.detect_changes`, and saves state and history in one transaction. `frontend/` (React) is the client; it polls every 3 s in `useArgusData.ts` and does not consume the SSE stream yet.
- **Legacy commands** (`generator`, `monitor`, to be removed once the frontend and history view are done): inventory from `ARGUS_DEVICES`, output through `exporters.export_topology`.

Web app points:

- All routes go on the `api` router, which requires a session; only login is declared on `app`.
- `scanner.status()["version"]` drives the SSE stream: call `scanner.notify()` after any change the UI must reload.
- The stored topology may still contain a just-deleted device until the next scan, so readers filter it with `graph.restrict` against the inventory.
- `detect_changes` compares by device IP, not hostname, and returns nothing when there is no previous topology.
- `frontend/src/api.ts` mirrors the API response shapes; update both sides together. FastAPI's 204 responses can declare JSON with an empty body.
- Node layers are decided in `graph.py` (manual `role`, then hostname words, then link count; the count never yields `core`). `frontend/src/layout.ts` only places them. Schema changes need a migration in `Database.__init__`, since users have an existing database.
- The PNG export (`frontend/src/exportPng.ts`) is client-side and keeps only `ok` nodes.
- Cytoscape forces `position: relative` on its container, which beats Tailwind v4 utilities: size the container with `size-full`, never with `absolute inset-0` (the graph collapses to zero height).
- The UI must work in a lab without Internet access: no external fonts, scripts or images.
- Tests use `TestClient` with a fake `collect` function. It buffers whole responses, so test the endless SSE stream through `web.event_stream`.

Shared points:


- The **topology dict** returned by `collect_topology` is the contract between modules: `{timestamp, devices: {hostname: {ip, device_type, vendor, model, protocol, neighbors: [{name, local_interface, remote_interface}]}}, failed_devices: [ip]}`. It is also the JSON export format, which the monitor reloads as its baseline, so changes must stay compatible with older files.
- A device that fails at any collection step goes to `failed_devices`; it is never reported with an empty neighbor list. For that reason `parse_neighbors` (ntc-templates on `show lldp neighbors detail`) requires the `Total entries displayed` count to match the parsed entries, because the template returns `[]` for empty or invalid input.
- Real lab IOS images omit `Local Intf` from the detail output. `parse_neighbors` then reads `show lldp neighbors` (names cut at 20 characters; with `R B` capabilities the template's port column keeps a leading `B`, hence the last token). A neighbor must never be stored with an empty local interface: both ends of a cable would no longer merge in `graph.build_graph`. Test parser changes against both output formats.
- Devices are collected in a thread pool (`ARGUS_MAX_WORKERS`); results keep the configured order.
- Use `logging`, not `print` (ruff `T20`). Only the `argus` logger hierarchy follows `ARGUS_LOG_LEVEL`; keep Netmiko/Paramiko at `WARNING`, since their debug output can expose secrets. `monitor.py` names its logger explicitly because `__name__` is `__main__` under `python -m`.
- `export_topology` writes the JSON last, so a failed export does not become the monitor's next baseline. A missing `dot` binary only skips the PNG.
- Configuration comes only from environment variables and `.env` (`ARGUS_*`), validated in `config.py`. A new variable also goes in `.env.example` and the README table.
- `ssh_compat.py` rewrites private `paramiko.Transport` class attributes, hence the `paramiko==4.0.0` pin. Call `configure_legacy_ssh` before any connection. Legacy algorithms are off by default.
