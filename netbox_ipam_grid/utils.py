"""
Shared native-IPAM automation helpers, used by the forms.

Assigning an IP to a Device or a Virtual Machine lives in one place here, so the
grid cell form, the device-IP form and bulk import all behave identically.
"""

from django.db.models import Q

from dcim.choices import InterfaceTypeChoices
from dcim.models import Device, Interface
from virtualization.models import VirtualMachine, VMInterface
from netbox.plugins import get_plugin_config


def get_or_create_mgmt_interface(device):
    """Return (creating if needed) the interface the plugin hangs IPs on."""
    name = get_plugin_config("netbox_ipam_grid", "default_interface_name")
    itype = (
        get_plugin_config("netbox_ipam_grid", "default_interface_type")
        or InterfaceTypeChoices.TYPE_VIRTUAL
    )
    interface, _ = Interface.objects.get_or_create(
        device=device,
        name=name,
        defaults={"type": itype},
    )
    return interface


def get_or_create_vm_interface(vm):
    """Return (creating if needed) the VM interface the plugin hangs IPs on."""
    name = get_plugin_config("netbox_ipam_grid", "default_interface_name")
    interface, _ = VMInterface.objects.get_or_create(
        virtual_machine=vm,
        name=name,
    )
    return interface


def clear_stale_primary(ip, keep_device=None):
    """Remove this IP from any device's primary_ip4/6 (optionally except one)."""
    qs = Device.objects.filter(Q(primary_ip4=ip) | Q(primary_ip6=ip))
    if keep_device is not None:
        qs = qs.exclude(pk=keep_device.pk)
    for dev in qs:
        changed = False
        if dev.primary_ip4_id == ip.pk:
            dev.primary_ip4 = None
            changed = True
        if dev.primary_ip6_id == ip.pk:
            dev.primary_ip6 = None
            changed = True
        if changed:
            dev.save()


def clear_stale_vm_primary(ip, keep_vm=None):
    """Remove this IP from any VM's primary_ip4/6 (optionally except one)."""
    qs = VirtualMachine.objects.filter(Q(primary_ip4=ip) | Q(primary_ip6=ip))
    if keep_vm is not None:
        qs = qs.exclude(pk=keep_vm.pk)
    for vm in qs:
        changed = False
        if vm.primary_ip4_id == ip.pk:
            vm.primary_ip4 = None
            changed = True
        if vm.primary_ip6_id == ip.pk:
            vm.primary_ip6 = None
            changed = True
        if changed:
            vm.save()


def set_primary(obj, ip):
    """Set obj.primary_ip4/6 = ip (obj is a Device or a VirtualMachine)."""
    attr = "primary_ip4" if ip.family == 4 else "primary_ip6"
    setattr(obj, attr, ip)
    obj.save()


def apply_assignment(ip, device=None, vm=None, set_as_primary=False):
    """
    Attach an IP to a Device OR a Virtual Machine (via the plugin's management
    interface), or leave it unassigned (a bare reservation) if both are None.

    Handles switching an existing IP between a device and a VM, cleaning up any
    stale primary-IP references on the object it left behind.

    The caller is responsible for form.save_m2m() afterwards if needed.
    """
    auto = get_plugin_config("netbox_ipam_grid", "auto_set_primary") or False

    # --- reservation / unassign -------------------------------------------
    if device is None and vm is None:
        if ip.pk:
            clear_stale_primary(ip)
            clear_stale_vm_primary(ip)
        ip.assigned_object = None
        ip.save()
        return ip

    # --- assign to a device -----------------------------------------------
    if device is not None:
        interface = get_or_create_mgmt_interface(device)
        if ip.pk:
            clear_stale_primary(ip, keep_device=device)
            clear_stale_vm_primary(ip)  # in case it was on a VM before
        ip.assigned_object = interface
        ip.save()

        family_attr = "primary_ip4" if ip.family == 4 else "primary_ip6"
        has_primary = getattr(device, f"{family_attr}_id") is not None
        if set_as_primary or (auto and not has_primary):
            set_primary(device, ip)
        elif not set_as_primary and getattr(device, f"{family_attr}_id") == ip.pk:
            setattr(device, family_attr, None)
            device.save()
        return ip

    # --- assign to a virtual machine --------------------------------------
    interface = get_or_create_vm_interface(vm)
    if ip.pk:
        clear_stale_vm_primary(ip, keep_vm=vm)
        clear_stale_primary(ip)  # in case it was on a device before
    ip.assigned_object = interface
    ip.save()

    family_attr = "primary_ip4" if ip.family == 4 else "primary_ip6"
    has_primary = getattr(vm, f"{family_attr}_id") is not None
    if set_as_primary or (auto and not has_primary):
        set_primary(vm, ip)
    elif not set_as_primary and getattr(vm, f"{family_attr}_id") == ip.pk:
        setattr(vm, family_attr, None)
        vm.save()
    return ip
