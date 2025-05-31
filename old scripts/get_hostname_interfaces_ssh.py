import subprocess
import platform
import paramiko
import time

# Liste des IP
devices = ["10.103.0.10",
           "10.103.0.11",
           "10.103.0.100",
           "10.103.0.254"]

# Credentials SSH
username = "admin"
password = "admin"

def ping(ip):
    """
    Fonction pour faire un ping vers une IP
    Retourne True si le ping réussit, False sinon
    """
    # Paramètre pour Windows (-n) ou Linux (-c)
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    # Construction de la commande
    command = ['ping', param, '1', ip]
    
    # Exécution du ping
    return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def get_interfaces(ip):
    """
    Fonction pour se connecter en SSH et récupérer les interfaces
    """
    try:
        # Création de la connexion SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, look_for_keys=False, allow_agent=False)

        # Ouverture d'un shell interactif
        shell = ssh.invoke_shell()
        time.sleep(1)
        shell.recv(1000)

        # Envoi des commandes
        shell.send("terminal length 0\n")
        time.sleep(1)
        shell.send("enable\n")
        time.sleep(1)
        shell.send(f"{password}\n")
        time.sleep(1)
        shell.send("show ip interface brief\n")
        time.sleep(2)

        # Lecture de la sortie
        output = ""
        while shell.recv_ready():
            output += shell.recv(5000).decode()
            time.sleep(0.5)

        print(f"\n=== Interfaces pour {ip} ===")
        print(output)
        print("=" * 50)

        ssh.close()
    except Exception as e:
        print(f"{ip} : Erreur SSH - {e}")

# Test de chaque IP
for ip in devices:
    if ping(ip):
        print(f"{ip} : UP")
        get_interfaces(ip)
    else:
        print(f"{ip} : DOWN")
