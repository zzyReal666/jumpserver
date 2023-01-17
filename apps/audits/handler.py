from datetime import datetime

from django.db import transaction
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _

from users.models import User
from common.utils import get_request_ip, get_logger
from common.utils.timezone import as_current_tz
from common.utils.encode import Singleton
from common.local import encrypted_field_set
from settings.serializers import SettingsSerializer
from jumpserver.utils import current_request
from orgs.utils import get_current_org_id

from .backends import get_operate_log_storage
from .const import ActionChoices


logger = get_logger(__name__)


class OperatorLogHandler(metaclass=Singleton):
    CACHE_KEY = 'OPERATOR_LOG_CACHE_KEY'

    def __init__(self):
        self.log_client = self.get_storage_client()

    @staticmethod
    def get_storage_client():
        client = get_operate_log_storage()
        return client

    @staticmethod
    def _consistent_type_to_str(value1, value2):
        if isinstance(value1, datetime):
            value1 = as_current_tz(value1).strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(value2, datetime):
            value2 = as_current_tz(value2).strftime('%Y-%m-%d %H:%M:%S')
        return value1, value2

    def _look_for_two_dict_change(self, left_dict, right_dict):
        # 以右边的字典为基础
        before, after = {}, {}
        for key, value in right_dict.items():
            pre_value = left_dict.get(key, '')
            pre_value, value = self._consistent_type_to_str(pre_value, value)
            if sorted(str(value)) == sorted(str(pre_value)):
                continue
            if pre_value:
                before[key] = pre_value
            if value:
                after[key] = value
        return before, after

    def cache_instance_before_data(self, instance_dict):
        instance_id = instance_dict.get('id')
        if instance_id is None:
            return

        key = '%s_%s' % (self.CACHE_KEY, instance_id)
        cache.set(key, instance_dict, 3 * 60)

    def get_instance_dict_from_cache(self, instance_id):
        if instance_id is None:
            return None, None

        key = '%s_%s' % (self.CACHE_KEY, instance_id)
        cache_instance = cache.get(key, {})
        log_id = cache_instance.get('operate_log_id')
        return log_id, cache_instance

    def get_instance_current_with_cache_diff(self, current_instance):
        log_id, before, after = None, None, None
        instance_id = current_instance.get('id')
        if instance_id is None:
            return log_id, before, after

        log_id, cache_instance = self.get_instance_dict_from_cache(instance_id)
        if not cache_instance:
            return log_id, before, after

        before, after = self._look_for_two_dict_change(
            cache_instance, current_instance
        )
        return log_id, before, after

    @staticmethod
    def get_resource_display_from_setting(resource):
        resource_display = None
        setting_serializer = SettingsSerializer()
        label = setting_serializer.get_field_label(resource)
        if label is not None:
            resource_display = label
        return resource_display

    def get_resource_display(self, resource):
        resource_display = str(resource)
        return_value = self.get_resource_display_from_setting(resource_display)
        if return_value is not None:
            resource_display = return_value
        return resource_display

    @staticmethod
    def serialized_value(value: (list, tuple)):
        if len(value) == 0:
            return ''
        if isinstance(value[0], str):
            return ','.join(value)
        return ','.join([i['value'] for i in value if i.get('value')])

    def __data_processing(self, dict_item, loop=True):
        encrypt_value = '******'
        for key, value in dict_item.items():
            if isinstance(value, bool):
                value = _('Yes') if value else _('No')
            elif isinstance(value, (list, tuple)):
                value = self.serialized_value(value)
            elif isinstance(value, dict) and loop:
                self.__data_processing(value, loop=False)
            if key in encrypted_field_set:
                value = encrypt_value
            dict_item[key] = value
        return dict_item

    def data_processing(self, before, after):
        if before:
            before = self.__data_processing(before)
        if after:
            after = self.__data_processing(after)
        return before, after

    @staticmethod
    def _get_Session_params(resource, **kwargs):
        # 更新会话的日志不在Activity中体现，
        # 否则会话结束，录像文件结束操作的会话记录都会体现出来
        params = {}
        action = kwargs.get('data', {}).get('action', 'create')
        detail = _(
            '{} used account[{}], login method[{}] login the asset.'
        ).format(
            resource.user, resource.account, resource.login_from_display
        )
        if action == ActionChoices.create:
            params = {
                'action': ActionChoices.connect,
                'resource_id': str(resource.asset_id),
                'user': resource.user, 'detail': detail
            }
        return params

    @staticmethod
    def _get_ChangeSecretRecord_params(resource, **kwargs):
        detail = _(
            'User {} has executed change auth plan for this account.({})'
        ).format(
            resource.created_by, _(resource.status.title())
        )
        return {
            'action': ActionChoices.change_auth, 'detail': detail,
            'resource_id': str(resource.account_id),
        }

    @staticmethod
    def _get_UserLoginLog_params(resource, **kwargs):
        username = resource.username
        login_status = _('Success') if resource.status else _('Failed')
        detail = _('User {} login into this service.[{}]').format(
            resource.username, login_status
        )
        user_id = User.objects.filter(username=username).\
            values_list('id', flat=True)[0]
        return {
            'action': ActionChoices.login, 'detail': detail,
            'resource_id': str(user_id),
        }

    def _activity_handle(self, data, object_name, resource):
        param_func = getattr(self, '_get_%s_params' % object_name, None)
        if param_func is not None:
            params = param_func(resource, data=data)
            data.update(params)
        return data

    def create_or_update_operate_log(
            self, action, resource_type, resource=None,
            force=False, log_id=None, before=None, after=None,
            object_name=None
    ):
        user = current_request.user if current_request else None
        if not user or not user.is_authenticated:
            return

        remote_addr = get_request_ip(current_request)
        resource_display = self.get_resource_display(resource)
        before, after = self.data_processing(before, after)
        if not force and not any([before, after]):
            # 前后都没变化，没必要生成日志，除非手动强制保存
            return

        data = {
            'id': log_id, "user": str(user), 'action': action,
            'resource_type': str(resource_type), 'resource': resource_display,
            'remote_addr': remote_addr, 'before': before, 'after': after,
            'org_id': get_current_org_id(), 'resource_id': str(resource.id)
        }
        data = self._activity_handle(data, object_name, resource=resource)
        with transaction.atomic():
            if self.log_client.ping(timeout=1):
                client = self.log_client
            else:
                logger.info('Switch default operate log storage save.')
                client = get_operate_log_storage(default=True)

            try:
                client.save(**data)
            except Exception as e:
                error_msg = 'An error occurred saving OperateLog.' \
                            'Error: %s, Data: %s' % (e, data)
                logger.error(error_msg)


op_handler = OperatorLogHandler()
# 理论上操作日志的唯一入口
create_or_update_operate_log = op_handler.create_or_update_operate_log
cache_instance_before_data = op_handler.cache_instance_before_data
get_instance_current_with_cache_diff = op_handler.get_instance_current_with_cache_diff
get_instance_dict_from_cache = op_handler.get_instance_dict_from_cache
