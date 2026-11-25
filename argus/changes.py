"""Détection des changements entre deux topologies."""


def _by_ip(topology):
    """Associe chaque IP à (nom, informations) ; informations vaut None en cas d'échec."""
    result = {ip: (ip, None) for ip in topology.get("failed_devices", [])}
    result.update({info["ip"]: (name, info) for name, info in topology["devices"].items()})
    return result


def _links(info):
    return {(n["local_interface"], n["name"], n["remote_interface"]) for n in info["neighbors"]}


def _change(kind, message, ip, device, **details):
    return {"type": kind, "message": message, "details": {"ip": ip, "device": device, **details}}


def _link_change(kind, verb, ip, device, link):
    local_interface, neighbor, remote_interface = link
    return _change(
        kind,
        f"Lien {verb} : {device} {local_interface} → {neighbor} {remote_interface}",
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
        name = old[ip][0]
        changes.append(
            _change("device_removed", f"Équipement retiré de la surveillance : {name}", ip, name)
        )

    for ip in sorted(new):
        name, info = new[ip]
        old_name, old_info = old.get(ip, (ip, None))

        if ip not in old:
            changes.append(_change("device_added", f"Nouvel équipement : {name}", ip, name))
            if info is None:
                changes.append(_change("device_failed", f"Équipement en échec : {name}", ip, name))
        elif info is None:
            if old_info is not None:
                changes.append(
                    _change("device_failed", f"Équipement en échec : {old_name}", ip, old_name)
                )
        elif old_info is None:
            changes.append(_change("device_recovered", f"Équipement rétabli : {name}", ip, name))
        else:
            if name != old_name:
                changes.append(
                    _change(
                        "device_renamed",
                        f"Équipement renommé : {old_name} → {name}",
                        ip,
                        name,
                        previous_device=old_name,
                    )
                )
            before, after = _links(old_info), _links(info)
            changes += [
                _link_change("link_removed", "perdu", ip, name, link)
                for link in sorted(before - after)
            ]
            changes += [
                _link_change("link_added", "ajouté", ip, name, link)
                for link in sorted(after - before)
            ]

    return changes
