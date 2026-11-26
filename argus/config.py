"""Configuration chargée depuis les variables d'environnement et le fichier .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Variable de configuration absente ou invalide."""


@dataclass(frozen=True)
class Settings:
    username: str
    password: str = field(repr=False)
    secret: str = field(repr=False)
    timeout: int
    session_timeout: int
    monitor_interval: int
    allow_legacy_ssh: bool
    max_workers: int
    log_level: str
    admin_password: str = field(repr=False)
    host: str
    port: int
    db_path: Path


def _required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"La variable {name} est obligatoire (voir .env.example)")
    return value


def _positive_int(name, default):
    value = os.getenv(name, "").strip() or str(default)
    if not value.isdecimal() or int(value) == 0:
        raise ConfigError(f"La variable {name} doit être un entier positif")
    return int(value)


def _boolean(name, default):
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"La variable {name} doit valoir true ou false")


def _log_level(name, default):
    value = os.getenv(name, "").strip().upper() or default
    if value not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ConfigError(f"La variable {name} doit valoir DEBUG, INFO, WARNING ou ERROR")
    return value


def load_settings(env_file=PROJECT_ROOT / ".env"):
    """Les variables d'environnement déjà définies priment sur le fichier .env."""
    load_dotenv(env_file)

    # Un chemin relatif est résolu depuis la racine du projet
    db_path = PROJECT_ROOT / (os.getenv("ARGUS_DB_PATH", "").strip() or "data/argus.db")

    return Settings(
        username=_required("ARGUS_USERNAME"),
        password=_required("ARGUS_PASSWORD"),
        secret=os.getenv("ARGUS_SECRET", ""),
        timeout=_positive_int("ARGUS_TIMEOUT", 20),
        session_timeout=_positive_int("ARGUS_SESSION_TIMEOUT", 20),
        monitor_interval=_positive_int("ARGUS_MONITOR_INTERVAL", 60),
        allow_legacy_ssh=_boolean("ARGUS_ALLOW_LEGACY_SSH", False),
        max_workers=_positive_int("ARGUS_MAX_WORKERS", 10),
        log_level=_log_level("ARGUS_LOG_LEVEL", "INFO"),
        admin_password=os.getenv("ARGUS_ADMIN_PASSWORD", ""),
        host=os.getenv("ARGUS_HOST", "").strip() or "127.0.0.1",
        port=_positive_int("ARGUS_PORT", 8000),
        db_path=db_path,
    )
