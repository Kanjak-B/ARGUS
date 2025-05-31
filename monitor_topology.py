"""
Script de surveillance de la topologie réseau
Vérifie périodiquement les changements de topologie via LLDP
"""

import json
import time
import subprocess
import os
import glob
import sys
import platform
from datetime import datetime
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from config import DEVICES, DEFAULT_CREDENTIALS, TIMEOUT, SESSION_TIMEOUT, DETECTION_COMMANDS

class TopologyMonitor:
    def __init__(self):
        self.topologies_dir = "topologies"
        self.current_topology = {}
        self.last_topology = None
        self.failed_devices = set()  # Pour suivre les équipements en erreur
        self.load_last_topology()

    def is_device_up(self, ip):
        """
        Vérifie si un équipement réseau est accessible via ping.
        
        Args:
            ip (str): L'adresse IP de l'équipement à tester
            
        Returns:
            bool: True si l'équipement répond au ping, False sinon
        """
        try:
            # Détermine le paramètre à utiliser pour la commande ping selon le système d'exploitation
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            
            # Exécute la commande ping avec un seul paquet
            result = subprocess.run(["ping", param, "1", ip], 
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            
            return result.returncode == 0
        except Exception:
            return False

    def get_latest_topology_file(self):
        """Trouve le dernier fichier de topologie JSON dans le dossier topologies"""
        try:
            # Créer le dossier s'il n'existe pas
            os.makedirs(self.topologies_dir, exist_ok=True)
            
            # Chercher tous les fichiers JSON de topologie
            topology_files = glob.glob(os.path.join(self.topologies_dir, "topology_*.json"))
            
            if not topology_files:
                print("[INFO] Aucun fichier de topologie précédent trouvé")
                return None
                
            # Trier les fichiers par date de modification (le plus récent en dernier)
            latest_file = max(topology_files, key=os.path.getmtime)
            print(f"[INFO] Dernier fichier de topologie trouvé: {latest_file}")
            return latest_file
            
        except Exception as e:
            print(f"[ERREUR] Impossible de trouver le dernier fichier de topologie: {e}")
            return None

    def load_last_topology(self):
        """Charge la dernière topologie connue depuis le dernier fichier JSON"""
        try:
            latest_file = self.get_latest_topology_file()
            if latest_file:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    self.last_topology = json.load(f)
                    print(f"[INFO] Topologie précédente chargée depuis {latest_file}")
                    print(f"[INFO] Timestamp de la dernière topologie: {self.last_topology.get('timestamp', 'inconnu')}")
            else:
                print("[INFO] Aucune topologie précédente trouvée")
                self.last_topology = None
        except Exception as e:
            print(f"[ERREUR] Impossible de charger la topologie précédente: {e}")
            self.last_topology = None

    def save_topology(self, topology_data):
        """Sauvegarde la topologie actuelle dans un nouveau fichier JSON"""
        try:
            # Créer le dossier topologies s'il n'existe pas
            os.makedirs(self.topologies_dir, exist_ok=True)
            
            # Générer le nom du fichier avec le timestamp
            filename = os.path.join(self.topologies_dir, f"topology_{topology_data['timestamp']}.json")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(topology_data, f, indent=4, ensure_ascii=False)
            print(f"[INFO] Topologie sauvegardée dans {filename}")
        except Exception as e:
            print(f"[ERREUR] Impossible de sauvegarder la topologie: {e}")

    def compare_topologies(self, current_topology):
        """
        Compare la topologie actuelle avec la dernière topologie connue
        Retourne True si des changements significatifs sont détectés
        """
        if not self.last_topology:
            print("[INFO] Pas de topologie précédente pour comparaison")
            return True

        # Extraire les ensembles d'équipements
        current_devices = set(current_topology['devices'].keys())
        last_devices = set(self.last_topology['devices'].keys())

        # Vérifier les nouveaux équipements
        new_devices = current_devices - last_devices
        if new_devices:
            print(f"[ALERTE] Nouveaux équipements détectés: {', '.join(new_devices)}")
            return True

        # Vérifier les changements dans les connexions pour chaque équipement existant
        for device in current_devices & last_devices:  # Intersection des deux ensembles
            current_neighbors = {
                (n['name'], n['local_interface'], n['remote_interface'])
                for n in current_topology['devices'][device]['neighbors']
            }
            last_neighbors = {
                (n['name'], n['local_interface'], n['remote_interface'])
                for n in self.last_topology['devices'][device]['neighbors']
            }

            # Vérifier les changements dans les connexions
            if current_neighbors != last_neighbors:
                print(f"[ALERTE] Changements détectés dans les connexions de {device}")
                print(f"  Anciennes connexions: {last_neighbors}")
                print(f"  Nouvelles connexions: {current_neighbors}")
                return True

        print("[INFO] Aucun changement significatif détecté dans la topologie")
        return False

    def get_device_neighbors(self, ip):
        """
        Récupère les voisins LLDP d'un équipement via SSH
        Retourne (hostname, neighbors) ou (None, None) en cas d'erreur
        """
        try:
            # Configuration de la connexion SSH
            device = {
                'device_type': 'cisco_ios',
                'host': ip,
                'username': DEFAULT_CREDENTIALS["username"],
                'password': DEFAULT_CREDENTIALS["password"],
                'secret': DEFAULT_CREDENTIALS['secret'],
                'timeout': TIMEOUT,
                'session_timeout': SESSION_TIMEOUT
            }

            # Connexion SSH
            with ConnectHandler(**device) as conn:
                conn.enable()
                
                # Récupération du hostname
                hostname_output = conn.send_command("show running-config | include hostname", 
                                                  expect_string=r"#", 
                                                  read_timeout=20)
                hostname = "Unknown"
                for line in hostname_output.splitlines():
                    if "hostname" in line.lower():
                        hostname = line.split("hostname")[1].strip()
                        break

                # Récupération des voisins LLDP
                output = conn.send_command("show lldp neighbors", 
                                         expect_string=r"#", 
                                         read_timeout=TIMEOUT)

                if "No LLDP neighbors" in output:
                    return hostname, []

                # Parsing des voisins
                neighbors = []
                for line in output.splitlines():
                    line = line.strip()
                    if not line or any(x in line for x in ["Capability codes:", "Device ID", "Total entries"]):
                        continue
                    if line.startswith("("):
                        continue

                    parts = line.split()
                    if len(parts) >= 4 and not parts[0].startswith("("):
                        neighbor_name = parts[0].split('.')[0]  # Suppression du domaine
                        local_intf = parts[1]
                        remote_intf = parts[-1]
                        
                        if not any(x in neighbor_name for x in ["Router", "Bridge", "Telephone", "WLAN", "Repeater", "Station"]):
                            neighbors.append({
                                "name": neighbor_name,
                                "local_interface": local_intf,
                                "remote_interface": remote_intf
                            })

                return hostname, neighbors

        except (NetmikoAuthenticationException, NetmikoTimeoutException) as e:
            print(f"[ERREUR] Problème de connexion SSH à {ip}: {e}")
            return None, None
        except Exception as e:
            print(f"[ERREUR] Erreur inattendue pour {ip}: {e}")
            return None, None

    def check_topology_changes(self):
        """Vérifie les changements de topologie et retourne True si des changements sont détectés"""
        topology_data = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "devices": {},
            "failed_devices": list(self.failed_devices)  # Inclure la liste des équipements en erreur
        }

        print("\n[INFO] Vérification de la topologie...")
        current_failed_devices = set()  # Pour suivre les échecs de cette vérification
        connectivity_changed = False  # Pour suivre les changements de connectivité
        
        for ip in DEVICES:
            try:
                # Vérifier d'abord si l'équipement répond au ping
                is_pingable = self.is_device_up(ip)
                
                if not is_pingable:
                    print(f"[ALERTE] Équipement {ip} ne répond pas au ping")
                    current_failed_devices.add(ip)
                    # Si l'équipement était accessible avant, c'est un changement
                    if ip not in self.failed_devices:
                        connectivity_changed = True
                    continue

                # Si le ping fonctionne, essayer la connexion SSH
                hostname, neighbors = self.get_device_neighbors(ip)
                if hostname and neighbors is not None:
                    short_hostname = hostname.split('.')[0]
                    
                    # Stockage des informations de l'équipement
                    topology_data["devices"][short_hostname] = {
                        "ip": ip,
                        "neighbors": neighbors
                    }
                    
                    # Si l'équipement était précédemment en erreur, c'est un changement
                    if ip in self.failed_devices:
                        print(f"[INFO] Équipement {ip} ({short_hostname}) est à nouveau accessible")
                        connectivity_changed = True
                        self.failed_devices.remove(ip)
                else:
                    current_failed_devices.add(ip)
                    # Si l'équipement était accessible avant, c'est un changement
                    if ip not in self.failed_devices:
                        connectivity_changed = True
            except Exception as e:
                print(f"[ERREUR] Erreur lors de la vérification de {ip}: {e}")
                current_failed_devices.add(ip)
                # Si l'équipement était accessible avant, c'est un changement
                if ip not in self.failed_devices:
                    connectivity_changed = True

        # Mettre à jour la liste des équipements en erreur
        self.failed_devices = current_failed_devices

        # Si nous avons des données valides, comparer avec la dernière topologie
        if topology_data["devices"]:
            changes_detected = self.compare_topologies(topology_data)
            
            # Sauvegarder la nouvelle topologie
            self.save_topology(topology_data)
            
            # Mettre à jour la dernière topologie connue
            self.last_topology = topology_data
            
            # Retourner True si des changements de topologie OU de connectivité sont détectés
            return changes_detected or connectivity_changed
        else:
            # Si aucun équipement n'est accessible, c'est un changement majeur
            if len(self.failed_devices) == len(DEVICES):
                print("[ALERTE] Aucun équipement n'est accessible. Changement majeur de topologie détecté.")
                self.save_topology(topology_data)
                return True
            # Si certains équipements sont inaccessibles, c'est aussi un changement
            elif connectivity_changed:
                print("[ALERTE] Changements de connectivité détectés.")
                self.save_topology(topology_data)
                return True
            else:
                print("[ERREUR] Aucune donnée de topologie valide n'a pu être récupérée")
                return False

    def run_monitoring(self):
        """Exécute la surveillance en boucle"""
        print("[INFO] Démarrage de la surveillance de la topologie...")
        
        while True:
            try:
                if self.check_topology_changes():
                    print("[ALERTE] Changements détectés dans la topologie!")
                    print("[INFO] Lancement du script de documentation...")
                    
                    # Lancement du script de documentation
                    try:
                        # Utiliser le même interpréteur Python que le script actuel
                        python_executable = sys.executable
                        subprocess.run([python_executable, "ARGUS_network_topology_generator.py"], 
                                     check=True)
                        print("[INFO] Script de documentation terminé avec succès")
                    except subprocess.CalledProcessError as e:
                        print(f"[ERREUR] Le script de documentation a échoué: {e}")
                    except Exception as e:
                        print(f"[ERREUR] Erreur lors du lancement du script: {e}")
                
                # Attente de 60 secondes avant la prochaine vérification
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n[INFO] Arrêt de la surveillance...")
                break
            except Exception as e:
                print(f"[ERREUR] Erreur inattendue dans la boucle principale: {e}")
                time.sleep(60)  # Attente avant de réessayer

if __name__ == "__main__":
    monitor = TopologyMonitor()
    monitor.run_monitoring() 