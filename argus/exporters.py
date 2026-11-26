"""Exports JSON et Excel, construits à partir du graphe affiché par l'interface."""

import io

from openpyxl import Workbook

_STATUS_LABELS = {
    "ok": "En ligne",
    "failed": "En échec",
    "pending": "En attente",
    "unmanaged": "Non géré",
}
_LAYER_LABELS = {"core": "Cœur", "distribution": "Distribution", "access": "Accès"}


def build_document(graph, view, scanned_at):
    """Contenu d'un export : les équipements, puis un enregistrement par câble."""
    names = {node["id"]: node["label"] for node in graph["nodes"]}
    return {
        "view": view,
        "scanned_at": scanned_at,
        "devices": [
            {
                "name": node["label"],
                "ip": node["ip"],
                "layer": node["layer"],
                "status": node["status"],
                "model": node["model"],
            }
            for node in graph["nodes"]
        ],
        "links": [
            {
                "device_a": names[edge["source"]],
                "interface_a": edge["source_interface"],
                "device_b": names[edge["target"]],
                "interface_b": edge["target_interface"],
            }
            for edge in graph["edges"]
        ],
    }


def _write_sheet(sheet, headers, rows):
    for row in [headers, *rows]:
        sheet.append(row)
        for cell in sheet[sheet.max_row]:
            # Les noms viennent du réseau (LLDP) : jamais interprétés comme des formules
            if isinstance(cell.value, str):
                cell.data_type = "s"

    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = width


def excel_bytes(document):
    workbook = Workbook()
    devices = workbook.active
    devices.title = "Équipements"
    _write_sheet(
        devices,
        ["Nom", "IP", "Couche", "Statut"],
        [
            [d["name"], d["ip"], _LAYER_LABELS[d["layer"]], _STATUS_LABELS[d["status"]]]
            for d in document["devices"]
        ],
    )
    _write_sheet(
        workbook.create_sheet("Liaisons"),
        ["Équipement A", "Port A", "Équipement B", "Port B"],
        [
            [link["device_a"], link["interface_a"], link["device_b"], link["interface_b"]]
            for link in document["links"]
        ],
    )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
