"""Thin wrapper around pynetbox for locating an IP Address by FQDN."""
import os

import pynetbox


class NetBoxConfigError(RuntimeError):
    pass


class IPAddressLookupError(RuntimeError):
    pass


def get_client():
    url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not url or not token:
        raise NetBoxConfigError("NETBOX_URL and NETBOX_TOKEN must be set in the environment.")
    return pynetbox.api(url, token=token)


def get_owner_names():
    raw = os.environ.get("NETBOX_OWNERS", "")
    owners = [o.strip() for o in raw.split(",") if o.strip()]
    if not owners:
        raise NetBoxConfigError("NETBOX_OWNERS must be set to a comma-separated list of owner names.")
    return owners


def resolve_owner_ids(nb, owner_names):
    """Resolve owner names to ids via the NetBox owners endpoint. Returns (ids, unresolved_names)."""
    ids = []
    unresolved = []
    for name in owner_names:
        owner = nb.users.owners.get(name=name)
        if owner:
            ids.append(owner.id)
        else:
            unresolved.append(name)
    if not ids:
        raise NetBoxConfigError(f"None of NETBOX_OWNERS resolved to a NetBox owner: {owner_names}")
    return ids, unresolved


def list_ip_addresses(nb, owner_ids):
    return list(nb.ipam.ip_addresses.filter(owner_id=owner_ids))


def find_ip_address(nb, fqdn, owner_ids):
    matches = list(nb.ipam.ip_addresses.filter(dns_name=fqdn, owner_id=owner_ids))
    if not matches:
        raise IPAddressLookupError(
            f"No IP Address found with dns_name={fqdn!r} owned by owner_id in {owner_ids}."
        )
    if len(matches) > 1:
        addrs = ", ".join(m.address for m in matches)
        raise IPAddressLookupError(f"Multiple IP Addresses found with dns_name={fqdn!r}: {addrs}")
    return matches[0]
