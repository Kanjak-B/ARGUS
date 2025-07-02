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
]

# ============================================================================
# CREDENTIALS PAR DÉFAUT
# ============================================================================

# Identifiants de connexion par défaut pour les équipements réseau
# Ces credentials seront utilisés pour tous les équipements
DEFAULT_CREDENTIALS = {
    "username": "admin",
    "password": "",
    "secret": "admin"  # Pour les équipements Cisco
}

# ============================================================================
# PARAMÈTRES DE CONNEXION
# ============================================================================

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