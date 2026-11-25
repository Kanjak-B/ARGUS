"""Collecte la topologie une fois et génère la documentation.

Usage : python -m argus.generator
"""

from argus.app import bootstrap
from argus.collector import collect_topology
from argus.exporters import export_topology


def main():
    settings = bootstrap()
    export_topology(collect_topology(settings), settings.output_dir)


if __name__ == "__main__":
    main()
