# -*- coding: utf-8 -*-
#

from rest_framework import serializers

from django.db.models import Count
from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from perms.models import AssetPermission, Action

__all__ = [
    'AssetPermissionSerializer',
    'ActionsField',
]


class ActionsField(serializers.MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = Action.CHOICES
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        return Action.value_to_choices(value)

    def to_internal_value(self, data):
        if data is None:
            return data
        return Action.choices_to_value(data)


class ActionsDisplayField(ActionsField):
    def to_representation(self, value):
        values = super().to_representation(value)
        choices = dict(Action.CHOICES)
        return [choices.get(i) for i in values]


class AssetPermissionSerializer(BulkOrgResourceModelSerializer):
    actions = ActionsField(required=False, allow_null=True)
    is_valid = serializers.BooleanField()
    is_expired = serializers.BooleanField()

    class Meta:
        model = AssetPermission
        mini_fields = ['id', 'name']
        small_fields = mini_fields + [
            'is_active', 'actions', 'created_by', 'date_created'
        ]
        m2m_fields = [
            'users', 'user_groups', 'assets', 'nodes', 'system_users',
            'users_amount', 'user_groups_amount', 'assets_amount', 'nodes_amount', 'system_users_amount',
        ]
        fields = small_fields + m2m_fields
        read_only_fields = ['created_by', 'date_created']

    @classmethod
    def setup_eager_loading(cls, queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.annotate(
            users_amount=Count('users'), user_groups_amount=Count('user_groups'),
            assets_amount=Count('assets'), nodes_amount=Count('nodes'),
            system_users_amount=Count('system_users')
        )
        return queryset
