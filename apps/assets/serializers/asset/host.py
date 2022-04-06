from rest_framework import serializers

from .common import AssetSerializer
from assets.models import DeviceInfo, Host

__all__ = ['DeviceSerializer', 'HostSerializer']


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceInfo
        fields = [
            'id', 'vendor', 'model', 'sn', 'cpu_model', 'cpu_count',
            'cpu_cores', 'cpu_vcpus', 'memory', 'disk_total', 'disk_info',
            'os', 'os_version', 'os_arch', 'hostname_raw',
            'cpu_info', 'hardware_info', 'date_updated'
        ]


class HostSerializer(AssetSerializer):
    device_info = DeviceSerializer(read_only=True, allow_null=True)

    class Meta(AssetSerializer.Meta):
        model = Host
        fields = AssetSerializer.Meta.fields + ['device_info']
