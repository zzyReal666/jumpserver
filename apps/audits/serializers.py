# -*- coding: utf-8 -*-
#
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from common.serializers.fields import LabeledChoiceField
from common.utils.timezone import as_current_tz
from ops.models.job import JobAuditLog
from ops.serializers.job import JobExecutionSerializer
from terminal.models import Session
from . import models
from .const import (
    ActionChoices, OperateChoices,
    MFAChoices, LoginStatusChoices,
    LoginTypeChoices,
)


class JobAuditLogSerializer(JobExecutionSerializer):
    class Meta:
        model = JobAuditLog
        read_only_fields = [
            "id", "material", "time_cost", 'date_start',
            'date_finished', 'date_created',
            'is_finished', 'is_success', 'created_by',
            'task_id'
        ]
        fields = read_only_fields + []


class FTPLogSerializer(serializers.ModelSerializer):
    operate = LabeledChoiceField(choices=OperateChoices.choices, label=_("Operate"))

    class Meta:
        model = models.FTPLog
        fields_mini = ["id"]
        fields_small = fields_mini + [
            "user", "remote_addr", "asset", "account",
            "org_id", "operate", "filename", "is_success",
            "date_start",
        ]
        fields = fields_small


class UserLoginLogSerializer(serializers.ModelSerializer):
    mfa = LabeledChoiceField(choices=MFAChoices.choices, label=_("MFA"))
    type = LabeledChoiceField(choices=LoginTypeChoices.choices, label=_("Type"))
    status = LabeledChoiceField(choices=LoginStatusChoices.choices, label=_("Status"))

    class Meta:
        model = models.UserLoginLog
        fields_mini = ["id"]
        fields_small = fields_mini + [
            "username", "type", "ip",
            "city", "user_agent", "mfa",
            "reason", "reason_display",
            "backend", "backend_display",
            "status", "datetime",
        ]
        fields = fields_small
        extra_kwargs = {
            "user_agent": {"label": _("User agent")},
            "reason_display": {"label": _("Reason display")},
            "backend_display": {"label": _("Authentication backend")},
        }


class OperateLogActionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OperateLog
        fields = ('before', 'after')


class OperateLogSerializer(serializers.ModelSerializer):
    action = LabeledChoiceField(choices=ActionChoices.choices, label=_("Action"))

    class Meta:
        model = models.OperateLog
        fields_mini = ["id"]
        fields_small = fields_mini + [
            "user", "action", "resource_type",
            "resource_type_display", "resource",
            "remote_addr", "datetime", "org_id",
        ]
        fields = fields_small
        extra_kwargs = {"resource_type_display": {"label": _("Resource Type")}}


class PasswordChangeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PasswordChangeLog
        fields = ("id", "user", "change_by", "remote_addr", "datetime")


class SessionAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = "__all__"


class ActivitiesOperatorLogSerializer(serializers.Serializer):
    timestamp = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    @staticmethod
    def get_timestamp(obj):
        return as_current_tz(obj.datetime).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def get_content(obj):
        action = obj.action.replace('_', ' ').capitalize()
        ctn = _('User {} {} this resource.').format(obj.user, _(action))
        return ctn
