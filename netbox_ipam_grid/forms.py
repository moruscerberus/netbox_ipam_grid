"""
Forms for the plugin.

  * DeviceIPForm  - assign an IP to a device (device required). Used by the
                    IPAM Grid "Add/Edit" pages.
  * IPCellForm    - reserve/assign a single address from the subnet grid
                    (device optional; leave blank to just reserve).
  * PrefixForm    - create a "subnet" (a native ipam.Prefix).
  * DeviceIPImportForm - CSV bulk import of IPAM Grid.

All the IPAM automation lives in utils.apply_assignment().
"""

import netaddr
from django import forms

from dcim.models import Device
from virtualization.models import VirtualMachine
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress, Prefix
from netbox.forms import NetBoxModelForm, NetBoxModelImportForm
from utilities.forms.fields import CSVModelChoiceField, DynamicModelChoiceField

from . import utils


def _normalise_address(value):
    """Accept a bare host address and normalise to CIDR (/32 or /128)."""
    value = str(value).strip()
    try:
        net = netaddr.IPNetwork(value)
    except (netaddr.AddrFormatError, ValueError):
        raise forms.ValidationError(
            "Enter a valid IPv4 or IPv6 address, optionally with a prefix length."
        )
    return str(net)


class DeviceIPForm(NetBoxModelForm):
    device = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        label="Device",
        help_text="Choose the device this IP address belongs to.",
    )
    set_as_primary = forms.BooleanField(
        required=False,
        label="Set as primary IP",
        help_text="Make this the device's primary IP for its address family.",
    )

    class Meta:
        model = IPAddress
        fields = ("address", "status", "description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = IPAddressStatusChoices
        if not (getattr(self, "instance", None) and self.instance.pk):
            self.fields["set_as_primary"].initial = True
        instance = getattr(self, "instance", None)

        from dcim.models import Interface
        from virtualization.models import VMInterface

        if instance and instance.pk:
            if isinstance(instance.assigned_object, Interface):
                dev = instance.assigned_object.device
                self.fields["device"].initial = dev.pk
                if instance.pk in (dev.primary_ip4_id, dev.primary_ip6_id):
                    self.fields["set_as_primary"].initial = True

            elif isinstance(instance.assigned_object, VMInterface):
                vm = instance.assigned_object.virtual_machine
                if "vm" in self.fields:
                    self.fields["vm"].initial = vm.pk
                if instance.pk in (vm.primary_ip4_id, vm.primary_ip6_id):
                    self.fields["set_as_primary"].initial = True

    def clean_address(self):
        return _normalise_address(self.cleaned_data["address"])

    def save(self, commit=True):
        ip = super().save(commit=False)
        if commit:
            utils.apply_assignment(ip, self.cleaned_data["device"], None,
                                   self.cleaned_data.get("set_as_primary"))
            self.save_m2m()
        return ip


class IPCellForm(NetBoxModelForm):
    device = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label="Device",
        help_text="Optional. Leave blank to just reserve this address without a device.",
    )
    vm = DynamicModelChoiceField(
        queryset=VirtualMachine.objects.all(),
        required=False,
        label="Virtual Machine",
        help_text="Optional. Leave blank to assign to a VM or reserve only.",
    )

    set_as_primary = forms.BooleanField(
        required=False,
        label="Set as primary IP",
    )

    class Meta:
        model = IPAddress
        fields = ("address", "status", "description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = IPAddressStatusChoices
        if not (getattr(self, "instance", None) and self.instance.pk):
            self.fields["set_as_primary"].initial = True
        # The address is pre-selected by the grid cell; keep it visible but
        # discourage editing.
        self.fields["address"].help_text = "The address you selected in the grid."
        instance = getattr(self, "instance", None)
        from dcim.models import Interface
        from virtualization.models import VMInterface
        if instance and instance.pk:
            ao = instance.assigned_object
            if isinstance(ao, Interface):
                dev = ao.device
                self.fields["device"].initial = dev.pk
                if instance.pk in (dev.primary_ip4_id, dev.primary_ip6_id):
                    self.fields["set_as_primary"].initial = True
            elif isinstance(ao, VMInterface):
                vm = ao.virtual_machine
                self.fields["vm"].initial = vm.pk
                if instance.pk in (vm.primary_ip4_id, vm.primary_ip6_id):
                    self.fields["set_as_primary"].initial = True

    def clean_address(self):
        return _normalise_address(self.cleaned_data["address"])

    def save(self, commit=True):
        ip = super().save(commit=False)
        if commit:
            utils.apply_assignment(ip, self.cleaned_data.get("device"), self.cleaned_data.get("vm"),
                                   self.cleaned_data.get("set_as_primary"))
            self.save_m2m()
        return ip


class PrefixForm(NetBoxModelForm):
    """Create a 'subnet'. This is just a native ipam.Prefix."""

    class Meta:
        model = Prefix
        fields = ("prefix", "status", "description")


class DeviceIPImportForm(NetBoxModelImportForm):
    device = CSVModelChoiceField(
        queryset=Device.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Device name (optional; blank = reserve only).",
    )

    class Meta:
        model = IPAddress
        fields = ("address", "status", "device", "description")

    def save(self, commit=True):
        ip = super().save(commit=False)
        if commit:
            utils.apply_assignment(ip, self.cleaned_data.get("device"), None, False)
            self.save_m2m()
        return ip
