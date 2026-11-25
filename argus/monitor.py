"""Surveille la topologie et regénère la documentation à chaque changement.

Usage : python -m argus.monitor
"""

import logging
import time

from argus.app import bootstrap
from argus.collector import collect_topology
from argus.exporters import export_topology, load_latest_json

# Nom fixe : avec python -m, __name__ vaut "__main__" et sortirait de la hiérarchie argus
logger = logging.getLogger("argus.monitor")


def _neighbor_set(device):
    return {(n["name"], n["local_interface"], n["remote_interface"]) for n in device["neighbors"]}


def detect_changes(previous, current):
    """Retourne la description des changements entre deux topologies."""
    if previous is None:
        return ["Pas de topologie précédente"]

    changes = []
    old, new = previous["devices"], current["devices"]

    changes += [f"Nouvel équipement : {name}" for name in sorted(new.keys() - old.keys())]
    changes += [f"Équipement disparu : {name}" for name in sorted(old.keys() - new.keys())]
    changes += [
        f"Connexions modifiées sur {name}"
        for name in sorted(old.keys() & new.keys())
        if _neighbor_set(old[name]) != _neighbor_set(new[name])
    ]

    if set(previous.get("failed_devices", [])) != set(current["failed_devices"]):
        failed = ", ".join(current["failed_devices"]) or "aucun"
        changes.append(f"Équipements en échec : {failed}")

    return changes


def run_cycle(previous, settings):
    """Exécute une vérification et retourne la nouvelle topologie de référence."""
    current = collect_topology(settings)
    changes = detect_changes(previous, current)
    if not changes:
        logger.info("Aucun changement détecté")
        return previous

    for change in changes:
        logger.warning("%s", change)
    export_topology(current, settings.output_dir)
    return current


def main():
    settings = bootstrap()
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
