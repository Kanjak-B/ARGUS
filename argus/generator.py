"""Collecte la topologie une fois et génère la documentation.

Usage : python -m argus.generator
"""

from argus.app import bootstrap, require_devices
from argus.collector import collect_topology
from argus.exporters import export_topology


def main():
    settings = bootstrap()
    require_devices(settings)
    export_topology(collect_topology(settings, settings.devices), settings.output_dir)


if __name__ == "__main__":
    main()
