"""Ligne de commande : argus serve."""

import argparse
import logging
import sys

import uvicorn

from argus.app import bootstrap
from argus.db import Database
from argus.scanner import Scanner
from argus.web import FRONTEND_DIR, create_app

logger = logging.getLogger("argus.cli")


def serve():
    settings = bootstrap()
    if not settings.admin_password:
        sys.exit("Erreur de configuration : la variable ARGUS_ADMIN_PASSWORD est obligatoire")

    if settings.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "L'interface est exposée sur %s sans HTTPS : réservez cet usage à un lab isolé",
            settings.host,
        )

    if not (FRONTEND_DIR / "index.html").is_file():
        logger.warning(
            "Interface non construite, seule l'API est servie : "
            "lancez « npm install » puis « npm run build » dans frontend/"
        )

    db = Database(settings.db_path)
    app = create_app(settings, db, Scanner(settings, db))
    # Sans ce délai, l'arrêt attendrait la fermeture des flux temps réel ouverts
    uvicorn.run(app, host=settings.host, port=settings.port, timeout_graceful_shutdown=2)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="argus", description="Documentation de topologie réseau")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="démarre l'application web")
    parser.parse_args(argv)
    serve()


if __name__ == "__main__":
    main()
