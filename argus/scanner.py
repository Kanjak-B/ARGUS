"""Surveillance en tâche de fond pour l'application web."""

import logging
import threading
from datetime import datetime

from argus.changes import detect_changes
from argus.collector import collect_topology
from argus.graph import restrict

logger = logging.getLogger(__name__)


class Scanner:
    def __init__(self, settings, db, collect=collect_topology):
        self._settings = settings
        self._db = db
        self._collect = collect
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._scan_lock = threading.Lock()
        self._version_lock = threading.Lock()
        self._thread = None
        self._version = 0
        self._scanning = False
        self._last_error = None

    def status(self):
        """La version augmente à chaque évolution que l'interface doit recharger."""
        return {
            "version": self._version,
            "scanning": self._scanning,
            "last_error": self._last_error,
        }

    def notify(self):
        with self._version_lock:
            self._version += 1

    def request_scan(self):
        """Déclenche un scan sans attendre la fin de l'intervalle."""
        self._wake.set()

    def run_once(self):
        with self._scan_lock:
            self._scanning = True
            self.notify()
            try:
                self._scan()
                self._last_error = None
            except Exception as e:
                self._last_error = str(e)
                raise
            finally:
                self._scanning = False
                self.notify()

    def _scan(self):
        ips = [device["ip"] for device in self._db.list_devices()]
        if ips:
            topology = self._collect(self._settings, ips)
        else:
            topology = {
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "devices": {},
                "failed_devices": [],
            }

        # Un équipement supprimé pendant la collecte ne doit pas réapparaître
        topology = restrict(topology, {device["ip"] for device in self._db.list_devices()})
        previous, _ = self._db.load_state()
        changes = detect_changes(previous, topology)
        for change in changes:
            logger.warning("%s", change["message"])
        self._db.save_scan(topology, changes)

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="argus-scanner", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            # Thread démon : on n'attend pas indéfiniment une collecte en cours
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.is_set():
            # Effacé avant le scan : une demande reçue pendant celui-ci en relancera un
            self._wake.clear()
            try:
                self.run_once()
            except Exception:
                logger.exception("Erreur pendant la surveillance")
            self._wake.wait(self._settings.monitor_interval)
