"""CLI: merge role/env/group/nagios/ansible metadata into a NetBox IP Address description, looked up by FQDN."""
import argparse
import re
import sys

import pynetbox
import requests

from .client import (
    IPAddressLookupError,
    NetBoxConfigError,
    find_ip_address,
    get_client,
    get_owner_names,
    list_ip_addresses,
    resolve_owner_ids,
)
from .description import merge_description, split_leading_json
from .schema import DEFAULTS, ValidationError, sanitize_env, validate_data

TABLE_COLUMNS = [("hostname", "Hostname"), ("role", "Role"), ("env", "Env"), ("group", "Group"), ("nagios", "Nagios"), ("ansible", "Ansible")]
DATA_FLAGS = ("role", "env", "group", "nagios", "ansible")


def _bool_flag(value):
    v = value.strip().lower()
    if v == "true":
        return True
    if v == "false":
        return False
    raise argparse.ArgumentTypeError(f"invalid value {value!r} (expected true or false)")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Look up a NetBox IP Address by FQDN (dns_name) and merge role/env/group/nagios/ansible "
            "metadata into the front of its description field."
        )
    )
    parser.add_argument(
        "fqdn",
        nargs="?",
        help=(
            "FQDN to look up via the IP Address dns_name field. "
            "With --list, this is instead a regex matched against the start of dns_name."
        ),
    )
    parser.add_argument("--role", help="Playbook to run against the host. Defaults to 'default' on first-time creation.")
    parser.add_argument("--env", help="Branch the playbook should be sourced from. Defaults to prod_a on first-time creation.")
    parser.add_argument(
        "--group",
        help=(
            "Which group_structure/<role>.yml node this host belongs to, for sync-inventory's "
            "nested-group support. No default -- only meaningful if --role has a matching "
            "group_structure file; otherwise ignored."
        ),
    )
    parser.add_argument(
        "--nagios",
        type=_bool_flag,
        metavar="{true,false}",
        help="Whether the host should be monitored by Nagios. Defaults to true on first-time creation.",
    )
    parser.add_argument(
        "--ansible",
        type=_bool_flag,
        metavar="{true,false}",
        help="Whether the host should be managed by the Ansible controller. Defaults to true on first-time creation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print the new description without saving it to NetBox.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt before saving.",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help=(
            "List IP Address entries owned by NETBOX_OWNERS as a table "
            "(hostname, role, env, group, nagios, ansible). Optionally pass a regex "
            "as the fqdn argument to only list entries whose dns_name matches it "
            "from the start, e.g. `nbmeta --list wiki`."
        ),
    )
    args = parser.parse_args(argv)

    given = [f for f in DATA_FLAGS if getattr(args, f) is not None]
    if args.list:
        if given:
            parser.error(f"--list cannot be combined with --{'/--'.join(given)}")
    elif not args.fqdn:
        parser.error("fqdn is required unless --list is given")

    return args


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _table_row(ip):
    existing, _ = split_leading_json(ip.description or "")
    row = {"hostname": ip.dns_name or ""}
    row.update({key: _cell(existing.get(key)) for key, _ in TABLE_COLUMNS[1:]})
    return row


def _print_table(rows):
    if not rows:
        print("No IP Address entries found for NETBOX_OWNERS.")
        return
    widths = [
        max(len(header), max((len(r[key]) for r in rows), default=0))
        for key, header in TABLE_COLUMNS
    ]

    def fmt(values):
        return "  ".join(v.ljust(w) for v, w in zip(values, widths))

    print(fmt([header for _, header in TABLE_COLUMNS]))
    print(fmt(["-" * w for w in widths]))
    for row in rows:
        print(fmt([row[key] for key, _ in TABLE_COLUMNS]))


def main(argv=None):
    args = parse_args(argv)

    try:
        nb = get_client()
        owner_names = get_owner_names()
        owner_ids, unresolved = resolve_owner_ids(nb, owner_names)
        if unresolved:
            print(f"warning: NETBOX_OWNERS not found in NetBox, ignoring: {unresolved}", file=sys.stderr)
    except NetBoxConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except requests.exceptions.ConnectionError as exc:
        print(f"error: could not reach NetBox: {exc}", file=sys.stderr)
        return 1

    if args.list:
        pattern = None
        if args.fqdn:
            try:
                pattern = re.compile(args.fqdn)
            except re.error as exc:
                print(f"error: invalid --list pattern {args.fqdn!r}: {exc}", file=sys.stderr)
                return 1
        rows = [
            _table_row(ip)
            for ip in list_ip_addresses(nb, owner_ids)
            if ip.dns_name and (pattern is None or pattern.match(ip.dns_name))
        ]
        _print_table(rows)
        return 0

    new_data = {f: getattr(args, f) for f in DATA_FLAGS if getattr(args, f) is not None}
    if "env" in new_data:
        new_data["env"] = sanitize_env(new_data["env"])

    try:
        validate_data(new_data)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        ip = find_ip_address(nb, args.fqdn, owner_ids)
    except IPAddressLookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    new_description = merge_description(ip.description, new_data, defaults=DEFAULTS)

    if args.dry_run:
        print(f"[dry-run] {ip.address} description would become:\n{new_description}")
        return 0

    print(f"IP Address:          {ip.address} ({args.fqdn})")
    print(f"Current description: {ip.description or ''}")
    print(f"New description:     {new_description}")

    if not args.yes:
        reply = input("Apply this change? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted: no changes made.")
            return 1

    ip.description = new_description
    try:
        saved = ip.save()
    except pynetbox.RequestError as exc:
        print(f"error: NetBox rejected the update for {ip.address}: {exc}", file=sys.stderr)
        return 1

    if not saved:
        print(f"error: failed to save description for {ip.address}.", file=sys.stderr)
        return 1

    print(f"success: updated description for {args.fqdn} ({ip.address}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
