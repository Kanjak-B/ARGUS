import asyncio
import contextlib
import dataclasses
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from argus.config import load_settings
from argus.db import Database
from argus.graph import build_graph
from argus.scanner import Scanner
from argus.web import create_app, event_stream


def make_settings():
    env = {"ARGUS_USERNAME": "u", "ARGUS_PASSWORD": "p", "ARGUS_ADMIN_PASSWORD": "secret"}
    with mock.patch.dict("os.environ", env, clear=True):
        return load_settings(Path("missing.env"))


def link(local, neighbor, remote):
    return {"local_interface": local, "name": neighbor, "remote_interface": remote}


def fake_topology(devices=None, failed=()):
    """devices : {nom: (ip, voisins)}."""
    return {
        "timestamp": "20260101_000000",
        "devices": {
            name: {"ip": ip, "model": "m", "protocol": "LLDP", "neighbors": neighbors}
            for name, (ip, neighbors) in (devices or {}).items()
        },
        "failed_devices": list(failed),
    }


class GraphTests(unittest.TestCase):
    INVENTORY = [
        {"ip": "192.0.2.1", "hostname": "SW1"},
        {"ip": "192.0.2.2", "hostname": "SW2"},
        {"ip": "192.0.2.3", "hostname": None},
    ]

    def test_both_ends_are_merged_and_parallel_links_kept(self):
        topology = fake_topology(
            {
                "SW1": (
                    "192.0.2.1",
                    [link("Gi0/1", "SW2", "Gi0/1"), link("Gi0/2", "SW2", "Gi0/2")],
                ),
                "SW2": (
                    "192.0.2.2",
                    [link("Gi0/1", "SW1", "Gi0/1"), link("Gi0/2", "SW1", "Gi0/2")],
                ),
            }
        )
        self.assertEqual(len(build_graph(self.INVENTORY, topology)["edges"]), 2)

    def test_node_statuses(self):
        topology = fake_topology(
            {"SW1": ("192.0.2.1", [link("Gi0/1", "SW2", "Gi0/1"), link("Gi0/3", "PC", "eth0")])},
            failed=["192.0.2.2"],
        )
        graph = build_graph(self.INVENTORY, topology)
        self.assertEqual(
            {node["id"]: node["status"] for node in graph["nodes"]},
            {"SW1": "ok", "SW2": "failed", "192.0.2.3": "pending", "PC": "unmanaged"},
        )

    def test_layers_from_role_then_name_then_links(self):
        inventory = [
            {"ip": "192.0.2.1", "hostname": "SW-DST-01"},
            {"ip": "192.0.2.2", "hostname": "SW-ACC-01", "role": "core"},
            {"ip": "192.0.2.3", "hostname": "Switch"},
        ]
        topology = fake_topology(
            {
                "SW-DST-01": ("192.0.2.1", [link("Et0/0", "SW-ACC-01", "Et3/3")]),
                "SW-ACC-01": ("192.0.2.2", []),
                "Switch": ("192.0.2.3", [link("e1", "PC1", "e0"), link("e2", "CORE2", "e0")]),
            }
        )
        nodes = build_graph(inventory, topology)["nodes"]
        self.assertEqual(
            {node["id"]: node["layer"] for node in nodes},
            {
                "SW-DST-01": "distribution",
                "SW-ACC-01": "core",
                "Switch": "distribution",
                "PC1": "access",
                "CORE2": "core",
            },
        )

    def test_before_first_scan(self):
        graph = build_graph(self.INVENTORY, None)
        self.assertEqual({node["status"] for node in graph["nodes"]}, {"pending"})
        self.assertEqual(graph["edges"], [])


class WebTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        settings = dataclasses.replace(make_settings(), db_path=Path(tmp.name) / "sub" / "a.db")
        self.db = Database(settings.db_path)
        self.result = fake_topology()
        self.scanner = Scanner(settings, self.db, collect=lambda _settings, _ips: self.result)
        self.client = TestClient(create_app(settings, self.db, self.scanner, run_scanner=False))

    def login(self):
        response = self.client.post("/api/login", json={"password": "secret"})
        self.assertEqual(response.status_code, 204)
        return response

    def add(self, ip):
        return self.client.post("/api/devices", json={"ip": ip})


class AuthTests(WebTestCase):
    def test_every_route_requires_a_session(self):
        calls = [
            ("get", "/api/devices"),
            ("post", "/api/devices"),
            ("delete", "/api/devices/1"),
            ("patch", "/api/devices/1"),
            ("get", "/api/topology"),
            ("get", "/api/changes"),
            ("post", "/api/scan"),
            ("get", "/api/events"),
            ("get", "/api/export/json"),
            ("post", "/api/logout"),
        ]
        for method, url in calls:
            with self.subTest(url=url, method=method):
                self.assertEqual(self.client.request(method, url).status_code, 401)

    def test_wrong_password(self):
        with mock.patch("argus.web.time.sleep"):
            for password in ("nope", "é"):
                response = self.client.post("/api/login", json={"password": password})
                self.assertEqual(response.status_code, 401)

    def test_cookie_flags_and_logout(self):
        cookie = self.login().headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        token = self.client.cookies["argus_session"]
        self.assertEqual(self.client.post("/api/logout").status_code, 204)
        self.client.cookies.set("argus_session", token)
        self.assertEqual(self.client.get("/api/devices").status_code, 401)


class DeviceTests(WebTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_validation_and_duplicates(self):
        self.assertEqual(self.add(" 192.0.2.1 ").json()["ip"], "192.0.2.1")
        self.assertEqual(self.add("192.0.2.1").status_code, 409)
        for ip in ("", "switch-01", "999.0.0.1", "-n 5", "192.0.2.0/24"):
            with self.subTest(ip=ip):
                self.assertEqual(self.add(ip).status_code, 422)

    def test_role_can_be_set_and_reset(self):
        url = f"/api/devices/{self.add('192.0.2.1').json()['id']}"
        self.assertEqual(self.client.patch(url, json={"role": "core"}).status_code, 204)
        (device,) = self.client.get("/api/devices").json()
        self.assertEqual((device["role"], device["layer"]), ("core", "core"))
        self.assertEqual(self.client.patch(url, json={"role": None}).status_code, 204)
        self.assertEqual(self.client.get("/api/devices").json()[0]["layer"], "access")
        self.assertEqual(self.client.patch(url, json={"role": "boss"}).status_code, 422)
        self.assertEqual(
            self.client.patch("/api/devices/999", json={"role": None}).status_code, 404
        )

    def test_database_without_role_column_is_migrated(self):
        path = self.db.path.with_name("old.db")
        with contextlib.closing(sqlite3.connect(path)) as conn, conn:
            conn.execute(
                "CREATE TABLE devices (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "ip TEXT NOT NULL UNIQUE, hostname TEXT, created_at TEXT NOT NULL)"
            )
            conn.execute("INSERT INTO devices (ip, created_at) VALUES ('192.0.2.9', 'x')")
        (device,) = Database(path).list_devices()
        self.assertEqual((device["ip"], device["role"]), ("192.0.2.9", None))

    def test_delete(self):
        device_id = self.add("192.0.2.1").json()["id"]
        self.assertEqual(self.client.delete(f"/api/devices/{device_id}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/devices/{device_id}").status_code, 404)
        self.assertEqual(self.client.get("/api/devices").json(), [])


class ScanCycleTests(WebTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.device_id = self.add("192.0.2.1").json()["id"]
        self.healthy = fake_topology({"SW1": ("192.0.2.1", [link("Gi0/1", "SW2", "Gi0/0")])})

    def scan(self, result):
        self.result = result
        self.scanner.run_once()

    def messages(self):
        return [change["message"] for change in self.client.get("/api/changes").json()]

    def test_failure_history_and_known_hostname(self):
        self.scan(self.healthy)
        self.assertEqual(self.messages(), [])
        self.assertEqual(self.client.get("/api/devices").json()[0]["status"], "ok")

        with self.assertLogs("argus.scanner", level="WARNING"):
            self.scan(fake_topology(failed=["192.0.2.1"]))
        self.assertEqual(self.messages(), ["Device failed: SW1"])
        (node,) = self.client.get("/api/topology").json()["nodes"]
        self.assertEqual((node["label"], node["status"]), ("SW1", "failed"))

    def test_history_stored_with_other_wording_is_shown_in_english(self):
        details = {"ip": "192.0.2.1", "device": "SW1"}
        old = {"type": "device_failed", "message": "Équipement en échec : SW1", "details": details}
        self.db.save_scan(fake_topology(), [old])
        self.assertEqual(self.messages(), ["Device failed: SW1"])

    def test_removal_is_immediate_and_not_a_failure(self):
        self.scan(self.healthy)
        self.client.delete(f"/api/devices/{self.device_id}")
        self.assertEqual(self.client.get("/api/topology").json()["nodes"], [])
        with self.assertLogs("argus.scanner", level="WARNING"):
            self.scan(self.healthy)  # le résultat contient encore l'équipement supprimé
        self.assertEqual(self.messages(), ["Device removed from monitoring: SW1"])

    def test_scan_error_is_reported_then_cleared(self):
        self.scanner._collect = mock.Mock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            self.scanner.run_once()
        self.assertEqual(self.scanner.status()["last_error"], "boom")
        self.assertFalse(self.scanner.status()["scanning"])
        self.scanner._collect = lambda _settings, _ips: self.healthy
        self.scanner.run_once()
        self.assertIsNone(self.scanner.status()["last_error"])

    def export(self, file_format, view):
        response = self.client.get(f"/api/export/{file_format}?view={view}")
        self.assertEqual(response.status_code, 200)
        return response

    def sheets(self, view):
        workbook = load_workbook(io.BytesIO(self.export("xlsx", view).content))
        return {sheet.title: list(sheet.values)[1:] for sheet in workbook}

    def test_export_follows_the_view(self):
        self.assertEqual(self.client.get("/api/export/json").status_code, 404)
        self.add("192.0.2.2")
        self.add("192.0.2.3")
        neighbors = [link("Gi0/1", "SW2", "Gi0/0"), link("Gi0/2", "SW-X", "e0")]
        self.scan(
            fake_topology(
                {
                    "SW1": ("192.0.2.1", neighbors),
                    "SW2": ("192.0.2.2", [link("Gi0/0", "SW1", "Gi0/1")]),
                },
                failed=["192.0.2.3"],
            )
        )

        complete = self.export("json", "all")
        self.assertIn("_full.json", complete.headers["content-disposition"])
        self.assertEqual(
            {d["name"]: d["status"] for d in complete.json()["devices"]},
            {"SW1": "ok", "SW2": "ok", "192.0.2.3": "failed", "SW-X": "unmanaged"},
        )
        self.assertEqual(len(complete.json()["links"]), 2)

        online = self.export("json", "online")
        self.assertIn("_online.json", online.headers["content-disposition"])
        self.assertEqual([d["name"] for d in online.json()["devices"]], ["SW1", "SW2"])
        cable = {
            "device_a": "SW1",
            "interface_a": "Gi0/1",
            "device_b": "SW2",
            "interface_b": "Gi0/0",
        }
        self.assertEqual(online.json()["links"], [cable])

        # Un équipement sans aucun câble figure quand même dans la feuille « Devices »
        failed_row = ("192.0.2.3", "192.0.2.3", "Access", "Failed")
        self.assertIn(failed_row, self.sheets("all")["Devices"])
        self.assertEqual(len(self.sheets("online")["Devices"]), 2)
        self.assertEqual(self.sheets("online")["Links"], [("SW1", "Gi0/1", "SW2", "Gi0/0")])

    def test_neighbor_names_are_never_excel_formulas(self):
        self.scan(fake_topology({"SW1": ("192.0.2.1", [link("Gi0/1", "=1+1", "e0")])}))
        workbook = load_workbook(io.BytesIO(self.export("xlsx", "all").content))
        cells = [cell for sheet in workbook for row in sheet for cell in row]
        self.assertIn("=1+1", [cell.value for cell in cells])
        self.assertNotIn("f", {cell.data_type for cell in cells})

    def test_unknown_format_or_view(self):
        self.scan(self.healthy)
        self.assertEqual(self.client.get("/api/export/png").status_code, 404)
        self.assertEqual(self.client.get("/api/export/json?view=autre").status_code, 422)


class FrontendTests(unittest.TestCase):
    def test_build_is_served_without_hiding_the_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "index.html").write_text("<title>ARGUS</title>", encoding="utf-8")
            db = Database(Path(tmp) / "a.db")
            settings = make_settings()
            app = create_app(
                settings, db, Scanner(settings, db), run_scanner=False, frontend_dir=Path(tmp)
            )
            client = TestClient(app)

            self.assertIn("ARGUS", client.get("/").text)
            self.assertEqual(client.get("/api/devices").status_code, 401)
            self.assertEqual(client.get("/docs").status_code, 200)
            self.assertEqual(client.get("/../pyproject.toml").status_code, 404)


class EventStreamTests(unittest.TestCase):
    def test_sends_new_versions_until_session_ends(self):
        scanner = mock.Mock()
        scanner.status.side_effect = [{"version": 1}, {"version": 1}, {"version": 2}]
        active = iter([True, True, True, False])

        async def collect():
            return [m async for m in event_stream(scanner, lambda: next(active), 0)]

        self.assertEqual(
            asyncio.run(collect()),
            ['data: {"version": 1}\n\n', 'data: {"version": 2}\n\n'],
        )


if __name__ == "__main__":
    unittest.main()
