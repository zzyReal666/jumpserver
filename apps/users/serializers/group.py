# -*- coding: utf-8 -*-
#
from django.utils.translation import ugettext_lazy as _
from django.db.models import Prefetch
from rest_framework import serializers

from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from django.db.models import Count
from ..models import User, UserGroup
from .. import utils

__all__ = [
    'UserGroupSerializer',
]


class UserGroupSerializer(BulkOrgResourceModelSerializer):
    users = serializers.PrimaryKeyRelatedField(
        required=False, many=True, queryset=User.objects, label=_('User'),
        # write_only=True, # group can return many to many on detail
    )

    class Meta:
        model = UserGroup
        fields_mini = ['id', 'name']
        fields_small = fields_mini + [
            'comment', 'date_created', 'created_by'
        ]
        fields = fields_mini + fields_small + [
            'users', 'users_amount',
        ]
        extra_kwargs = {
            'created_by': {'label': _('Created by'), 'read_only': True},
            'users_amount': {'label': _('Users amount')},
            'id': {'label': _('ID')},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_fields_queryset()

    def set_fields_queryset(self):
        users_field = self.fields.get('users')
        if users_field:
            users_field.child_relation.queryset = utils.get_current_org_members()

    @classmethod
    def setup_eager_loading(cls, queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.prefetch_related(
            Prefetch('users', queryset=User.objects.only('id'))
        ).annotate(users_amount=Count('users'))
        return queryset
