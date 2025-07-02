"""
Script de surveillance de la topologie réseau
Vérifie périodiquement les changements de topologie via LLDP
"""
# Docstring : décrit le but du script, qui est de surveiller la topologie réseau via LLDP.

import json  # Pour manipuler les fichiers et données JSON
import time  # Pour gérer les temporisations (sleep)
import os  # Pour les opérations système (fichiers, dossiers)
import subprocess  # Pour exécuter des commandes système externes
import glob  # Pour rechercher des fichiers selon un motif
import sys  # Pour accéder à des variables et fonctions système (ex: sys.executable)
import platform  # Pour détecter le système d'exploitation
from datetime import datetime  # Pour manipuler les dates et heures
import logging  # Pour la gestion des logs
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
# Importation de Netmiko pour la connexion SSH aux équipements réseau

from config import (
    DEVICES, 
    SSH_KEY_PATH, 
    SSH_USERNAME,
    SSH_CONFIG,
    TIMEOUT, 
    SESSION_TIMEOUT, 
    DETECTION_COMMANDS
)
# Importation des paramètres de configuration depuis le fichier config.py

class TopologyMonitor:
    # Classe principale pour la surveillance de la topologie réseau

    def __init__(self):
        # Constructeur de la classe
        self.setup_logging()  # Initialise la configuration des logs (ici vide)
        self.topologies_dir = "topologies"  # Dossier où sont stockées les topologies
        self.current_topology = {}  # Dictionnaire pour la topologie courante
        self.last_topology = None  # Dernière topologie connue
        self.failed_devices = set()  # Ensemble des équipements en erreur
        self.load_last_topology()  # Charge la dernière topologie sauvegardée

    def setup_logging(self):
        # Méthode pour configurer le logging (ici vide)
        pass

    def is_device_up(self, ip):
        """
        Vérifie si un équipement réseau est accessible via ping.
        """
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            # Choisit le paramètre de ping selon l'OS (-n pour Windows, -c pour Unix)
            result = subprocess.run(["ping", param, "1", ip], 
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            # Exécute la commande ping, redirige la sortie vers null
            return result.returncode == 0
            # Retourne True si le ping a réussi (code retour 0)
        except Exception:
            return False
            # En cas d'erreur, considère l'équipement comme injoignable

    def get_latest_topology_file(self):
        """Trouve le dernier fichier de topologie JSON dans le dossier topologies"""
        try:
            os.makedirs(self.topologies_dir, exist_ok=True)
            # Crée le dossier s'il n'existe pas
            topology_files = glob.glob(os.path.join(self.topologies_dir, "topology_*.json"))
            # Cherche tous les fichiers de topologie JSON
            if not topology_files:
                print("[INFO] Aucun fichier de topologie précédent trouvé")
                return None
            latest_file = max(topology_files, key=os.path.getmtime)
            # Prend le fichier le plus récent (par date de modification)
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
                    # Charge le contenu JSON du fichier
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
            os.makedirs(self.topologies_dir, exist_ok=True)
            # Crée le dossier s'il n'existe pas
            filename = os.path.join(self.topologies_dir, f"topology_{topology_data['timestamp']}.json")
            # Génère le nom du fichier avec le timestamp
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(topology_data, f, indent=4, ensure_ascii=False)
                # Sauvegarde la topologie au format JSON
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
            # Si aucune topologie précédente, considère qu'il y a un changement

        current_devices = set(current_topology['devices'].keys())
        last_devices = set(self.last_topology['devices'].keys())
        # Récupère les ensembles d'équipements

        new_devices = current_devices - last_devices
        # Détecte les nouveaux équipements
        if new_devices:
            print(f"[ALERTE] Nouveaux équipements détectés: {', '.join(new_devices)}")
            return True

        for device in current_devices & last_devices:
            # Pour chaque équipement présent dans les deux topologies
            current_neighbors = {
                (n['name'], n['local_interface'], n['remote_interface'])
                for n in current_topology['devices'][device]['neighbors']
            }
            last_neighbors = {
                (n['name'], n['local_interface'], n['remote_interface'])
                for n in self.last_topology['devices'][device]['neighbors']
            }
            # Récupère les voisins de chaque équipement

            if current_neighbors != last_neighbors:
                print(f"[ALERTE] Changements détectés dans les connexions de {device}")
                print(f"  Anciennes connexions: {last_neighbors}")
                print(f"  Nouvelles connexions: {current_neighbors}")
                return True
                # Si les voisins ont changé, signale un changement

        print("[INFO] Aucun changement significatif détecté dans la topologie")
        return False

    def execute_ssh_command(self, ip, command):
        """
        Exécute une commande SSH sur un équipement en utilisant subprocess
        Retourne la sortie de la commande ou None en cas d'erreur
        """
        try:
            ssh_cmd = [
                "ssh",
                "-o", "MACs=hmac-sha1,hmac-sha1-96,hmac-md5,hmac-md5-96",
                "-o", "KexAlgorithms=+diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1",
                "-o", "Ciphers=aes128-ctr,aes192-ctr,aes256-ctr,aes128-cbc,3des-cbc",
                "-i", SSH_KEY_PATH,
                f"{SSH_USERNAME}@{ip}",
                command
            ]
            # Prépare la commande SSH avec des options spécifiques de sécurité
            print(f"[DEBUG] Exécution de la commande SSH: {' '.join(ssh_cmd)}")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            # Exécute la commande SSH
            if result.returncode == 0:
                return result.stdout
                # Retourne la sortie si succès
            else:
                print(f"[ERREUR] Commande SSH échouée: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"[ERREUR] Timeout lors de l'exécution de la commande SSH sur {ip}")
            return None
        except Exception as e:
            print(f"[ERREUR] Erreur inattendue lors de l'exécution de la commande SSH sur {ip}: {str(e)}")
            return None

    def get_device_neighbors(self, ip):
        """
        Récupère les voisins LLDP d'un équipement via SSH
        Retourne (hostname, neighbors) ou (None, None) en cas d'erreur
        """
        try:
            device = SSH_CONFIG.copy()
            # Copie la configuration SSH de base
            device['host'] = ip
            # Ajoute l'adresse IP de l'équipement
            print(f"[DEBUG] Tentative de connexion à {ip} avec la clé {SSH_KEY_PATH}")
            print(f"[DEBUG] Configuration SSH: {device}")
            with ConnectHandler(**device) as conn:
                # Établit la connexion SSH
                print(f"[DEBUG] Connexion SSH établie à {ip}")
                conn.enable()
                # Passe en mode enable
                print(f"[DEBUG] Mode enable activé sur {ip}")
                hostname_output = conn.send_command("show running-config | include hostname", 
                                                  expect_string=r"#", 
                                                  read_timeout=20)
                # Récupère le hostname de l'équipement
                print(f"[DEBUG] Sortie hostname: {hostname_output}")
                hostname = "Unknown"
                for line in hostname_output.splitlines():
                    if "hostname" in line.lower():
                        hostname = line.split("hostname")[1].strip()
                        break
                print(f"[DEBUG] Hostname détecté: {hostname}")
                output = conn.send_command("show lldp neighbors", 
                                         expect_string=r"#", 
                                         read_timeout=TIMEOUT)
                # Récupère la liste des voisins LLDP
                print(f"[DEBUG] Sortie LLDP: {output}")
                if "No LLDP neighbors" in output:
                    return hostname, []
                neighbors = []
                for line in output.splitlines():
                    line = line.strip()
                    if not line or any(x in line for x in ["Capability codes:", "Device ID", "Total entries"]):
                        continue
                    if line.startswith("("):
                        continue
                    parts = line.split()
                    if len(parts) >= 4 and not parts[0].startswith("("):
                        neighbor_name = parts[0].split('.')[0]
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
            print(f"[ERREUR] Erreur inattendue pour {ip}: {str(e)}")
            return None, None

    def check_topology_changes(self):
        """Vérifie les changements de topologie et retourne True si des changements sont détectés"""
        topology_data = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "devices": {},
            "failed_devices": list(self.failed_devices)
        }
        print("\n[INFO] Vérification de la topologie...")
        current_failed_devices = set()
        connectivity_changed = False
        for ip in DEVICES:
            try:
                is_pingable = self.is_device_up(ip)
                # Vérifie si l'équipement répond au ping
                if not is_pingable:
                    print(f"[ALERTE] Équipement {ip} ne répond pas au ping")
                    current_failed_devices.add(ip)
                    if ip not in self.failed_devices:
                        connectivity_changed = True
                    continue
                hostname, neighbors = self.get_device_neighbors(ip)
                if hostname and neighbors is not None:
                    short_hostname = hostname.split('.')[0]
                    topology_data["devices"][short_hostname] = {
                        "ip": ip,
                        "neighbors": neighbors
                    }
                    if ip in self.failed_devices:
                        print(f"[INFO] Équipement {ip} ({short_hostname}) est à nouveau accessible")
                        connectivity_changed = True
                        self.failed_devices.remove(ip)
                else:
                    current_failed_devices.add(ip)
                    if ip not in self.failed_devices:
                        connectivity_changed = True
            except Exception as e:
                print(f"[ERREUR] Erreur lors de la vérification de {ip}: {e}")
                current_failed_devices.add(ip)
                if ip not in self.failed_devices:
                    connectivity_changed = True
        self.failed_devices = current_failed_devices
        if topology_data["devices"]:
            changes_detected = self.compare_topologies(topology_data)
            self.save_topology(topology_data)
            self.last_topology = topology_data
            return changes_detected or connectivity_changed
        else:
            if len(self.failed_devices) == len(DEVICES):
                print("[ALERTE] Aucun équipement n'est accessible. Changement majeur de topologie détecté.")
                self.save_topology(topology_data)
                return True
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
                    try:
                        python_executable = sys.executable
                        subprocess.run([python_executable, "ARGUS_network_topology_generator.py"], 
                                     check=True)
                        print("[INFO] Script de documentation terminé avec succès")
                    except subprocess.CalledProcessError as e:
                        print(f"[ERREUR] Le script de documentation a échoué: {e}")
                    except Exception as e:
                        print(f"[ERREUR] Erreur lors du lancement du script: {e}")
                time.sleep(60)
            except KeyboardInterrupt:
                print("\n[INFO] Arrêt de la surveillance...")
                break
            except Exception as e:
                print(f"[ERREUR] Erreur inattendue dans la boucle principale: {e}")
                time.sleep(60)

if __name__ == "__main__":
    monitor = TopologyMonitor()
    monitor.run_monitoring()
# Point d'entrée du script : crée une instance de TopologyMonitor et lance la surveillance en boucle