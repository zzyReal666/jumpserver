# coding: utf-8
#

from orgs.mixins.api import OrgBulkModelViewSet
from orgs.mixins import generics
from common.exceptions import JMSException
from ..hands import IsOrgAdmin, IsAppUser
from .. import models
from ..serializers import RemoteAppSerializer, RemoteAppConnectionInfoSerializer


__all__ = [
    'RemoteAppViewSet', 'RemoteAppConnectionInfoApi',
]


class RemoteAppViewSet(OrgBulkModelViewSet):
    model = models.RemoteApp
    filter_fields = ('name', 'type', 'comment')
    search_fields = filter_fields
    permission_classes = (IsOrgAdmin,)
    serializer_class = RemoteAppSerializer


class RemoteAppConnectionInfoApi(generics.RetrieveAPIView):
    model = models.Application
    permission_classes = (IsAppUser, )
    serializer_class = RemoteAppConnectionInfoSerializer

    def get_object(self):
        obj = super().get_object()
        if not models.Category.is_remote_app(obj.category):
            raise JMSException('The request instance is not of category `remote_app`')
        return obj
