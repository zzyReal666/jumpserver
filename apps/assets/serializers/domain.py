# -*- coding: utf-8 -*-
#
from rest_framework import serializers

from common.serializers import AdaptedBulkListSerializer
from orgs.mixins.serializers import BulkOrgResourceModelSerializer

from ..models import Domain, Gateway
from .base import AuthSerializerMixin


class DomainSerializer(BulkOrgResourceModelSerializer):
    asset_count = serializers.SerializerMethodField()
    gateway_count = serializers.SerializerMethodField()

    class Meta:
        model = Domain
        fields_mini = ['id', 'name']
        fields_small = fields_mini + [
            'comment', 'date_created'
        ]
        fields_m2m = [
            'asset_count', 'assets', 'gateway_count',
        ]
        fields = fields_small + fields_m2m
        read_only_fields = ('asset_count', 'gateway_count', 'date_created')
        extra_kwargs = {
            'assets': {'required': False}
        }
        list_serializer_class = AdaptedBulkListSerializer

    @staticmethod
    def get_asset_count(obj):
        return obj.assets.count()

    @staticmethod
    def get_gateway_count(obj):
        return obj.gateway_set.all().count()


class GatewaySerializer(AuthSerializerMixin, BulkOrgResourceModelSerializer):
    class Meta:
        model = Gateway
        list_serializer_class = AdaptedBulkListSerializer
        fields = [
            'id', 'name', 'ip', 'port', 'protocol', 'username', 'password',
            'private_key', 'public_key', 'domain', 'is_active', 'date_created',
            'date_updated', 'created_by', 'comment',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol_limit_to_ssh()

    def protocol_limit_to_ssh(self):
        protocol_field = self.fields['protocol']
        choices = protocol_field.choices
        choices.pop('rdp')
        protocol_field._choices = choices


class GatewayWithAuthSerializer(GatewaySerializer):
    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        fields.extend(
            ['password', 'private_key']
        )
        return fields




class DomainWithGatewaySerializer(BulkOrgResourceModelSerializer):
    gateways = GatewayWithAuthSerializer(many=True, read_only=True)

    class Meta:
        model = Domain
        fields = '__all__'
