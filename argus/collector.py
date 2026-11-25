"""Collecte des voisins LLDP : ping, connexion SSH et analyse des sorties."""

import logging
import platform
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from netmiko import ConnectHandler
from ntc_templates.parse import parse_output

DEVICE_TYPE = "cisco_ios"
VENDOR = "Cisco"
PROTOCOL = "LLDP"
MODEL_PATTERN = r"Cisco.*Software.*Version"
NEIGHBORS_COMMAND = "show lldp neighbors detail"
TABLE_COMMAND = "show lldp neighbors"

logger = logging.getLogger(__name__)


class CollectionError(Exception):
    """L'équipement répond mais ses informations sont inexploitables."""


def short_name(hostname):
    """Retire le domaine d'un nom d'équipement."""
    return hostname.split(".")[0]


def is_reachable(ip):
    """Vérifie par un ping que l'équipement est accessible."""
    count_flag = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(
            ["ping", count_flag, "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def parse_hostname(output):
    match = re.search(r"^\s*hostname\s+(\S+)", output, re.MULTILINE)
    return match.group(1) if match else "Unknown"


def _find_local_interface(rows, name, remote_interface):
    """Retrouve un port local dans le tableau, où les noms sont coupés à 20 caractères."""
    matches = [
        row["local_interface"]
        for row in rows
        # Avec des capacités « R B », la colonne extraite peut valoir « B   Et3/2 »
        if row["neighbor_interface"].split()[-1] == remote_interface.split()[-1]
        and name.startswith(row["neighbor_name"])
    ]
    if len(matches) != 1:
        raise CollectionError(f"port local introuvable ou ambigu pour le voisin {name}")
    return matches[0]


def parse_neighbors(output, read_table):
    """Analyse la sortie de 'show lldp neighbors detail' avec ntc-templates.

    Certaines versions d'IOS n'y indiquent pas le port local : read_table() fournit alors
    la sortie de 'show lldp neighbors', où il figure.
    """
    total = re.search(r"Total entries displayed:\s*(\d+)", output)
    if not total:
        # Sans ce total, une sortie tronquée ou une erreur passerait pour « aucun voisin »
        raise CollectionError("sortie LLDP incomplète ou inattendue")

    entries = parse_output(platform=DEVICE_TYPE, command=NEIGHBORS_COMMAND, data=output)
    if len(entries) != int(total.group(1)):
        raise CollectionError(
            f"{len(entries)} voisin(s) analysé(s) sur {total.group(1)} annoncé(s)"
        )

    rows = None
    if any(not e["local_interface"] for e in entries):
        rows = parse_output(platform=DEVICE_TYPE, command=TABLE_COMMAND, data=read_table())

    neighbors = []
    for e in entries:
        # Sans System Name annoncé, le Chassis ID identifie le voisin
        full_name = e["neighbor_name"] or e["chassis_id"]
        local_interface = e["local_interface"] or _find_local_interface(
            rows, full_name, e["neighbor_port_id"]
        )
        neighbors.append(
            {
                "name": short_name(full_name) if e["neighbor_name"] else full_name,
                "local_interface": local_interface,
                "remote_interface": e["neighbor_port_id"],
            }
        )
    return neighbors


def collect_device(ip, settings):
    """Interroge un équipement et retourne (hostname court, informations)."""
    with ConnectHandler(
        device_type=DEVICE_TYPE,
        host=ip,
        username=settings.username,
        password=settings.password,
        secret=settings.secret,
        timeout=settings.timeout,
        session_timeout=settings.session_timeout,
    ) as conn:
        conn.enable()

        def run(command):
            output = conn.send_command(command, read_timeout=settings.timeout)
            logger.debug("%s > %s\n%s", ip, command, output)
            return output

        model = re.search(MODEL_PATTERN, run("show version"))
        if not model:
            raise CollectionError("type d'équipement non reconnu")

        if "LLDP is not enabled" in run("show lldp"):
            raise CollectionError("LLDP n'est pas activé")

        hostname = parse_hostname(run("show running-config | include hostname"))
        neighbors = parse_neighbors(run(NEIGHBORS_COMMAND), lambda: run(TABLE_COMMAND))

    return short_name(hostname), {
        "ip": ip,
        "device_type": DEVICE_TYPE,
        "vendor": VENDOR,
        "model": model.group(0),
        "protocol": PROTOCOL,
        "neighbors": neighbors,
    }


def _probe(ip, settings):
    """Retourne (hostname, informations), ou None si l'équipement est en échec."""
    if not is_reachable(ip):
        logger.error("%s ne répond pas au ping", ip)
        return None

    try:
        hostname, info = collect_device(ip, settings)
    except Exception as e:  # un équipement en échec ne doit pas arrêter la collecte
        logger.error("Collecte impossible sur %s : %s", ip, e)
        logger.debug("Détail de l'échec sur %s", ip, exc_info=True)
        return None

    logger.info("%s (%s) : %d voisin(s)", ip, hostname, len(info["neighbors"]))
    return hostname, info


def collect_topology(settings, ips):
    """Interroge en parallèle les équipements demandés."""
    with ThreadPoolExecutor(max_workers=settings.max_workers) as pool:
        # map conserve l'ordre des adresses
        results = list(pool.map(lambda ip: _probe(ip, settings), ips))

    names = Counter(result[0] for result in results if result)
    devices = {}
    for result in filter(None, results):
        name, info = result
        # Des homonymes ne doivent pas s'écraser dans le dictionnaire
        devices[f"{name} ({info['ip']})" if names[name] > 1 else name] = info

    return {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "devices": devices,
        "failed_devices": [ip for ip, result in zip(ips, results, strict=True) if not result],
    }
