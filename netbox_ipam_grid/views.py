"""
Views for the plugin.

IPAM Grid:  list / add / edit / delete / import  (native ipam.IPAddress)
Subnets:     ONE page = subnet list + phpIPAM-style grid (native ipam.Prefix)
Grid cell:   reserve / assign a single address
"""

import ipaddress as ipmod
import time

from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.generic import View

from dcim.models import Device, Interface
from virtualization.models import VMInterface
from ipam.models import IPAddress, Prefix
from netbox.plugins import get_plugin_config
from netbox.views import generic

from .forms import DeviceIPForm, DeviceIPImportForm, IPCellForm, PrefixForm

# Theme-friendly palette: map NetBox status colour names to concrete hexes so
# the grid looks intentional regardless of the raw colour name.
TABLER = {
    "blue": "#4299e1", "azure": "#4299e1", "indigo": "#4263eb", "purple": "#ae3ec9",
    "pink": "#d6336c", "red": "#d63939", "orange": "#f76707", "yellow": "#f59f00",
    "green": "#2fb344", "lime": "#74b816", "teal": "#0ca678", "cyan": "#17a2b8",
    "gray": "#667382", "grey": "#667382", "black": "#1d273b", "dark": "#1d273b",
    "white": "#f8f9fa", "light": "#f8f9fa",
}

LEGEND = [
    ("Available", None),
    ("Active", "#4299e1"),
    ("Reserved", "#17a2b8"),
    ("Deprecated", "#d63939"),
    ("DHCP", "#2fb344"),
    ("SLAAC", "#ae3ec9"),
]


def device_assigned_ips():
    return (
        IPAddress.objects.filter(
            assigned_object_type__app_label="dcim",
            assigned_object_type__model="interface",
        ).prefetch_related("assigned_object")
    )


def _build_grid(prefix):
    net = prefix.prefix  # netaddr IPNetwork
    max_hosts = get_plugin_config("netbox_ipam_grid", "grid_max_hosts")
    family = net.version
    size = net.size
    too_big = (family != 4) or (size > max_hosts + 2)

    cells = []
    if not too_big:
        existing = {str(ip.address.ip): ip for ip in prefix.get_child_ips()}
        netobj = ipmod.ip_network(str(net), strict=False)
        edit_base = f"/plugins/device-ips/subnets/{prefix.pk}/ip/"
        hosts = list(netobj.hosts()) or [netobj.network_address]
        for host in hosts:
            s = str(host)
            obj = existing.get(s)
            device = None
            vm = None
            if obj is not None:
                ao = obj.assigned_object
                if isinstance(ao, Interface):
                    device = ao.device
                elif isinstance(ao, VMInterface):
                    vm = ao.virtual_machine
            color = None
            if obj is not None:
                raw = obj.get_status_color()
                color = TABLER.get(raw, raw)
            cells.append({
                "address": s,
                "label": s.split(".")[-1],
                "ip": obj,
                "state": obj.get_status_display() if obj else "Available",
                "color": color,
                "device": device,
                "vm": vm,
                "edit_url": reverse(
                    "plugins:netbox_ipam_grid:ipcell_edit",
                    kwargs={"prefix_pk": prefix.pk, "address": s},
                ),
            })
    used = sum(1 for c in cells if c["ip"])
    total = len(cells)
    pct = round(100 * used / total) if total else 0
    return {
        "cells": cells, "too_big": too_big, "size": size, "family": family,
        "max_hosts": max_hosts, "used": used, "total": total, "pct": pct,
    }


# ----------------------------------------------------------------------------
# IPAM Grid
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# IPAM Grid
# ----------------------------------------------------------------------------
class DeviceIPEditView(generic.ObjectEditView):
    template_name = "netbox_ipam_grid/deviceip_edit.html"
    queryset = IPAddress.objects.all()
    form = DeviceIPForm

    def post(self, request, *args, **kwargs):
        if "release" in request.POST:
            ip = self.get_object()
            if ip.pk:
                Device.objects.filter(primary_ip4=ip).update(primary_ip4=None)
                Device.objects.filter(primary_ip6=ip).update(primary_ip6=None)
                ip.delete()
            return redirect(reverse("plugins:netbox_ipam_grid:subnets") + f"?subnet={self.kwargs["prefix_pk"]}")
        return super().post(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_ipam_grid:subnets")


class DeviceIPDeleteView(generic.ObjectDeleteView):
    queryset = IPAddress.objects.all()

    def post(self, request, *args, **kwargs):
        if "release" in request.POST:
            ip = self.get_object()
            if ip.pk:
                Device.objects.filter(primary_ip4=ip).update(primary_ip4=None)
                Device.objects.filter(primary_ip6=ip).update(primary_ip6=None)
                ip.delete()
            return redirect(reverse("plugins:netbox_ipam_grid:subnets") + f"?subnet={self.kwargs["prefix_pk"]}")
        return super().post(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_ipam_grid:subnets")


class DeviceIPImportView(generic.BulkImportView):
    queryset = IPAddress.objects.all()
    model_form = DeviceIPImportForm
    # table = DeviceIPTable

    def post(self, request, *args, **kwargs):
        if "release" in request.POST:
            ip = self.get_object()
            if ip.pk:
                Device.objects.filter(primary_ip4=ip).update(primary_ip4=None)
                Device.objects.filter(primary_ip6=ip).update(primary_ip6=None)
                ip.delete()
            return redirect(reverse("plugins:netbox_ipam_grid:subnets") + f"?subnet={self.kwargs["prefix_pk"]}")
        return super().post(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        return reverse("plugins:netbox_ipam_grid:subnets")


# ----------------------------------------------------------------------------
# Subnets — single page: list (left) + grid (right)
# ----------------------------------------------------------------------------
class SubnetsView(View):
    def get(self, request):
        subnets = Prefix.objects.restrict(request.user, "view").all().order_by("prefix")

        selected = None
        sel_pk = request.GET.get("subnet")
        if sel_pk:
            selected = get_object_or_404(
                Prefix.objects.restrict(request.user, "view"), pk=sel_pk
            )
        elif subnets:
            selected = subnets.first()

        grid = _build_grid(selected) if selected else {}
        return render(request, "netbox_ipam_grid/subnets.html", {
            "subnets": subnets,
            "selected": selected,
            "legend": LEGEND,
            **grid,
        })


class SubnetEditView(generic.ObjectEditView):
    queryset = Prefix.objects.all()
    form = PrefixForm

    def post(self, request, *args, **kwargs):
        if "release" in request.POST:
            ip = self.get_object()
            if ip.pk:
                Device.objects.filter(primary_ip4=ip).update(primary_ip4=None)
                Device.objects.filter(primary_ip6=ip).update(primary_ip6=None)
                ip.delete()
            return redirect(reverse("plugins:netbox_ipam_grid:subnets") + f"?subnet={self.kwargs["prefix_pk"]}")
        return super().post(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        base = reverse("plugins:netbox_ipam_grid:subnets")
        if obj and obj.pk:
            return f"{base}?subnet={obj.pk}"
        return base


# ----------------------------------------------------------------------------
# Grid cell: reserve / assign a single address
# ----------------------------------------------------------------------------
class IPCellEditView(generic.ObjectEditView):
    template_name = "netbox_ipam_grid/deviceip_edit.html"
    queryset = IPAddress.objects.all()
    form = IPCellForm

    def get_object(self, **kwargs):
        prefix = get_object_or_404(Prefix, pk=self.kwargs["prefix_pk"])
        address = self.kwargs["address"]
        mask = prefix.prefix.prefixlen
        for ip in prefix.get_child_ips():
            if str(ip.address.ip) == address:
                return ip
        return IPAddress(address=f"{address}/{mask}")

    def post(self, request, *args, **kwargs):
        if "release" in request.POST:
            ip = self.get_object()
            if ip.pk:
                Device.objects.filter(primary_ip4=ip).update(primary_ip4=None)
                Device.objects.filter(primary_ip6=ip).update(primary_ip6=None)
                ip.delete()
            return redirect(reverse("plugins:netbox_ipam_grid:subnets") + f"?subnet={self.kwargs["prefix_pk"]}")
        return super().post(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        base = reverse("plugins:netbox_ipam_grid:subnets")
        return f"{base}?subnet={self.kwargs['prefix_pk']}"
