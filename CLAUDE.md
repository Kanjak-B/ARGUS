# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Off-limits directories

Do not read the contents of `How to do it/`, `old scripts/` or `withkey/` (rule from `AGENTS.md`). Exclude them from repo-wide searches too.

## Project

ARGUS documents a network's topology (access and distribution layers): it collects LLDP neighbors from Cisco IOS devices over SSH and exports JSON, Excel and a Graphviz PNG. It is tested on GNS3 labs. Comments, console output and commit messages are in French.

## Commands

PowerShell, from the repo root (`topologies/` and the generator script are resolved relative to the working directory):

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

python monitor_topology.py                  # 60 s monitoring loop
python ARGUS_network_topology_generator.py  # one-shot documentation run

$env:ALLOW_LEGACY_SSH = "false"             # disable legacy SSH algorithms
```

PNG rendering also needs the Graphviz system binary (`dot`) on `PATH`.

There is no build, linter or test suite. For a syntax check that contacts no device:

```powershell
python -m py_compile config.py ssh_compat.py monitor_topology.py ARGUS_network_topology_generator.py
```

Both entry scripts ping and SSH into the IPs in `config.DEVICES`. The generator calls `create_network_map()` at module level, so merely importing it starts a live run.

## Architecture

- `config.py`: device IPs, shared credentials, timeouts, and `DETECTION_COMMANDS` (per-platform detection regex and LLDP commands).
- `ssh_compat.py`: patches `paramiko.Transport` algorithm preferences as an import side effect. **Import it before `netmiko`.** `ALLOW_LEGACY_SSH` defaults to `true`, which appends obsolete algorithms for isolated labs; `false` removes them. It depends on private Paramiko attributes, hence the `paramiko==4.0.0` pin.
- `monitor_topology.py`: `TopologyMonitor` polls the devices, compares the result with the last known topology and connectivity state, and runs the generator as a subprocess on any change. The generator then queries all the devices again; no data is passed between the two.
- `ARGUS_network_topology_generator.py`: full collection, then console table, `.xlsx`, `.json` and `.png`. In the graph, nodes with more than one connection are treated as distribution switches and the others as access switches.
- `main.py` is the unused PyCharm template.

Points that span both scripts:

- Ping, SSH connection and LLDP table parsing are **duplicated**, not shared. Apply collection or parsing fixes to both. Only the generator reads `DETECTION_COMMANDS`; the monitor hardcodes `cisco_ios` and its commands.
- Both write `topologies/topology_<timestamp>.json`. At startup the monitor loads the newest one by modification time, whichever script wrote it, so keep `devices.<hostname>.neighbors[].{name, local_interface, remote_interface}` compatible. The generator adds device metadata; the monitor adds `failed_devices`.
- The monitor saves a JSON file on every cycle that reaches at least one device, even without changes. `compare_topologies` does not report removed devices; the connectivity tracking in `check_topology_changes` covers failures.

## Known limitations

- The generator does not create `topologies/`; a direct run on a fresh clone fails at export unless the folder exists.
- The parser expects the tabular `show lldp neighbors` output. The `detail` fallback goes through the same parser, and `neighbors_parse` is not used.
- `model_pattern` is re-applied to the neighbor output instead of `show version`, so `model` is normally `Unknown`.

## Security

- The root scripts use **password** authentication from `DEFAULT_CREDENTIALS` in the tracked `config.py`, although `README.md` describes SSH-key-only authentication. The code is authoritative. Do not print these values or add more secrets to tracked files.
- `netmiko_session.log` is tracked despite the `*.log` ignore rule. Session logs can contain sensitive device data.
