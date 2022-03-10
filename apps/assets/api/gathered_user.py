# -*- coding: utf-8 -*-
#

from orgs.mixins.api import OrgModelViewSet
from assets.models import GatheredUser

from ..serializers import GatheredUserSerializer
from ..filters import AssetRelatedByNodeFilterBackend


__all__ = ['GatheredUserViewSet']


class GatheredUserViewSet(OrgModelViewSet):
    model = GatheredUser
    serializer_class = GatheredUserSerializer
    extra_filter_backends = [AssetRelatedByNodeFilterBackend]

    filterset_fields = ['asset', 'username', 'present', 'asset__ip', 'asset__hostname', 'asset_id']
    search_fields = ['username', 'asset__ip', 'asset__hostname']
