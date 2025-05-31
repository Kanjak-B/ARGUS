import subprocess
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
import platform
from tabulate import tabulate
from collections import defaultdict

# Liste des IP
devices = [
    "10.103.0.10",
    "10.103.0.11",
    "10.103.0.100",
    "10.103.0.254"
]

# Credentials SSH
username = "admin"
password = "admin"
admin_password = "admin"  # pour le mode enable

def is_device_up(ip):
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(["ping", param, "1", ip], stdout=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False

def get_device_info(ip):
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': username,
        'password': password,
        'secret': admin_password,
        'timeout': 20,  # Augmenter le timeout
        'session_timeout': 20
    }
    
    try:
        conn = ConnectHandler(**device)
        conn.enable()
        
        # Récupérer le hostname
        hostname_output = conn.send_command("show running-config | include hostname", expect_string=r"#", read_timeout=20)
        hostname = "Unknown"
        for line in hostname_output.splitlines():
            if "hostname" in line.lower():
                hostname = line.split("hostname")[1].strip()
                break
        
        # Essayer CDP d'abord
        output = conn.send_command("show cdp neighbors", expect_string=r"#", read_timeout=20)
        protocol = "CDP"
        
        if "Invalid input" in output or "CDP is not enabled" in output:
            # Essayer LLDP si CDP ne fonctionne pas
            output = conn.send_command("show lldp neighbors", expect_string=r"#", read_timeout=20)
            protocol = "LLDP"
            if "Invalid input" in output or "LLDP is not enabled" in output:
                return None, None, None
        
        # Parser les voisins
        neighbors = []
        lines = output.splitlines()
        start_parsing = False
        
        for line in lines:
            if "Device ID" in line:
                start_parsing = True
                continue
                
            if start_parsing and line.strip():
                parts = line.split()
                if len(parts) >= 2 and not any(x in parts[0].lower() for x in ['device', 'capability', 'total']):
                    # Extraire le nom complet du voisin
                    neighbor = parts[0]
                    # Si le nom contient un point, prendre tout ce qui est avant le point
                    if '.' in neighbor:
                        neighbor = neighbor.split('.')[0]
                    # Si le nom contient un espace, prendre tout ce qui est avant l'espace
                    if ' ' in neighbor:
                        neighbor = neighbor.split(' ')[0]
                    
                    # Extraire l'interface locale et distante
                    local_intf = ' '.join(parts[1:3]) if len(parts) > 2 else parts[1]
                    remote_intf = ' '.join(parts[-2:]) if len(parts) > 3 else parts[-1]
                    neighbors.append([neighbor, local_intf, remote_intf])
        
        conn.disconnect()
        return hostname, neighbors, protocol
        
    except Exception as e:
        print(f"Erreur pour {ip}: {e}")
        return None, None, None

def create_network_map():
    print("\n🔍 Création de la cartographie réseau...\n")
    
    # Dictionnaire pour stocker les informations de chaque équipement
    network_map = defaultdict(list)
    
    # Collecter les informations de tous les équipements
    for ip in devices:
        if is_device_up(ip):
            hostname, neighbors, protocol = get_device_info(ip)
            if hostname and neighbors:
                network_map[hostname] = {
                    'ip': ip,
                    'protocol': protocol,
                    'neighbors': neighbors
                }
    
    # Créer le tableau de la topologie
    topology = []
    for device, info in network_map.items():
        for neighbor in info['neighbors']:
            topology.append([
                device,
                info['ip'],
                neighbor[0],  # nom du voisin
                neighbor[1],  # interface locale
                neighbor[2],  # interface distante
                info['protocol']
            ])
    
    # Afficher la topologie
    if topology:
        print("Topologie du réseau:")
        print(tabulate(
            topology,
            headers=["Équipement", "IP", "Voisin", "Interface Locale", "Interface Distante", "Protocole"],
            tablefmt="simple"  # Utiliser un format plus simple
        ))
    else:
        print("Aucune information de topologie trouvée.")

# Exécuter la cartographie
create_network_map()
