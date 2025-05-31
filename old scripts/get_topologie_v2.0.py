import subprocess
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
import platform
from tabulate import tabulate
from collections import defaultdict

# Liste des IP
devices = [
    "10.103.0.10",
    # "10.103.0.11",
    "10.103.0.100",
    # "10.103.0.254"
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
    print(f"\nTentative de connexion à {ip}...")
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': username,
        'password': password,
        'secret': admin_password,
        'timeout': 20,
        'session_timeout': 20
    }
    
    try:
        print(f"Connexion SSH en cours...")
        conn = ConnectHandler(**device)
        print(f"Connexion SSH réussie, passage en mode enable...")
        conn.enable()
        
        # Récupérer le hostname
        print(f"Récupération du hostname...")
        hostname_output = conn.send_command("show running-config | include hostname", expect_string=r"#", read_timeout=20)
        hostname = "Unknown"
        for line in hostname_output.splitlines():
            if "hostname" in line.lower():
                hostname = line.split("hostname")[1].strip()
                break
        print(f"Hostname trouvé: {hostname}")
        
        # Essayer CDP d'abord
        print(f"Tentative de récupération des voisins CDP...")
        output = conn.send_command("show cdp neighbors detail", expect_string=r"#", read_timeout=20)
        protocol = "CDP"
        
        if "Invalid input" in output or "CDP is not enabled" in output:
            print(f"CDP non disponible, tentative avec LLDP...")
            # Essayer LLDP si CDP ne fonctionne pas
            output = conn.send_command("show lldp neighbors detail", expect_string=r"#", read_timeout=20)
            protocol = "LLDP"
            if "Invalid input" in output or "LLDP is not enabled" in output:
                print(f"Ni CDP ni LLDP ne sont disponibles sur {ip}")
                return None, None, None
        
        print(f"Protocole utilisé: {protocol}")
        print(f"Réponse brute du protocole:\n{output}")
        
        # Parser les voisins
        neighbors = []
        current_neighbor = None
        current_local_intf = None
        current_remote_intf = None
        
        for line in output.splitlines():
            line = line.strip()
            
            if protocol == "CDP":
                if "Device ID:" in line:
                    if current_neighbor and current_local_intf and current_remote_intf:
                        neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
                    current_neighbor = line.split("Device ID:")[1].strip()
                    if '.' in current_neighbor:
                        current_neighbor = current_neighbor.split('.')[0]
                    if ' ' in current_neighbor:
                        current_neighbor = current_neighbor.split(' ')[0]
                elif "Interface:" in line and "Port ID (outgoing port):" in line:
                    # Les deux infos sont sur la même ligne
                    parts = line.split(',')
                    current_local_intf = parts[0].split("Interface:")[1].strip()
                    current_remote_intf = parts[1].split("Port ID (outgoing port):")[1].strip()
                    if current_neighbor and current_local_intf and current_remote_intf:
                        neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
                        current_neighbor = None
                        current_local_intf = None
                        current_remote_intf = None
                elif "Interface:" in line:
                    current_local_intf = line.split("Interface:")[1].strip()
                elif "Port ID (outgoing port):" in line:
                    current_remote_intf = line.split("Port ID (outgoing port):")[1].strip()
                    if current_neighbor and current_local_intf and current_remote_intf:
                        neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
                        current_neighbor = None
                        current_local_intf = None
                        current_remote_intf = None
            
            elif protocol == "LLDP":
                if "System Name:" in line:
                    # Si on a déjà un voisin complet, on l'ajoute
                    if current_neighbor and current_local_intf and current_remote_intf:
                        neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
                    current_neighbor = line.split("System Name:")[1].strip()
                elif "Local Interface:" in line:
                    current_local_intf = line.split("Local Interface:")[1].strip()
                elif "Remote Interface:" in line:
                    current_remote_intf = line.split("Remote Interface:")[1].strip()
                    # Une fois qu'on a toutes les infos, on ajoute le voisin
                    if current_neighbor and current_local_intf:
                        neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
                        # Réinitialiser pour le prochain voisin
                        current_neighbor = None
                        current_local_intf = None
                        current_remote_intf = None
        
        # Ajouter le dernier voisin s'il est complet
        if current_neighbor and current_local_intf and current_remote_intf:
            neighbors.append([current_neighbor, current_local_intf, current_remote_intf])
        
        print(f"Nombre de voisins trouvés: {len(neighbors)}")
        conn.disconnect()
        return hostname, neighbors, protocol
        
    except NetmikoAuthenticationException:
        print(f"Erreur d'authentification SSH pour {ip}")
        return None, None, None
    except NetmikoTimeoutException:
        print(f"Timeout de connexion SSH pour {ip}")
        return None, None, None
    except Exception as e:
        print(f"Erreur inattendue pour {ip}: {str(e)}")
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
            tablefmt="simple"
        ))
        
        # Afficher un résumé des connexions
        print("\nRésumé des connexions:")
        connections = defaultdict(set)
        for row in topology:
            device = row[0]
            neighbor = row[2]
            connections[device].add(neighbor)
        
        for device, neighbors in connections.items():
            print(f"{device} est connecté à: {', '.join(neighbors)}")
    else:
        print("Aucune information de topologie trouvée.")

# Exécuter la cartographie
create_network_map()
