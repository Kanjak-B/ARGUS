"""Détection des changements entre deux topologies."""


def _by_ip(topology):
    """Associe chaque IP à (nom, informations) ; informations vaut None en cas d'échec."""
    result = {ip: (ip, None) for ip in topology.get("failed_devices", [])}
    result.update({info["ip"]: (name, info) for name, info in topology["devices"].items()})
    return result


def _links(info):
    return {(n["local_interface"], n["name"], n["remote_interface"]) for n in info["neighbors"]}


_LINK = "{device} {local_interface} → {neighbor} {remote_interface}"
_MESSAGES = {
    "device_added": "New device: {device}",
    "device_removed": "Device removed from monitoring: {device}",
    "device_failed": "Device failed: {device}",
    "device_recovered": "Device recovered: {device}",
    "device_renamed": "Device renamed: {previous_device} → {device}",
    "link_added": "Link added: " + _LINK,
    "link_removed": "Link lost: " + _LINK,
}


def describe(kind, details):
    """Texte affiché à l'utilisateur, toujours recalculé à partir des données."""
    return _MESSAGES[kind].format(**details)


def _change(kind, ip, device, **details):
    details = {"ip": ip, "device": device, **details}
    return {"type": kind, "message": describe(kind, details), "details": details}


def _link_change(kind, ip, device, link):
    local_interface, neighbor, remote_interface = link
    return _change(
        kind,
        ip,
        device,
        local_interface=local_interface,
        neighbor=neighbor,
        remote_interface=remote_interface,
    )


def detect_changes(previous, current):
    """Retourne les changements structurés. Sans référence précédente, il n'y en a aucun."""
    if previous is None:
        return []

    old, new = _by_ip(previous), _by_ip(current)
    changes = []

    for ip in sorted(old.keys() - new.keys()):
        changes.append(_change("device_removed", ip, old[ip][0]))

    for ip in sorted(new):
        name, info = new[ip]
        old_name, old_info = old.get(ip, (ip, None))

        if ip not in old:
            changes.append(_change("device_added", ip, name))
            if info is None:
                changes.append(_change("device_failed", ip, name))
        elif info is None:
            if old_info is not None:
                changes.append(_change("device_failed", ip, old_name))
        elif old_info is None:
            changes.append(_change("device_recovered", ip, name))
        else:
            if name != old_name:
                changes.append(_change("device_renamed", ip, name, previous_device=old_name))
            before, after = _links(old_info), _links(info)
            changes += [
                _link_change("link_removed", ip, name, link) for link in sorted(before - after)
            ]
            changes += [
                _link_change("link_added", ip, name, link) for link in sorted(after - before)
            ]

    return changes
