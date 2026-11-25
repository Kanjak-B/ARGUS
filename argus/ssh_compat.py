"""Compatibility for legacy SSH algorithms used by isolated labs."""

import logging

import paramiko

_LEGACY_ALGORITHMS = {
    "_preferred_kex": ("diffie-hellman-group1-sha1", "_kex_info"),
    "_preferred_keys": ("ssh-rsa", "_key_info"),
    "_preferred_ciphers": ("aes128-cbc", "_cipher_info"),
    "_preferred_macs": ("hmac-sha1", "_mac_info"),
}


def configure_legacy_ssh(allow):
    """Active ou retire les algorithmes obsolètes. À appeler avant toute connexion."""
    for preference_name, (algorithm, registry_name) in _LEGACY_ALGORITHMS.items():
        if allow and algorithm not in getattr(paramiko.Transport, registry_name):
            raise RuntimeError(
                f"{algorithm} is not supported by Paramiko "
                f"{paramiko.__version__}; install Paramiko 4.0.0 in the project "
                "virtual environment to enable legacy SSH for the lab."
            )

        preferences = tuple(
            item for item in getattr(paramiko.Transport, preference_name) if item != algorithm
        )
        if allow:
            preferences += (algorithm,)
        setattr(paramiko.Transport, preference_name, preferences)

    if allow:
        logging.getLogger(__name__).warning(
            "Legacy SSH algorithms are enabled for this session; use only in an isolated lab."
        )
