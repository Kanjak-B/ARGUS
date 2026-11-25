"""Compatibility for legacy SSH algorithms used by isolated labs."""

import logging
import os

import paramiko


_LEGACY_ALGORITHMS = {
    "_preferred_kex": ("diffie-hellman-group1-sha1", "_kex_info"),
    "_preferred_keys": ("ssh-rsa", "_key_info"),
    "_preferred_ciphers": ("aes128-cbc", "_cipher_info"),
    "_preferred_macs": ("hmac-sha1", "_mac_info"),
}
_ALLOW_LEGACY_SSH = os.getenv("ALLOW_LEGACY_SSH", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if _ALLOW_LEGACY_SSH:
    for preference_name, (algorithm, registry_name) in _LEGACY_ALGORITHMS.items():
        registry = getattr(paramiko.Transport, registry_name)
        if algorithm not in registry:
            raise RuntimeError(
                f"{algorithm} is not supported by Paramiko "
                f"{paramiko.__version__}; install Paramiko 4.0.0 in the project "
                "virtual environment to enable legacy SSH for the lab."
            )

        preferences = getattr(paramiko.Transport, preference_name)
        if not preferences or preferences[-1] != algorithm:
            preferences = tuple(item for item in preferences if item != algorithm)
            setattr(paramiko.Transport, preference_name, preferences + (algorithm,))

    logging.getLogger(__name__).warning(
        "Legacy SSH algorithms are enabled for this session; use only in an "
        "isolated lab."
    )
else:
    for preference_name, (algorithm, _) in _LEGACY_ALGORITHMS.items():
        preferences = getattr(paramiko.Transport, preference_name)
        if algorithm in preferences:
            setattr(
                paramiko.Transport,
                preference_name,
                tuple(item for item in preferences if item != algorithm),
            )
