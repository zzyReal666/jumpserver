# -*- coding: utf-8 -*-
#

import os
import json
import jms_storage

from rest_framework.views import Response, APIView
from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import ugettext_lazy as _

from .models import Setting
from .utils import LDAPUtil
from common.permissions import IsOrgAdmin, IsSuperUser
from common.utils import get_logger
from .serializers import MailTestSerializer, LDAPTestSerializer


logger = get_logger(__file__)


class MailTestingAPI(APIView):
    permission_classes = (IsOrgAdmin,)
    serializer_class = MailTestSerializer
    success_message = _("Test mail sent to {}, please check")

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            email_host_user = serializer.validated_data["EMAIL_HOST_USER"]
            for k, v in serializer.validated_data.items():
                if k.startswith('EMAIL'):
                    setattr(settings, k, v)
            try:
                subject = "Test"
                message = "Test smtp setting"
                send_mail(subject, message,  email_host_user, [email_host_user])
            except Exception as e:
                return Response({"error": str(e)}, status=401)

            return Response({"msg": self.success_message.format(email_host_user)})
        else:
            return Response({"error": str(serializer.errors)}, status=401)


class LDAPTestingAPI(APIView):
    permission_classes = (IsOrgAdmin,)
    serializer_class = LDAPTestSerializer
    success_message = _("Test ldap success")

    @staticmethod
    def get_ldap_util(serializer):
        host = serializer.validated_data["AUTH_LDAP_SERVER_URI"]
        bind_dn = serializer.validated_data["AUTH_LDAP_BIND_DN"]
        password = serializer.validated_data["AUTH_LDAP_BIND_PASSWORD"]
        use_ssl = serializer.validated_data.get("AUTH_LDAP_START_TLS", False)
        search_ougroup = serializer.validated_data["AUTH_LDAP_SEARCH_OU"]
        search_filter = serializer.validated_data["AUTH_LDAP_SEARCH_FILTER"]
        attr_map = serializer.validated_data["AUTH_LDAP_USER_ATTR_MAP"]
        try:
            attr_map = json.loads(attr_map)
        except json.JSONDecodeError:
            return Response({"error": "AUTH_LDAP_USER_ATTR_MAP not valid"}, status=401)

        util = LDAPUtil(
            use_settings_config=False, server_uri=host, bind_dn=bind_dn,
            password=password, use_ssl=use_ssl,
            search_ougroup=search_ougroup, search_filter=search_filter,
            attr_map=attr_map
        )
        return util

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({"error": str(serializer.errors)}, status=401)

        util = self.get_ldap_util(serializer)

        try:
            users = util.get_search_user_items()
        except Exception as e:
            return Response({"error": str(e)}, status=401)

        if len(users) > 0:
            return Response({"msg": _("Match {} s users").format(len(users))})
        else:
            return Response({"error": "Have user but attr mapping error"}, status=401)


class LDAPUserListApi(APIView):
    permission_classes = (IsOrgAdmin,)

    def get(self, request):
        util = LDAPUtil()
        try:
            users = util.get_search_user_items()
        except Exception as e:
            users = []
            logger.error(e, exc_info=True)
        else:
            users = sorted(users, key=lambda u: (u['existing'], u['username']))
        return Response(users)


class LDAPUserSyncAPI(APIView):
    permission_classes = (IsOrgAdmin,)

    def post(self, request):
        user_names = request.data.get('user_names', '')

        util = LDAPUtil()
        try:
            result = util.sync_users(username_set=user_names)
        except Exception as e:
            logger.error(e, exc_info=True)
            return Response({'error': str(e)}, status=401)
        else:
            msg = _("succeed: {} failed: {} total: {}").format(
                result['succeed'], result['failed'], result['total']
            )
            return Response({'msg': msg})


class ReplayStorageCreateAPI(APIView):
    permission_classes = (IsSuperUser,)

    def post(self, request):
        storage_data = request.data

        if storage_data.get('TYPE') == 'ceph':
            port = storage_data.get('PORT')
            if port.isdigit():
                storage_data['PORT'] = int(storage_data.get('PORT'))

        storage_name = storage_data.pop('NAME')
        data = {storage_name: storage_data}

        if not self.is_valid(storage_data):
            return Response({
                "error": _("Error: Account invalid (Please make sure the "
                           "information such as Access key or Secret key is correct)")},
                status=401
            )

        Setting.save_storage('TERMINAL_REPLAY_STORAGE', data)
        return Response({"msg": _('Create succeed')}, status=200)

    @staticmethod
    def is_valid(storage_data):
        if storage_data.get('TYPE') == 'server':
            return True
        storage = jms_storage.get_object_storage(storage_data)
        target = 'tests.py'
        src = os.path.join(settings.BASE_DIR, 'common', target)
        return storage.is_valid(src, target)


class ReplayStorageDeleteAPI(APIView):
    permission_classes = (IsSuperUser,)

    def post(self, request):
        storage_name = str(request.data.get('name'))
        Setting.delete_storage('TERMINAL_REPLAY_STORAGE', storage_name)
        return Response({"msg": _('Delete succeed')}, status=200)


class CommandStorageCreateAPI(APIView):
    permission_classes = (IsSuperUser,)

    def post(self, request):
        storage_data = request.data
        storage_name = storage_data.pop('NAME')
        data = {storage_name: storage_data}
        if not self.is_valid(storage_data):
            return Response(
                {"error": _("Error: Account invalid (Please make sure the "
                            "information such as Access key or Secret key is correct)")},
                status=401
            )

        Setting.save_storage('TERMINAL_COMMAND_STORAGE', data)
        return Response({"msg": _('Create succeed')}, status=200)

    @staticmethod
    def is_valid(storage_data):
        if storage_data.get('TYPE') == 'server':
            return True
        try:
            storage = jms_storage.get_log_storage(storage_data)
        except Exception:
            return False

        return storage.ping()


class CommandStorageDeleteAPI(APIView):
    permission_classes = (IsSuperUser,)

    def post(self, request):
        storage_name = str(request.data.get('name'))
        Setting.delete_storage('TERMINAL_COMMAND_STORAGE', storage_name)
        return Response({"msg": _('Delete succeed')}, status=200)


class DjangoSettingsAPI(APIView):
    def get(self, request):
        if not settings.DEBUG:
            return Response("Not in debug mode")

        data = {}
        for i in [settings, getattr(settings, '_wrapped')]:
            if not i:
                continue
            for k, v in i.__dict__.items():
                if k and k.isupper():
                    try:
                        json.dumps(v)
                        data[k] = v
                    except (json.JSONDecodeError, TypeError):
                        data[k] = str(v)
        return Response(data)



