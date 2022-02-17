# ~*~ coding: utf-8 ~*~

from django.views.generic.detail import SingleObjectMixin
from django.utils.translation import ugettext as _
from rest_framework.views import APIView, Response
from rest_framework.serializers import ValidationError

from common.utils import get_logger
from orgs.mixins.api import OrgBulkModelViewSet
from ..models import Domain, Gateway
from .. import serializers


logger = get_logger(__file__)
__all__ = ['DomainViewSet', 'GatewayViewSet', "GatewayTestConnectionApi"]


class DomainViewSet(OrgBulkModelViewSet):
    model = Domain
    filterset_fields = ("name", )
    search_fields = filterset_fields
    serializer_class = serializers.DomainSerializer
    ordering_fields = ('name',)
    ordering = ('name', )

    def get_serializer_class(self):
        if self.request.query_params.get('gateway'):
            return serializers.DomainWithGatewaySerializer
        return super().get_serializer_class()


class GatewayViewSet(OrgBulkModelViewSet):
    model = Gateway
    filterset_fields = ("domain__name", "name", "username", "ip", "domain")
    search_fields = ("domain__name", "name", "username", "ip")
    serializer_class = serializers.GatewaySerializer


class GatewayTestConnectionApi(SingleObjectMixin, APIView):
    object = None
    rbac_perms = {
        'POST': 'assets.change_gateway'
    }

    def post(self, request, *args, **kwargs):
        self.object = self.get_object(Gateway.objects.all())
        local_port = self.request.data.get('port') or self.object.port
        try:
            local_port = int(local_port)
        except ValueError:
            raise ValidationError({'port': _('Number required')})
        ok, e = self.object.test_connective(local_port=local_port)
        if ok:
            return Response("ok")
        else:
            return Response({"error": e}, status=400)
