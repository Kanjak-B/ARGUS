# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ARGUS is a prototype that documents a network's topology: it collects LLDP neighbors from Cisco IOS devices over SSH and exports JSON, Excel and a Graphviz PNG. `README.md` covers setup, configuration variables and known limitations. Comments, console output, documentation and commit messages are in French (`ssh_compat.py` is in English).

## Commands

PowerShell, from the repo root:

```powershell
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"      # dependencies live in pyproject.toml

python -m argus.generator    # one-shot documentation run
python -m argus.monitor      # monitoring loop

ruff check .
ruff format .                # CI runs `ruff format --check .`
python -m unittest discover -s tests -v
python -m unittest tests.test_argus.ChangeDetectionTests.test_lost_link   # single test
```

CI (`.github/workflows/ci.yml`) runs these checks on Python 3.10 and 3.13. Tests need no device. Both `argus` commands ping and SSH into the devices listed in `.env`. PNG export needs the Graphviz `dot` binary on `PATH`.

## Architecture

`generator` and `monitor` are thin orchestrators over the same pipeline: `app.bootstrap` (settings, logging, SSH compatibility) → `collector.collect_topology` → `exporters.export_topology`. The monitor adds `detect_changes` between collection and export, and exports the snapshot it already collected.

- The **topology dict** returned by `collect_topology` is the contract between modules: `{timestamp, devices: {hostname: {ip, device_type, vendor, model, protocol, neighbors: [{name, local_interface, remote_interface}]}}, failed_devices: [ip]}`. It is also the JSON export format, which the monitor reloads as its baseline, so changes must stay compatible with older files.
- A device that fails at any collection step goes to `failed_devices`; it is never reported with an empty neighbor list. For that reason `parse_neighbors` (ntc-templates on `show lldp neighbors detail`) requires the `Total entries displayed` count to match the parsed entries, because the template returns `[]` for empty or invalid input.
- Devices are collected in a thread pool (`ARGUS_MAX_WORKERS`); results keep the configured order.
- Use `logging`, not `print` (ruff `T20`). Only the `argus` logger hierarchy follows `ARGUS_LOG_LEVEL`; keep Netmiko/Paramiko at `WARNING`, since their debug output can expose secrets. `monitor.py` names its logger explicitly because `__name__` is `__main__` under `python -m`.
- `export_topology` writes the JSON last, so a failed export does not become the monitor's next baseline. A missing `dot` binary only skips the PNG.
- Configuration comes only from environment variables and `.env` (`ARGUS_*`), validated in `config.py`. A new variable also goes in `.env.example` and the README table.
- `ssh_compat.py` rewrites private `paramiko.Transport` class attributes, hence the `paramiko==4.0.0` pin. Call `configure_legacy_ssh` before any connection. Legacy algorithms are off by default.
