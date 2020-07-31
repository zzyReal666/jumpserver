# -*- coding: utf-8 -*-
#
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException
from rest_framework import status


class JMSException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class JMSObjectDoesNotExist(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = 'object_does_not_exist'
    default_detail = _('%s object does not exist.')

    def __init__(self, detail=None, code=None, object_name=None):
        if detail is None and object_name:
            detail = self.default_detail % object_name
        super(JMSObjectDoesNotExist, self).__init__(detail=detail, code=code)
