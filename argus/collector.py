"""Collecte des voisins LLDP : ping, connexion SSH et analyse des sorties."""

import logging
import platform
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from netmiko import ConnectHandler
from ntc_templates.parse import parse_output

DEVICE_TYPE = "cisco_ios"
VENDOR = "Cisco"
PROTOCOL = "LLDP"
MODEL_PATTERN = r"Cisco.*Software.*Version"
NEIGHBORS_COMMAND = "show lldp neighbors detail"

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


def parse_neighbors(output):
    """Analyse la sortie de 'show lldp neighbors detail' avec ntc-templates."""
    total = re.search(r"Total entries displayed:\s*(\d+)", output)
    if not total:
        # Sans ce total, une sortie tronquée ou une erreur passerait pour « aucun voisin »
        raise CollectionError("sortie LLDP incomplète ou inattendue")

    entries = parse_output(platform=DEVICE_TYPE, command=NEIGHBORS_COMMAND, data=output)
    if len(entries) != int(total.group(1)):
        raise CollectionError(
            f"{len(entries)} voisin(s) analysé(s) sur {total.group(1)} annoncé(s)"
        )

    return [
        {
            # Sans System Name annoncé, le Chassis ID identifie le voisin
            "name": short_name(e["neighbor_name"]) if e["neighbor_name"] else e["chassis_id"],
            "local_interface": e["local_interface"],
            "remote_interface": e["neighbor_port_id"],
        }
        for e in entries
    ]


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
        neighbors = parse_neighbors(run(NEIGHBORS_COMMAND))

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


def collect_topology(settings):
    """Interroge en parallèle tous les équipements configurés."""
    with ThreadPoolExecutor(max_workers=settings.max_workers) as pool:
        # map conserve l'ordre de la configuration
        results = list(pool.map(lambda ip: _probe(ip, settings), settings.devices))

    return {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "devices": dict(result for result in results if result),
        "failed_devices": [
            ip for ip, result in zip(settings.devices, results, strict=True) if not result
        ],
    }
