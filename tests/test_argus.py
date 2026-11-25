import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from argus.changes import detect_changes
from argus.collector import CollectionError, collect_topology, parse_hostname, parse_neighbors
from argus.config import ConfigError, load_settings
from argus.exporters import build_links, export_topology, load_latest_json


def lldp_entry(local_interface, system_name):
    name = f"System Name: {system_name}" if system_name else "System Name - not advertised"
    lines = [
        "------------------------------------------------",
        f"Local Intf: {local_interface}",
        "Chassis id: 5254.0012.3456",
        "Port id: Gi0/0",
        "Port Description: GigabitEthernet0/0",
        name,
        "",
        "System Description: ",
        "Cisco IOS Software, vios_l2 Software, Version 15.2",
        "Technical Support: http://www.cisco.com/techsupport",
        "",
        "Time remaining: 99 seconds",
        "System Capabilities: B,R",
        "Enabled Capabilities: B",
        "Management Addresses:",
        "    IP: 192.0.2.20",
        "Auto Negotiation - not supported",
        "Physical media capabilities - not advertised",
        "Media Attachment Unit type - not advertised",
        "Vlan ID: - not advertised",
        "",
        "",
    ]
    return "\n".join(lines)


def lldp_output(*entries):
    return "".join(entries) + f"\nTotal entries displayed: {len(entries)}\n"


LLDP_OUTPUT = lldp_output(lldp_entry("Gi0/1", "SW-ACC-01.lab.local"))


def topology(neighbors, failed=()):
    return {
        "timestamp": "20260101_000000",
        "devices": {"SW-DIST-01": {"ip": "192.0.2.10", "protocol": "LLDP", "neighbors": neighbors}},
        "failed_devices": list(failed),
    }


class ParserTests(unittest.TestCase):
    def test_neighbors(self):
        self.assertEqual(
            parse_neighbors(LLDP_OUTPUT),
            [{"name": "SW-ACC-01", "local_interface": "Gi0/1", "remote_interface": "Gi0/0"}],
        )

    def test_long_and_missing_names(self):
        output = lldp_output(
            lldp_entry("Gi0/1", "SW-ACCESS-WITH-A-VERY-LONG-NAME.lab.local"),
            lldp_entry("Gi0/2", None),
        )
        self.assertEqual(
            [n["name"] for n in parse_neighbors(output)],
            ["SW-ACCESS-WITH-A-VERY-LONG-NAME", "5254.0012.3456"],
        )

    def test_no_neighbors(self):
        self.assertEqual(parse_neighbors("\nTotal entries displayed: 0\n"), [])

    def test_unusable_output_is_an_error(self):
        cases = (
            "",
            "% Invalid input detected at '^' marker.",
            LLDP_OUTPUT.replace("displayed: 1", "displayed: 2"),
        )
        for output in cases:
            with self.subTest(output=output[:30]), self.assertRaises(CollectionError):
                parse_neighbors(output)

    def test_hostname(self):
        self.assertEqual(parse_hostname("hostname SW-DIST-01\n"), "SW-DIST-01")
        self.assertEqual(parse_hostname(""), "Unknown")


class CollectionTests(unittest.TestCase):
    def test_parallel_collection_keeps_order_and_isolates_failures(self):
        devices = ("192.0.2.1", "192.0.2.2", "192.0.2.3")
        settings = mock.Mock(max_workers=3)
        # La barrière n'est franchie que si les trois collectes sont simultanées
        barrier = threading.Barrier(len(devices), timeout=5)

        def fake_collect(ip, _settings):
            barrier.wait()
            if ip == "192.0.2.2":
                raise CollectionError("échec simulé")
            return f"SW-{ip[-1]}", {"ip": ip, "neighbors": []}

        with (
            mock.patch("argus.collector.is_reachable", return_value=True),
            mock.patch("argus.collector.collect_device", side_effect=fake_collect),
            self.assertLogs("argus.collector", level="ERROR"),
        ):
            result = collect_topology(settings, devices)

        self.assertEqual(list(result["devices"]), ["SW-1", "SW-3"])
        self.assertEqual(result["failed_devices"], ["192.0.2.2"])

    def test_duplicate_hostnames_are_both_kept(self):
        with (
            mock.patch("argus.collector.is_reachable", return_value=True),
            mock.patch(
                "argus.collector.collect_device",
                side_effect=lambda ip, _: ("Switch", {"ip": ip, "neighbors": []}),
            ),
        ):
            result = collect_topology(mock.Mock(max_workers=2), ["192.0.2.1", "192.0.2.2"])

        self.assertEqual(list(result["devices"]), ["Switch (192.0.2.1)", "Switch (192.0.2.2)"])


class ChangeDetectionTests(unittest.TestCase):
    def setUp(self):
        self.reference = topology(parse_neighbors(LLDP_OUTPUT))
        self.down = {**self.reference, "devices": {}, "failed_devices": ["192.0.2.10"]}

    def types(self, previous, current):
        return [change["type"] for change in detect_changes(previous, current)]

    def test_no_change(self):
        self.assertEqual(detect_changes(self.reference, self.reference), [])

    def test_first_run_is_only_a_reference(self):
        self.assertEqual(detect_changes(None, self.reference), [])

    def test_lost_and_added_link(self):
        (lost,) = detect_changes(self.reference, topology([]))
        self.assertEqual(lost["message"], "Lien perdu : SW-DIST-01 Gi0/1 → SW-ACC-01 Gi0/0")
        self.assertEqual(lost["details"]["local_interface"], "Gi0/1")
        self.assertEqual(self.types(topology([]), self.reference), ["link_added"])

    def test_failure_and_recovery_are_single_events(self):
        self.assertEqual(self.types(self.reference, self.down), ["device_failed"])
        self.assertEqual(self.types(self.down, self.down), [])
        self.assertEqual(self.types(self.down, self.reference), ["device_recovered"])

    def test_inventory_changes(self):
        empty = {"devices": {}, "failed_devices": []}
        self.assertEqual(self.types(self.reference, empty), ["device_removed"])
        self.assertEqual(self.types(empty, self.reference), ["device_added"])
        self.assertEqual(self.types(empty, self.down), ["device_added", "device_failed"])

    def test_rename(self):
        renamed = {**self.reference, "devices": {"SW-NEW": self.reference["devices"]["SW-DIST-01"]}}
        self.assertEqual(self.types(self.reference, renamed), ["device_renamed"])


class ExportTests(unittest.TestCase):
    def test_json_round_trip_creates_output_dir(self):
        data = topology([])
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "missing"
            export_topology(data, output_dir)
            self.assertEqual(load_latest_json(output_dir), data)

    def test_links(self):
        self.assertEqual(
            build_links(topology(parse_neighbors(LLDP_OUTPUT))),
            [["SW-DIST-01", "192.0.2.10", "SW-ACC-01", "Gi0/1", "Gi0/0", "LLDP"]],
        )


class ConfigTests(unittest.TestCase):
    ENV = {
        "ARGUS_DEVICES": "192.0.2.10, 192.0.2.11,",
        "ARGUS_USERNAME": "u",
        "ARGUS_PASSWORD": "p",
    }
    NO_FILE = Path("missing.env")

    def load(self, env):
        with mock.patch.dict(os.environ, env, clear=True):
            return load_settings(self.NO_FILE)

    def test_defaults(self):
        settings = self.load(self.ENV)
        self.assertEqual(settings.devices, ("192.0.2.10", "192.0.2.11"))
        self.assertFalse(settings.allow_legacy_ssh)
        self.assertNotIn("password", repr(settings))
        self.assertEqual((settings.max_workers, settings.log_level), (10, "INFO"))

    def test_invalid_values(self):
        overrides = (
            {"ARGUS_PASSWORD": ""},
            {"ARGUS_TIMEOUT": "0"},
            {"ARGUS_ALLOW_LEGACY_SSH": "maybe"},
            {"ARGUS_LOG_LEVEL": "TRACE"},
        )
        for override in overrides:
            with self.subTest(override), self.assertRaises(ConfigError):
                self.load({**self.ENV, **override})


if __name__ == "__main__":
    unittest.main()
