# nbmeta

A CLI for managing a small JSON metadata block embedded in the `description`
field of a NetBox IP Address entry.

## What it does

Given a host's FQDN, `nbmeta`:

1. Looks up the matching IP Address in NetBox by its `dns_name` field,
   restricted to entries owned by one of the owners listed in `NETBOX_OWNERS`.
2. Reads any JSON object already leading that IP Address's `description`
   field (any trailing free text after the JSON is left untouched).
3. Shallow-merges in whatever fields you pass on the command line — only the
   fields you supply are changed; everything else is preserved.
4. Writes the updated description back to NetBox via its REST API.
5. Prints a success or error message and exits with the matching status code.

The metadata block only ever holds five keys, all optional, each with a
default that's applied on first-time creation only:

| Key       | Type    | Default              |
|-----------|---------|----------------------|
| `role`    | string  | `default`            |
| `env`     | string  | `prod_a`             |
| `group`   | string  | *(same as `role`)*   |
| `nagios`  | boolean | `true`               |
| `ansible` | boolean | `true`               |

`role` is the playbook to run against the host, `env` is the branch the
playbook is sourced from, and `nagios`/`ansible` control whether the host
should be monitored by Nagios / managed by the Ansible controller. `group`
is only meaningful if sync-inventory's `--role` has a matching
`group_structure/<role>.yml` describing a nested group shape — it names
which node of that shape the host belongs to, and is otherwise ignored. If
`--group` isn't passed, it defaults to whatever `role` ends up being (either
the `--role` you passed, or `role`'s own default/existing value).

`env` is sanitized before being stored: any `/` or `-` in the value is
converted to `_` (e.g. `--env feature/foo-bar` is stored as `feature_foo_bar`).

Defaults are only applied to fill in keys that are missing after the merge —
they never overwrite a value you already set, so partial updates (e.g. just
flipping `--nagios false`) are safe.

## Install

Requires Python 3.9+.

```bash
git clone <this-repo>
cd nbmeta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `nbmeta` command into your virtualenv.

### Configuration

`nbmeta` reads its NetBox connection details and search scope from the
environment:

```bash
export NETBOX_URL=https://netbox.example.com
export NETBOX_TOKEN=your-api-token
export NETBOX_OWNERS=team-a,team-b
```

- `NETBOX_URL` / `NETBOX_TOKEN` — your NetBox instance and API token.
- `NETBOX_OWNERS` — comma-separated list of NetBox owner names. Lookups and
  listings are restricted to IP Addresses owned by one of these.

## Quick guide

Tag a new host with all defaults (`role=default`, `env=prod_a`, `nagios=true`, `ansible=true`):

```bash
nbmeta host.example.com
```

Set the role on a new host (still fills in the defaults for `env`, `nagios`, `ansible`):

```bash
nbmeta host.example.com --role proxmox
```

Update just one field on a host that's already tagged (everything else is left alone):

```bash
nbmeta host.example.com --nagios false
```

Preview a change without writing it to NetBox:

```bash
nbmeta host.example.com --env staging --dry-run
```

Skip the confirmation prompt (useful in scripts):

```bash
nbmeta host.example.com --role proxmox -y
```

List entries owned by `NETBOX_OWNERS` that at least have `role` configured:

```bash
nbmeta --list
```

List every entry owned by `NETBOX_OWNERS`, including ones with no role
configured at all:

```bash
nbmeta --list-all   # or: nbmeta -la
```

Either form accepts a regex as the fqdn argument to only list entries whose
hostname starts with it (matched against the start of `dns_name`):

```bash
nbmeta --list wiki
nbmeta --list-all wiki
```

By default (without `-y`/`--yes`), `nbmeta` prints the current and proposed
description and asks for confirmation before saving:

```
$ nbmeta host.example.com --role proxmox
IP Address:          10.0.0.5/32 (host.example.com)
Current description:
New description:     {"ansible": true, "env": "prod_a", "nagios": true, "role": "proxmox"}
Apply this change? [y/N]
```

Run `nbmeta --help` for the full list of flags.

## To Do

- Publish this as a proper Python package so it can be installed without
  cloning the repository. Still in development.
