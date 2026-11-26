# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ARGUS is a lab prototype: a web app that collects LLDP neighbors from Cisco IOS devices over SSH, shows the topology as a graph and reports changes live. `README.md` covers setup, configuration variables, security scope and known limitations. Everything the user sees is in **English** (UI, API errors, history messages, Excel and PNG content), with `en-GB` date formatting. Comments, terminal logs, documentation and commit messages are in French (`ssh_compat.py` is in English).

## Commands

PowerShell, from the repo root:

```powershell
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"      # dependencies live in pyproject.toml

argus serve                  # web app on 127.0.0.1:8000 (API docs at /docs)

ruff check .
ruff format .                # CI runs `ruff format --check .`
python -m unittest discover -s tests -v
python -m unittest tests.test_argus.ChangeDetectionTests.test_lost_and_added_link   # single test
```

Frontend, from `frontend/`:

```powershell
npm install
npm run dev                  # Vite dev server, proxies /api to `argus serve`
npm run build                # type check + build into frontend/dist, served by FastAPI
```

CI (`.github/workflows/ci.yml`) runs the Python checks on 3.10 and 3.13, and builds the frontend. There are no frontend tests or linter: after a UI change, check it in a browser, since a passing build says nothing about rendering. Tests need no device. `argus serve` pings and SSHes into the devices stored in its database; to try the app without a lab, call `web.create_app` with a `Scanner` given a fake `collect` function and a temporary database.

## Architecture

`cli.serve` → `app.bootstrap` (settings, logging, SSH compatibility) → `web.create_app` (FastAPI) + `scanner.Scanner` (background thread) + `db.Database` (SQLite). The scanner reads the inventory from the database, calls `collector.collect_topology(settings, ips)`, diffs with `changes.detect_changes`, and saves state and history in one transaction.

Live updates: `scanner.status()["version"]` drives the SSE stream (`/api/events`), and `frontend/src/useArgusData.ts` refetches everything on each message. Call `scanner.notify()` after any change the UI must reload.

### Backend

- The **topology dict** returned by `collect_topology` is the contract between modules: `{timestamp, devices: {hostname: {ip, device_type, vendor, model, protocol, neighbors: [{name, local_interface, remote_interface}]}}, failed_devices: [ip]}`. It is stored in the database, so changes must stay compatible with stored data.
- A device that fails at any collection step goes to `failed_devices`; it is never reported with an empty neighbor list. For that reason `parse_neighbors` (ntc-templates on `show lldp neighbors detail`) requires the `Total entries displayed` count to match the parsed entries, because the template returns `[]` for empty or invalid input.
- Real lab IOS images omit `Local Intf` from the detail output. `parse_neighbors` then reads `show lldp neighbors` (names cut at 20 characters; with `R B` capabilities the template's port column keeps a leading `B`, hence the last token). A neighbor must never be stored with an empty local interface: both ends of a cable would no longer merge in `graph.build_graph`. Test parser changes against both output formats.
- All routes go on the `api` router, which requires a session; only login is declared on `app`. The frontend is mounted last so it does not hide `/api` or `/docs`.
- The stored topology may still contain a just-deleted device until the next scan, so readers filter it with `graph.restrict` against the inventory.
- History messages are rebuilt on read by `changes.describe(type, details)`, so rewording them also applies to stored entries; every new change type needs a template there.
- `detect_changes` compares by device IP, not hostname, and returns nothing when there is no previous topology.
- JSON and Excel exports are built by `exporters.build_document` from the output of `graph.build_graph`, not from the topology dict, so they match the UI. The "online" view rule exists twice and must stay identical: `graph.online_only` (exports) and `applyView` in `frontend/src/views.ts` (screen and PNG). Layers are assigned before filtering.
- Neighbor names come from the network: Excel cells are forced to string type to prevent formula injection.
- Node layers are decided in `graph.py` (manual `role`, then hostname words, then link count; the count never yields `core`). Schema changes need a migration in `Database.__init__`, since users have an existing database.
- Use `logging`, not `print` (ruff `T20`). Only the `argus` logger hierarchy follows `ARGUS_LOG_LEVEL`; keep Netmiko/Paramiko at `WARNING`, since their debug output can expose secrets.
- Configuration comes only from environment variables and `.env` (`ARGUS_*`), validated in `config.py`. A new variable also goes in `.env.example` and the README table. Device addresses are not configuration: they are managed in the UI.
- `ssh_compat.py` rewrites private `paramiko.Transport` class attributes, hence the `paramiko==4.0.0` pin. Call `configure_legacy_ssh` before any connection. Legacy algorithms are off by default.
- Tests use `TestClient` with a fake `collect` function. It buffers whole responses, so test the endless SSE stream through `web.event_stream`.

### Frontend

- `src/api.ts` mirrors the API response shapes, including change types; update both sides together. FastAPI's 204 responses can declare JSON with an empty body.
- `src/layout.ts` only places nodes in the layers chosen by the backend. The PNG export (`src/exportPng.ts`) is client-side and renders the open view. `TopologyGraph` is remounted per view (`key={view}`) and keeps positions separately for each.
- Cytoscape forces `position: relative` on its container, which beats Tailwind v4 utilities: size the container with `size-full`, never with `absolute inset-0` (the graph collapses to zero height).
- The UI must work in a lab without Internet access: no external fonts, scripts or images.
