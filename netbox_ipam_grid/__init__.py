"""
netbox_ipam_grid
=================

A small NetBox plugin that lets you assign IP addresses *directly to a device*
through one simple form, while doing the tedious native-IPAM plumbing for you
behind the scenes:

    pick a device  ->  the plugin ensures a management interface exists,
                       creates a real ipam.IPAddress on it, sets its state,
                       and (optionally) marks it as the device's primary IP.

Because the plugin operates on genuine ``ipam.IPAddress`` objects, those IPs
remain first-class citizens of NetBox IPAM (uniqueness checks, prefixes, the
REST/GraphQL API, etc.), and any IP you flag as primary populates the native
"Primary IPv4 / Primary IPv6" rows in a device's Management panel.

The plugin defines NO new database models, so there is nothing to migrate.
"""

from netbox.plugins import PluginConfig

__version__ = "0.3.0"


class DeviceIPsConfig(PluginConfig):
    name = "netbox_ipam_grid"
    verbose_name = "IPAM Grid"
    description = (
        "Assign IP addresses directly to devices with an automated, "
        "native-IPAM workflow."
    )
    version = __version__
    author = "Jörgen Gullstrand"
    author_email = "moruscerberus@gmail.com"
    base_url = "device-ips"

    # Targeting NetBox Community 4.6.x.
    min_version = "4.6.0"
    max_version = "4.7.99"

    default_settings = {
        # Name of the interface the plugin creates/uses on each device to
        # anchor the IP. (Native NetBox requires an IP to be attached to an
        # interface before it can become a device's primary IP.)
        "default_interface_name": "mgmt0",
        # Interface type used when the plugin has to create that interface.
        "default_interface_type": "virtual",
        # If True, when a device has no primary IP of the address's family yet,
        # a newly-assigned IP is set as the primary automatically.
        "auto_set_primary": True,
        # Largest IPv4 subnet (host count) the visual grid will render. 1024 =
        # up to a /22. Bigger subnets show a notice instead (rendering tens of
        # thousands of cells is slow and unreadable).
        "grid_max_hosts": 1024,
    }

    def ready(self):
        super().ready()
        # --- UNSUPPORTED: add "Subnets" under the core IPAM menu -------------
        # This build has no MENUS list; menus are individual objects rendered
        # via a cached get_menus(). We mutate IPAM_MENU in place and clear that
        # cache. Fully guarded so it can never stop NetBox from starting.
        try:
            from netbox.navigation import menu as navmenu
            ipam = navmenu.IPAM_MENU
            MenuGroup = navmenu.MenuGroup
            MenuItem = navmenu.MenuItem
        except Exception:
            return
        link = "plugins:netbox_ipam_grid:subnets"
        try:
            for g in ipam.groups:
                if getattr(g, "label", None) == "Custom" and any(
                    getattr(i, "link", None) == link for i in getattr(g, "items", ())
                ):
                    return  # already added
        except Exception:
            pass
        try:
            try:
                item = MenuItem(link=link, link_text="Subnets",
                                permissions=["ipam.view_prefix"])
            except TypeError:
                item = MenuItem(link=link, link_text="Subnets")
            try:
                group = MenuGroup(label="Custom", items=(item,))
            except TypeError:
                group = MenuGroup("Custom", (item,))
            new_groups = tuple(ipam.groups) + (group,)
            try:
                ipam.groups = new_groups
            except Exception:
                object.__setattr__(ipam, "groups", new_groups)
            get_menus = getattr(navmenu, "get_menus", None)
            if get_menus is not None and hasattr(get_menus, "cache_clear"):
                get_menus.cache_clear()
        except Exception:
            import logging
            logging.getLogger("netbox_ipam_grid").warning(
                "Could not inject Subnets into IPAM menu.", exc_info=True
            )

config = DeviceIPsConfig
