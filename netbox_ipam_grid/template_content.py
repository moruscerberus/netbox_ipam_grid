"""
Injects a card onto every device's detail page listing the IPs managed here.

Note on placement: the NetBox plugin API can only add a plugin's *own* card to
the left column, right column, or full-width bottom of a core page. It cannot
insert rows inside the native "Management" panel (NetBox forbids modifying core
content). The primary IP you set via this plugin still appears in that native
panel's "Primary IPv4 / IPv6" rows, because those are driven by the device's
real primary_ip fields, which we populate.
"""

from ipam.models import IPAddress
from netbox.plugins import PluginTemplateExtension


class DeviceIPCard(PluginTemplateExtension):
    models = ["dcim.device"]  # v4.x: plural attribute, list of "app.model" strings

    def full_width_page(self):
        device = self.context["object"]
        ips = (
            IPAddress.objects.filter(
                assigned_object_type__app_label="dcim",
                assigned_object_type__model="interface",
                assigned_object_id__in=device.interfaces.values_list("id", flat=True),
            )
            .order_by("address")
        )
        return self.render(
            "netbox_ipam_grid/inc/device_ips.html",
            extra_context={
                "device_ips": ips,
                "primary_ip4_id": device.primary_ip4_id,
                "primary_ip6_id": device.primary_ip6_id,
            },
        )


template_extensions = [DeviceIPCard]
