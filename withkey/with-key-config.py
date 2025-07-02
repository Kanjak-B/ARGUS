# ============================================================================
# CONFIGURATION DES ÉQUIPEMENTS
# ============================================================================

# Liste des adresses IP des équipements réseau à interroger
# L'administrateur n'a qu'à ajouter ou retirer des IP ici
DEVICES = [
    "10.103.0.10",
    "10.103.0.11",
    "10.103.0.12",
    "10.103.0.13",
    "10.103.0.14",
    "10.103.0.100",
    "10.103.0.254"
]

# ============================================================================
# PARAMÈTRES DE CONNEXION SSH
# ============================================================================

# Chemin vers la clé privée SSH
SSH_KEY_PATH = r"C:\Users\kanja\.ssh\id_rsa"

# Nom d'utilisateur SSH par défaut
SSH_USERNAME = "admin"

# Paramètres de connexion SSH
SSH_CONFIG = {
    "device_type": "cisco_ios",
    "username": SSH_USERNAME,
    "use_keys": True,
    "key_file": SSH_KEY_PATH,
    "timeout": 20,
    "session_timeout": 20,
    "auth_timeout": 20,
    "banner_timeout": 20,
    "blocking_timeout": 20,
    "session_log": "netmiko_session.log",
    "fast_cli": False,
    "global_delay_factor": 2,
    "ssh_config_file": None,  # Désactive le fichier de config SSH par défaut
    "allow_auto_change": True,
    "default_enter": "\r\n",
    "conn_timeout": 20,
    "keepalive": 30,
    "ssh_strict": False,  # Permet des algorithmes plus anciens
    "auth_protocol": "ssh_keys",  # Force l'utilisation des clés SSH
    "ssh_config_file": None,  # Désactive le fichier de config SSH par défaut
    "use_keys": True,  # Force l'utilisation des clés
    "key_file": SSH_KEY_PATH,  # Chemin vers la clé privée
    "allow_agent": False,  # Désactive l'agent SSH
    "hostkey_verify": False,  # Désactive la vérification de l'empreinte de l'hôte
    "look_for_keys": False,  # Ne cherche pas d'autres clés
    "disabled_algorithms": {
        "pubkeys": ["rsa-sha2-256", "rsa-sha2-512"],
        "kex": ["diffie-hellman-group-exchange-sha256", "diffie-hellman-group16-sha512", "diffie-hellman-group18-sha512", "sntrup761x25519-sha512@openssh.com", "curve25519-sha256", "curve25519-sha256@libssh.org", "ecdh-sha2-nistp256", "ecdh-sha2-nistp384", "ecdh-sha2-nistp521"],
        "ciphers": ["aes128-gcm@openssh.com", "aes256-gcm@openssh.com", "chacha20-poly1305@openssh.com"],
        "macs": ["umac-64-etm@openssh.com", "umac-128-etm@openssh.com", "hmac-sha2-256-etm@openssh.com", "hmac-sha2-512-etm@openssh.com", "hmac-sha1-etm@openssh.com", "umac-64@openssh.com", "umac-128@openssh.com", "hmac-sha2-256", "hmac-sha2-512", "hmac-sha1"]
    }
}

# Délais d'attente pour les connexions SSH (en secondes)
TIMEOUT = 20
SESSION_TIMEOUT = 20

# ============================================================================
# COMMANDES DE DÉTECTION
# ============================================================================

# Commandes pour détecter le type d'équipement et récupérer les voisins LLDP
DETECTION_COMMANDS = [
    {
        "command": "show version",
        "device_type": "cisco_ios",
        "vendor": "Cisco",
        "model_pattern": r"Cisco.*Software.*Version",
        "hostname_pattern": r"hostname\s+(\S+)",
        "neighbors_cmd": "show lldp neighbors",
        "neighbors_alt_cmd": "show lldp neighbors detail",  # Commande alternative avec plus de détails
        "neighbors_parse": {
            "protocol": "LLDP",
            "alt_protocol": "LLDP",
            "device_id": "Device ID:",
            "local_intf": "Local Interface:",
            "remote_intf": "Port ID:"
        }
    }
] 