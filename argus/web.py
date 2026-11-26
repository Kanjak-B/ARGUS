"""API web : authentification, équipements, topologie, historique et flux temps réel."""

import asyncio
import ipaddress
import json
import secrets
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from argus.config import PROJECT_ROOT
from argus.db import DuplicateDeviceError
from argus.exporters import build_document, excel_bytes
from argus.graph import build_graph, device_status, online_only, restrict

SESSION_COOKIE = "argus_session"
SESSION_LIFETIME = 12 * 3600
_HEARTBEAT_EVERY = 15
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"

_VIEW_SUFFIXES = {"all": "full", "online": "online"}
_MEDIA_TYPES = {
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class Login(BaseModel):
    password: str = Field(max_length=256)


class NewDevice(BaseModel):
    ip: str = Field(max_length=64)


class DeviceRole(BaseModel):
    role: Literal["core", "distribution", "access"] | None


class Sessions:
    """Sessions en mémoire : elles sont perdues au redémarrage."""

    def __init__(self):
        self._expirations = {}

    def create(self):
        token = secrets.token_urlsafe(32)
        self._expirations[token] = time.monotonic() + SESSION_LIFETIME
        return token

    def is_valid(self, token):
        return self._expirations.get(token, 0) > time.monotonic()

    def revoke(self, token):
        self._expirations.pop(token, None)


async def event_stream(scanner, is_active, poll_interval=1.0):
    """Flux SSE : un message à chaque nouvelle version, tant que la session est valide."""
    last_version = None
    idle = 0
    while is_active():
        status = scanner.status()
        if status["version"] != last_version:
            last_version = status["version"]
            idle = 0
            yield f"data: {json.dumps(status)}\n\n"
        else:
            idle += 1
            if idle >= _HEARTBEAT_EVERY:
                idle = 0
                yield ": heartbeat\n\n"
        await asyncio.sleep(poll_interval)


def create_app(settings, db, scanner, run_scanner=True, frontend_dir=FRONTEND_DIR):
    sessions = Sessions()

    @asynccontextmanager
    async def lifespan(_app):
        if run_scanner:
            scanner.start()
        yield
        if run_scanner:
            scanner.stop()

    def require_session(request: Request):
        if not sessions.is_valid(request.cookies.get(SESSION_COOKIE)):
            raise HTTPException(401, "Authentication required")

    app = FastAPI(title="ARGUS", lifespan=lifespan)
    api = APIRouter(prefix="/api", dependencies=[Depends(require_session)])

    def inventory_topology():
        """Dernière topologie, limitée aux équipements encore enregistrés."""
        inventory = db.list_devices()
        topology, scanned_at = db.load_state()
        if topology:
            topology = restrict(topology, {d["ip"] for d in inventory})
        return inventory, topology, scanned_at

    @app.post("/api/login", status_code=204)
    def login(credentials: Login, response: Response):
        if not secrets.compare_digest(
            credentials.password.encode(), settings.admin_password.encode()
        ):
            time.sleep(1)  # freine les essais répétés
            raise HTTPException(401, "Wrong password")
        response.set_cookie(
            SESSION_COOKIE,
            sessions.create(),
            max_age=SESSION_LIFETIME,
            httponly=True,
            samesite="strict",
        )

    @api.post("/logout", status_code=204)
    def logout(request: Request, response: Response):
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE)

    @api.get("/devices")
    def list_devices():
        inventory, topology, _ = inventory_topology()
        nodes = build_graph(inventory, topology)["nodes"]
        layers = {node["ip"]: node["layer"] for node in nodes if node["ip"]}
        return [
            {**d, "status": device_status(d["ip"], topology), "layer": layers[d["ip"]]}
            for d in inventory
        ]

    @api.post("/devices", status_code=201)
    def add_device(new: NewDevice):
        try:
            ip = str(ipaddress.ip_address(new.ip.strip()))
        except ValueError:
            raise HTTPException(422, "Invalid IP address") from None
        try:
            device = db.add_device(ip)
        except DuplicateDeviceError:
            raise HTTPException(409, "This device is already registered") from None
        scanner.notify()
        scanner.request_scan()
        return {**device, "status": "pending"}

    @api.patch("/devices/{device_id}", status_code=204)
    def set_device_role(device_id: int, update: DeviceRole):
        if not db.set_role(device_id, update.role):
            raise HTTPException(404, "Device not found")
        scanner.notify()

    @api.delete("/devices/{device_id}", status_code=204)
    def delete_device(device_id: int):
        if not db.delete_device(device_id):
            raise HTTPException(404, "Device not found")
        scanner.notify()
        scanner.request_scan()

    @api.get("/topology")
    def get_topology():
        inventory, topology, scanned_at = inventory_topology()
        return {**build_graph(inventory, topology), "scanned_at": scanned_at, **scanner.status()}

    @api.get("/changes")
    def get_changes(limit: int = 100):
        return db.list_changes(max(1, min(limit, 500)))

    @api.post("/scan", status_code=202)
    def scan():
        scanner.request_scan()

    @api.get("/events")
    async def events(request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        return StreamingResponse(
            event_stream(scanner, lambda: sessions.is_valid(token)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @api.get("/export/{file_format}")
    def export(file_format: str, view: Literal["all", "online"] = "all"):
        if file_format not in _MEDIA_TYPES:
            raise HTTPException(404, "Unknown format")
        inventory, topology, scanned_at = inventory_topology()
        if topology is None:
            raise HTTPException(404, "No topology available")

        graph = build_graph(inventory, topology)
        if view == "online":
            graph = online_only(graph)
        document = build_document(graph, view, scanned_at)

        if file_format == "json":
            content = json.dumps(document, indent=4, ensure_ascii=False).encode()
        else:
            content = excel_bytes(document)
        filename = f"topology_{topology['timestamp']}_{_VIEW_SUFFIXES[view]}.{file_format}"
        return Response(
            content,
            media_type=_MEDIA_TYPES[file_format],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    app.include_router(api)
    # Monté en dernier pour ne pas masquer l'API ni /docs
    if (frontend_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
