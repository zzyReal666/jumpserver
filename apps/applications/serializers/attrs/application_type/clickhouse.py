from rest_framework import serializers
from django.utils.translation import ugettext_lazy as _

from ..application_category import DBSerializer

__all__ = ['ClickHouseSerializer']


class ClickHouseSerializer(DBSerializer):
    port = serializers.IntegerField(default=9000, label=_('Port'), allow_null=True)
