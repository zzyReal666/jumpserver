from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from perms.serializers import ActionsField
from perms.models import Action
from assets.models import Asset, SystemUser
from .base import BaseTicketMetaSerializer, BaseTicketMetaApproveSerializerMixin


__all__ = [
    'TicketMetaApplyAssetApplySerializer',
    'TicketMetaApplyAssetApproveSerializer',
]


class TicketMetaApplyAssetSerializer(BaseTicketMetaSerializer):
    # 申请信息
    apply_ip_group = serializers.ListField(
        child=serializers.IPAddressField(), default=list, label=_('IP group')
    )
    apply_hostname_group = serializers.ListField(
        child=serializers.CharField(), default=list, label=_('Hostname group')
    )
    apply_system_user_group = serializers.ListField(
        child=serializers.CharField(), default=list, label=_('System user group')
    )
    apply_actions = ActionsField(
        choices=Action.DB_CHOICES, default=Action.ALL
    )
    apply_date_start = serializers.DateTimeField(
        required=True, label=_('Date start')
    )
    apply_date_expired = serializers.DateTimeField(
        required=True, label=_('Date expired')
    )
    # 审批信息
    approve_assets = serializers.ListField(
        required=True, child=serializers.UUIDField(), label=_('Approve assets')
    )
    approve_system_users = serializers.ListField(
        required=True, child=serializers.UUIDField(), label=_('Approve system users')
    )
    approve_actions = ActionsField(
        required=False, choices=Action.DB_CHOICES, default=Action.ALL
    )
    approve_date_start = serializers.DateTimeField(
        required=True, label=_('Date start')
    )
    approve_date_expired = serializers.DateTimeField(
        required=True, label=_('Date expired')
    )


class TicketMetaApplyAssetApplySerializer(TicketMetaApplyAssetSerializer):

    class Meta:
        fields = [
            'apply_ip_group', 'apply_hostname_group',
            'apply_system_user_group', 'apply_actions',
            'apply_date_start', 'apply_date_expired'
        ]


class TicketMetaApplyAssetApproveSerializer(BaseTicketMetaApproveSerializerMixin,
                                            TicketMetaApplyAssetSerializer):

    class Meta:
        fields = [
            'approve_assets', 'approve_system_users',
            'approve_actions', 'approve_date_start',
            'approve_date_expired'
        ]

    def validate_approve_assets(self, approve_assets):
        assets_id = self.filter_approve_resources(resource_model=Asset, resources_id=approve_assets)
        return assets_id

    def validate_approve_system_users(self, approve_system_users):
        queries = {'protocol__in': SystemUser.ASSET_CATEGORY_PROTOCOLS}
        system_users_id = self.filter_approve_system_users(approve_system_users, queries)
        return system_users_id
