"""Initialisation de l'application : configuration, journalisation, SSH."""

import logging
import sys

from argus.config import ConfigError, load_settings
from argus.ssh_compat import configure_legacy_ssh


def setup_logging(level):
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # Seul ARGUS suit le niveau demandé : le DEBUG de Netmiko/Paramiko peut exposer des secrets
    logging.getLogger("argus").setLevel(level)


def bootstrap():
    """Prépare l'exécution et retourne la configuration."""
    try:
        settings = load_settings()
    except ConfigError as e:
        sys.exit(f"Erreur de configuration : {e}")

    setup_logging(settings.log_level)
    configure_legacy_ssh(settings.allow_legacy_ssh)
    return settings
