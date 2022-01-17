# -*- coding: utf-8 -*-
#
from rest_framework import serializers
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from ..models import Asset, Node, Platform, SystemUser

__all__ = [
    'AssetSerializer', 'AssetSimpleSerializer', 'MiniAssetSerializer',
    'ProtocolsField', 'PlatformSerializer',
    'AssetTaskSerializer', 'AssetsTaskSerializer', 'ProtocolsField',
]


class ProtocolField(serializers.RegexField):
    protocols = '|'.join(dict(Asset.Protocol.choices).keys())
    default_error_messages = {
        'invalid': _('Protocol format should {}/{}').format(protocols, '1-65535')
    }
    regex = r'^(%s)/(\d{1,5})$' % protocols

    def __init__(self, *args, **kwargs):
        super().__init__(self.regex, **kwargs)


def validate_duplicate_protocols(values):
    errors = []
    names = []

    for value in values:
        if not value or '/' not in value:
            continue
        name = value.split('/')[0]
        if name in names:
            errors.append(_("Protocol duplicate: {}").format(name))
        names.append(name)
        errors.append('')
    if any(errors):
        raise serializers.ValidationError(errors)


class ProtocolsField(serializers.ListField):
    default_validators = [validate_duplicate_protocols]

    def __init__(self, *args, **kwargs):
        kwargs['child'] = ProtocolField()
        kwargs['allow_null'] = True
        kwargs['allow_empty'] = True
        kwargs['min_length'] = 1
        kwargs['max_length'] = 4
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        if not value:
            return []
        return value.split(' ')


class AssetSerializer(BulkOrgResourceModelSerializer):
    platform = serializers.SlugRelatedField(
        slug_field='name', queryset=Platform.objects.all(), label=_("Platform")
    )
    protocols = ProtocolsField(label=_('Protocols'), required=False, default=['ssh/22'])
    domain_display = serializers.ReadOnlyField(source='domain.name', label=_('Domain name'))
    nodes_display = serializers.ListField(
        child=serializers.CharField(), label=_('Nodes name'), required=False
    )
    labels_display = serializers.ListField(
        child=serializers.CharField(), label=_('Labels name'), required=False, read_only=True
    )

    """
    资产的数据结构
    """

    class Meta:
        model = Asset
        fields_mini = ['id', 'hostname', 'ip', 'platform', 'protocols']
        fields_small = fields_mini + [
            'protocol', 'port', 'protocols', 'is_active',
            'public_ip', 'number', 'comment',
        ]
        fields_hardware = [
            'vendor', 'model', 'sn', 'cpu_model', 'cpu_count',
            'cpu_cores', 'cpu_vcpus', 'memory', 'disk_total', 'disk_info',
            'os', 'os_version', 'os_arch', 'hostname_raw',
            'cpu_info', 'hardware_info',
        ]
        fields_fk = [
            'domain', 'domain_display', 'platform', 'admin_user', 'admin_user_display'
        ]
        fields_m2m = [
            'nodes', 'nodes_display', 'labels', 'labels_display',
        ]
        read_only_fields = [
            'connectivity', 'date_verified', 'cpu_info', 'hardware_info',
            'created_by', 'date_created',
        ]
        fields = fields_small + fields_hardware + fields_fk + fields_m2m + read_only_fields
        extra_kwargs = {
            'protocol': {'write_only': True},
            'port': {'write_only': True},
            'hardware_info': {'label': _('Hardware info'), 'read_only': True},
            'admin_user_display': {'label': _('Admin user display'), 'read_only': True},
            'cpu_info': {'label': _('CPU info')},
        }

    def get_fields(self):
        fields = super().get_fields()

        admin_user_field = fields.get('admin_user')
        # 因为 mixin 中对 fields 有处理，可能不需要返回 admin_user
        if admin_user_field:
            admin_user_field.queryset = SystemUser.objects.filter(type=SystemUser.Type.admin)
        return fields

    @classmethod
    def setup_eager_loading(cls, queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.prefetch_related('domain', 'platform', 'admin_user')
        queryset = queryset.prefetch_related('nodes', 'labels')
        return queryset

    def compatible_with_old_protocol(self, validated_data):
        protocols_data = validated_data.pop("protocols", [])

        # 兼容老的api
        name = validated_data.get("protocol")
        port = validated_data.get("port")
        if not protocols_data and name and port:
            protocols_data.insert(0, '/'.join([name, str(port)]))
        elif not name and not port and protocols_data:
            protocol = protocols_data[0].split('/')
            validated_data["protocol"] = protocol[0]
            validated_data["port"] = int(protocol[1])
        if protocols_data:
            validated_data["protocols"] = ' '.join(protocols_data)

    def perform_nodes_display_create(self, instance, nodes_display):
        if not nodes_display:
            return
        nodes_to_set = []
        for full_value in nodes_display:
            node = Node.objects.filter(full_value=full_value).first()
            if node:
                nodes_to_set.append(node)
            else:
                node = Node.create_node_by_full_value(full_value)
            nodes_to_set.append(node)
        instance.nodes.set(nodes_to_set)

    def create(self, validated_data):
        self.compatible_with_old_protocol(validated_data)
        nodes_display = validated_data.pop('nodes_display', '')
        instance = super().create(validated_data)
        self.perform_nodes_display_create(instance, nodes_display)
        return instance

    def update(self, instance, validated_data):
        nodes_display = validated_data.pop('nodes_display', '')
        self.compatible_with_old_protocol(validated_data)
        instance = super().update(instance, validated_data)
        self.perform_nodes_display_create(instance, nodes_display)
        return instance


class MiniAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = AssetSerializer.Meta.fields_mini


class PlatformSerializer(serializers.ModelSerializer):
    meta = serializers.DictField(required=False, allow_null=True, label=_('Meta'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO 修复 drf SlugField RegexValidator bug，之后记得删除
        validators = self.fields['name'].validators
        if isinstance(validators[-1], RegexValidator):
            validators.pop()

    class Meta:
        model = Platform
        fields = [
            'id', 'name', 'base', 'charset',
            'internal', 'meta', 'comment'
        ]


class AssetSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'hostname', 'ip', 'port', 'connectivity', 'date_verified']


class AssetsTaskSerializer(serializers.Serializer):
    ACTION_CHOICES = (
        ('refresh', 'refresh'),
        ('test', 'test'),
    )
    task = serializers.CharField(read_only=True)
    action = serializers.ChoiceField(choices=ACTION_CHOICES, write_only=True)
    assets = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects, required=False, allow_empty=True, many=True
    )


class AssetTaskSerializer(AssetsTaskSerializer):
    ACTION_CHOICES = tuple(list(AssetsTaskSerializer.ACTION_CHOICES) + [
        ('push_system_user', 'push_system_user'),
        ('test_system_user', 'test_system_user')
    ])
    action = serializers.ChoiceField(choices=ACTION_CHOICES, write_only=True)
    asset = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects, required=False, allow_empty=True, many=False
    )
    system_users = serializers.PrimaryKeyRelatedField(
        queryset=SystemUser.objects, required=False, allow_empty=True, many=True
    )
