"""Surveille la topologie et regénère la documentation à chaque changement.

Usage : python -m argus.monitor
"""

import logging
import time

from argus.app import bootstrap, require_devices
from argus.changes import detect_changes
from argus.collector import collect_topology
from argus.exporters import export_topology, load_latest_json

# Nom fixe : avec python -m, __name__ vaut "__main__" et sortirait de la hiérarchie argus
logger = logging.getLogger("argus.monitor")


def run_cycle(previous, settings):
    """Exécute une vérification et retourne la nouvelle topologie de référence."""
    current = collect_topology(settings, settings.devices)
    changes = detect_changes(previous, current)
    if previous is not None and not changes:
        logger.info("Aucun changement détecté")
        return previous

    for change in changes:
        logger.warning("%s", change["message"])
    export_topology(current, settings.output_dir)
    return current


def main():
    settings = bootstrap()
    require_devices(settings)
    previous = load_latest_json(settings.output_dir)
    logger.info("Démarrage de la surveillance de la topologie")

    try:
        while True:
            try:
                previous = run_cycle(previous, settings)
            except Exception as e:  # la surveillance doit survivre à un cycle en échec
                logger.error("Erreur inattendue pendant la vérification : %s", e)
                logger.debug("Détail de l'erreur", exc_info=True)
            time.sleep(settings.monitor_interval)
    except KeyboardInterrupt:
        logger.info("Arrêt de la surveillance")


if __name__ == "__main__":
    main()
