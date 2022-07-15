from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request
from common.drf.api import JMSBulkModelViewSet
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404
from assets.models import Asset
from orgs.utils import tmp_to_root_org
from applications.models import Application
from terminal.models import Session
from ..models import Endpoint, EndpointRule
from .. import serializers
from common.permissions import IsValidUserOrConnectionToken


__all__ = ['EndpointViewSet', 'EndpointRuleViewSet']


class SmartEndpointViewMixin:
    get_serializer: callable
    request: Request

    # View 处理过程中用的属性
    target_instance: None
    target_protocol: None

    @action(methods=['get'], detail=False, permission_classes=[IsValidUserOrConnectionToken],
            url_path='smart')
    def smart(self, request, *args, **kwargs):
        self.target_instance = self.get_target_instance()
        self.target_protocol = self.get_target_protocol()
        if not self.target_protocol:
            error = _('Not found protocol query params')
            return Response(data={'error': error}, status=status.HTTP_404_NOT_FOUND)
        endpoint = self.match_endpoint()
        serializer = self.get_serializer(endpoint)
        return Response(serializer.data)

    def match_endpoint(self):
        endpoint = self.match_endpoint_by_label()
        if not endpoint:
            endpoint = self.match_endpoint_by_target_ip()
        return endpoint

    def match_endpoint_by_label(self):
        return Endpoint.match_by_instance_label(self.target_instance, self.target_protocol)

    def match_endpoint_by_target_ip(self):
        # 用来方便测试
        target_ip = self.request.GET.get('target_ip', '')
        if not target_ip and callable(getattr(self.target_instance, 'get_target_ip', None)):
            target_ip = self.target_instance.get_target_ip()
        endpoint = EndpointRule.match_endpoint(target_ip, self.target_protocol, self.request)
        return endpoint

    def get_target_instance(self):
        request = self.request
        asset_id = request.GET.get('asset_id')
        app_id = request.GET.get('app_id')
        session_id = request.GET.get('session_id')
        token_id = request.GET.get('token')
        if token_id:
            from authentication.models import ConnectionToken
            token = ConnectionToken.objects.filter(id=token_id).first()
            if token:
                if token.asset:
                    asset_id = token.asset.id
                elif token.application:
                    app_id = token.application.id
        if asset_id:
            pk, model = asset_id, Asset
        elif app_id:
            pk, model = app_id, Application
        elif session_id:
            pk, model = session_id, Session
        else:
            pk, model = None, None
        if not pk or not model:
            return None
        with tmp_to_root_org():
            instance = get_object_or_404(model, pk=pk)
            return instance

    def get_target_protocol(self):
        protocol = None
        if isinstance(self.target_instance, Application) and self.target_instance.is_type(Application.APP_TYPE.oracle):
            protocol = self.target_instance.get_target_protocol_for_oracle()
        if not protocol:
            protocol = self.request.GET.get('protocol')
        return protocol


class EndpointViewSet(SmartEndpointViewMixin, JMSBulkModelViewSet):
    filterset_fields = ('name', 'host')
    search_fields = filterset_fields
    serializer_class = serializers.EndpointSerializer
    queryset = Endpoint.objects.all()


class EndpointRuleViewSet(JMSBulkModelViewSet):
    filterset_fields = ('name',)
    search_fields = filterset_fields
    serializer_class = serializers.EndpointRuleSerializer
    queryset = EndpointRule.objects.all()
