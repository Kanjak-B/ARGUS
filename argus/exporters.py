"""Restitution d'une topologie : journal, JSON, Excel et graphe PNG."""

import json
import logging
from collections import Counter

import graphviz
from openpyxl import Workbook
from tabulate import tabulate

HEADERS = ["Équipement", "IP", "Voisin", "Interface Locale", "Interface Distante", "Protocole"]

logger = logging.getLogger(__name__)


def build_links(topology):
    """Une ligne par couple (équipement, voisin), dans l'ordre de HEADERS."""
    return [
        [
            device,
            info["ip"],
            n["name"],
            n["local_interface"],
            n["remote_interface"],
            info["protocol"],
        ]
        for device, info in topology["devices"].items()
        for n in info["neighbors"]
    ]


def load_latest_json(output_dir):
    """Retourne la dernière topologie exportée, ou None."""
    files = list(output_dir.glob("topology_*.json"))
    if not files:
        return None

    latest = max(files, key=lambda path: path.stat().st_mtime)
    try:
        topology = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.error("Impossible de charger %s : %s", latest, e)
        return None

    logger.info("Topologie précédente chargée depuis %s", latest)
    return topology


def _save_json(topology, path):
    path.write_text(json.dumps(topology, indent=4, ensure_ascii=False), encoding="utf-8")


def _save_excel(links, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Topologie"
    for row in [HEADERS, *links]:
        ws.append(row)

    for column in ws.columns:
        width = max(len(str(cell.value)) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = width

    wb.save(path)


def build_graph(links):
    dot = graphviz.Graph(comment="Topologie Réseau", engine="dot")
    dot.attr(overlap="false", splines="true", rankdir="TB", dpi="300")
    dot.attr(
        "node",
        shape="box",
        style="filled",
        fillcolor="lightblue",
        fontname="Helvetica",
        fontsize="10",
    )
    dot.attr("edge", fontsize="8", fontname="Helvetica")

    # Heuristique : plusieurs connexions = distribution, sinon accès
    counts = Counter()
    for device, _, neighbor, *_ in links:
        counts.update([device, neighbor])

    for cluster, rank, is_distribution in (("cluster_0", "min", True), ("cluster_1", "max", False)):
        with dot.subgraph(name=cluster) as subgraph:
            subgraph.attr(rank=rank)
            for node, count in counts.items():
                if (count > 1) == is_distribution:
                    subgraph.node(node, node)

    # Une seule arête par couple d'équipements
    seen = set()
    for device, _, neighbor, local_intf, remote_intf, _ in links:
        key = frozenset((device, neighbor))
        if key not in seen:
            seen.add(key)
            dot.edge(
                device,
                neighbor,
                headlabel=remote_intf,
                taillabel=local_intf,
                color="darkblue",
                labeldistance="2.0",
                labelfloat="false",
                labelangle="45",
            )
    return dot


def _save_png(links, path):
    try:
        image = build_graph(links).pipe(format="png")
    except graphviz.ExecutableNotFound:
        logger.warning("PNG non généré : l'exécutable Graphviz 'dot' est absent du PATH")
        return False

    path.write_bytes(image)
    return True


def log_summary(links):
    logger.info("Topologie du réseau :\n%s", tabulate(links, headers=HEADERS, tablefmt="simple"))

    connections = {}
    for device, _, neighbor, *_ in links:
        connections.setdefault(device, set()).add(neighbor)

    summary = "\n".join(
        f"{device} est connecté à : {', '.join(sorted(neighbors))}"
        for device, neighbors in connections.items()
    )
    logger.info("Résumé des connexions :\n%s", summary)


def export_topology(topology, output_dir):
    """Exporte la topologie ; Excel et PNG exigent au moins une liaison."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / f"topology_{topology['timestamp']}"
    links = build_links(topology)

    if links:
        log_summary(links)
        _save_excel(links, base.with_suffix(".xlsx"))
        logger.info("Export Excel : %s.xlsx", base)
        if _save_png(links, base.with_suffix(".png")):
            logger.info("Export PNG : %s.png", base)
    else:
        logger.info("Aucune liaison trouvée")

    # Écrit en dernier : sert de référence au moniteur, donc seulement si le reste a réussi
    _save_json(topology, base.with_suffix(".json"))
    logger.info("Export JSON : %s.json", base)
