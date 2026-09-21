# netbox-ipam-grid

A small NetBox plugin that lets you assign an IP address **directly to a
device** through one simple form — with a searchable *"choose a device"*
dropdown and an IP **state** selector — while the plugin does the native-IPAM
plumbing for you.

Target: **NetBox Community 4.6.x** (tested against 4.6.7 · Python 3.12 · Django 5.2).

## What it does (and why it's built this way)

NetBox never attaches an IP to a device directly — an IP lives on an
*interface*, and the device inherits it. That interface step is the friction.
This plugin removes the friction **without** abandoning IPAM:

1. You pick a device and type an IP, choosing its state (Active, Reserved,
   Deprecated, DHCP, …).
2. The plugin ensures a management interface exists on that device
   (created automatically if needed).
3. It creates a **real `ipam.IPAddress`** on that interface with the state you chose.
4. If you tick *"Set as primary IP"* (or the device has no primary of that
   family yet), it sets the device's `primary_ip4`/`primary_ip6`.

Because the IPs are genuine IPAM objects, you keep uniqueness checks, prefixes,
the REST/GraphQL API — and any primary IP shows up in the device's native
**Management** panel ("Primary IPv4 / Primary IPv6" rows).

The plugin defines **no new database models**, so there are no migrations.

### One honest limitation

The plugin can add its **own card** to the device page (it does — a "IPAM Grid"
card across the bottom), but the NetBox plugin API cannot insert rows *inside*
the native Management panel; that's disallowed by NetBox core. The primary IP
you set still appears in that panel via the native primary-IP rows.

## Install (development / editable)

Assuming a source install of NetBox at `/opt/netbox`:

```bash
source /opt/netbox/venv/bin/activate
cd netbox-ipam-grid
pip install -e .
```

## Install (production)

```bash
source /opt/netbox/venv/bin/activate
pip install .
```

## Enable the plugin

In `/opt/netbox/netbox/netbox/configuration.py`:

```python
PLUGINS = [
    "netbox_ipam_grid",
]

# Optional — these are the defaults:
PLUGINS_CONFIG = {
    "netbox_ipam_grid": {
        "default_interface_name": "mgmt0",   # interface the IPs are hung on
        "default_interface_type": "virtual", # type used if it must be created
        "auto_set_primary": True,            # auto-set primary when device has none
    },
}
```

No migrations are required (the plugin adds no models), but it's harmless to run:

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
```

Then restart NetBox (`systemctl restart netbox netbox-rq`).

## Usage

* A **IPAM Grid** entry appears in the navigation menu. Its list shows every
  device-assigned IP with columns for address, state, device, and interface.
* Hit **Add** (or the *Add IP* button on a device page) to open the form:
  choose a device from the dropdown, enter the IP, pick its state, optionally
  set it primary.
* Each row has **edit** / **delete** buttons. Editing lets you change the state
  or move the IP to a different device (the plugin re-homes it and cleans up any
  stale primary reference on the old device).
* Every device detail page gets a **IPAM Grid** card listing that device's IPs.

## Permissions

The plugin reads and writes native IPAM objects, so users need the standard
IPAM object permissions:

* `ipam.view_ipaddress`, `ipam.add_ipaddress`, `ipam.change_ipaddress`,
  `ipam.delete_ipaddress`
* Setting a primary IP also touches the device, so `dcim.change_device` is
  needed for that step, and `dcim.add_interface` if the management interface
  must be created.

## Renaming the plugin

Prefer a different name than `netbox_ipam_grid`? Rename the package directory
and update `name`/`base_url` in `netbox_ipam_grid/__init__.py`, the
`name`/`packages` entries in `pyproject.toml`, and the `plugins:...` URL names.

## Notes / edge cases

* Bare host addresses (e.g. `192.0.2.10`) are normalised to `/32` (or `/128`
  for IPv6). Include a prefix length if you want a specific mask.
* All plugin-managed IPs share one interface per device (`default_interface_name`).
  If you need multiple interfaces, that's a good first extension point.
* Moving an IP between devices reassigns its interface; the old management
  interface is left in place (empty) rather than deleted.

---

## v0.2 — Subnets & visual grid

This release adds a phpIPAM-style subnet grid plus list controls, still all on
native IPAM (a "subnet" is an `ipam.Prefix`; each cell is an `ipam.IPAddress`).

* **Subnets** (new nav item): a list of prefixes with an **Add Subnet** button.
  Click any subnet to open its grid.
* **Subnet grid**: every host address in the prefix as a coloured cell —
  green = available, otherwise coloured by IP state, with the device shown on
  hover. Click a cell to **reserve** it (choose a state, no device) or
  **assign it to a device** (runs the same interface/primary automation).
* **IPAM Grid list** now has **Add**, **Import** (CSV), and **Export** buttons.

### Notes / limits
* The grid renders IPv4 subnets up to `grid_max_hosts` addresses (default 1024,
  i.e. up to a /22). Larger or IPv6 subnets show a notice instead — rendering
  tens of thousands of cells is slow and unreadable.
* CSV **Import** columns: `address, status, device, description` (device is a
  name and is optional; blank = reserve only).
* Creating/assigning touches native IPAM + devices, so users need the matching
  `ipam.*` and `dcim.*` permissions (add/change on ipaddress, prefix, interface,
  device).
