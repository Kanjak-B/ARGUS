"""Transformation d'une topologie en graphe (nœuds et liens) pour l'interface."""

import re
from collections import Counter

# Couches reconnues dans les noms, par exemple « SW-DST-01 » ou « CORE1 »
_LAYER_WORDS = {
    "core": {"CORE", "COR", "COEUR"},
    "distribution": {"DIST", "DST", "DIS", "DISTRIB", "DISTRIBUTION"},
    "access": {"ACC", "ACCESS", "ACCES"},
}


def layer_from_name(name):
    """Retourne la couche indiquée par le nom, ou None."""
    words = set(re.split(r"[^A-Z]+", name.upper()))
    return next((layer for layer, known in _LAYER_WORDS.items() if words & known), None)


def _assign_layers(nodes, edges, roles):
    """Priorité : choix de l'administrateur, nom, puis nombre de liaisons (jamais « core »)."""
    degrees = Counter()
    for edge in edges:
        degrees.update([edge["source"], edge["target"]])

    for node in nodes:
        guess = (
            "distribution" if node["status"] != "unmanaged" and degrees[node["id"]] > 1 else None
        )
        node["layer"] = roles.get(node["ip"]) or layer_from_name(node["label"]) or guess or "access"


def restrict(topology, ips):
    """Écarte de la topologie les équipements qui ne sont plus dans l'inventaire."""
    return {
        **topology,
        "devices": {n: i for n, i in topology["devices"].items() if i["ip"] in ips},
        "failed_devices": [ip for ip in topology["failed_devices"] if ip in ips],
    }


def device_status(ip, topology):
    """Retourne 'ok', 'failed' ou 'pending' (pas encore scanné)."""
    if topology:
        if ip in topology["failed_devices"]:
            return "failed"
        if any(info["ip"] == ip for info in topology["devices"].values()):
            return "ok"
    return "pending"


def build_graph(inventory, topology):
    """Construit {nodes, edges} à partir de l'inventaire et de la dernière topologie."""
    topology = restrict(
        topology or {"devices": {}, "failed_devices": []}, {d["ip"] for d in inventory}
    )
    scanned = {info["ip"]: (name, info) for name, info in topology["devices"].items()}
    nodes = {}

    # Les équipements joignables d'abord : leur nom actuel est prioritaire
    for ip, (name, info) in scanned.items():
        nodes[name] = {
            "id": name,
            "label": name,
            "status": "ok",
            "ip": ip,
            "model": info.get("model"),
        }

    for device in inventory:
        ip = device["ip"]
        if ip in scanned:
            continue
        # Le dernier nom connu permet de rattacher les liens annoncés par les voisins
        name = device["hostname"]
        node_id = name if name and name not in nodes else ip
        nodes[node_id] = {
            "id": node_id,
            "label": name or ip,
            "status": device_status(ip, topology),
            "ip": ip,
            "model": None,
        }

    edges = {}
    for source, info in topology["devices"].items():
        for neighbor in info["neighbors"]:
            target = neighbor["name"]
            nodes.setdefault(
                target,
                {"id": target, "label": target, "status": "unmanaged", "ip": None, "model": None},
            )
            local, remote = neighbor["local_interface"], neighbor["remote_interface"]
            # Même clé vue des deux extrémités ; des ports différents donnent des liens distincts
            first, second = sorted([(source, local), (target, remote)])
            edge_id = f"{first[0]}:{first[1]}--{second[0]}:{second[1]}"
            edges.setdefault(
                edge_id,
                {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "source_interface": local,
                    "target_interface": remote,
                },
            )

    roles = {device["ip"]: device.get("role") for device in inventory}
    _assign_layers(nodes.values(), edges.values(), roles)
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
