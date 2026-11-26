"""Export d'une topologie en tableau Excel."""

import io

from openpyxl import Workbook

HEADERS = ["Équipement", "IP", "Voisin", "Interface Locale", "Interface Distante", "Protocole"]


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


def excel_bytes(links):
    wb = Workbook()
    ws = wb.active
    ws.title = "Topologie"
    for row in [HEADERS, *links]:
        ws.append(row)

    for column in ws.columns:
        width = max(len(str(cell.value)) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
