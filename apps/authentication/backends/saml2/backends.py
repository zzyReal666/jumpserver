# -*- coding: utf-8 -*-
#
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import transaction

from common.utils import get_logger
from authentication.errors import reason_choices, reason_user_invalid
from .signals import (
    saml2_user_authenticated, saml2_user_authentication_failed,
    saml2_create_or_update_user
)

__all__ = ['SAML2Backend']

logger = get_logger(__file__)


class SAML2Backend(ModelBackend):
    def user_can_authenticate(self, user):
        is_valid = getattr(user, 'is_valid', None)
        return is_valid or is_valid is None

    @transaction.atomic
    def get_or_create_from_saml_data(self, request, **saml_user_data):
        log_prompt = "Get or Create user [SAML2Backend]: {}"
        logger.debug(log_prompt.format('start'))

        user, created = get_user_model().objects.get_or_create(
            username=saml_user_data['username'], defaults=saml_user_data
        )
        logger.debug(log_prompt.format("user: {}|created: {}".format(user, created)))

        logger.debug(log_prompt.format("Send signal => saml2 create or update user"))
        saml2_create_or_update_user.send(
            sender=self, request=request, user=user, created=created, attrs=saml_user_data
        )
        return user, created

    def authenticate(self, request, saml_user_data=None, **kwargs):
        log_prompt = "Process authenticate [SAML2AuthCodeBackend]: {}"
        logger.debug(log_prompt.format('Start'))
        if saml_user_data is None:
            logger.error(log_prompt.format('saml_user_data is missing'))
            return None

        logger.debug(log_prompt.format('saml data, {}'.format(saml_user_data)))
        username = saml_user_data.get('username')
        if not username:
            logger.debug(log_prompt.format('username is missing'))
            return None

        user, created = self.get_or_create_from_saml_data(request, **saml_user_data)

        if self.user_can_authenticate(user):
            logger.debug(log_prompt.format('SAML2 user login success'))
            saml2_user_authenticated.send(
                sender=self, request=request, user=user, created=created
            )
            return user
        else:
            logger.debug(log_prompt.format('SAML2 user login failed'))
            saml2_user_authentication_failed.send(
                sender=self, request=request, username=username,
                reason=reason_choices.get(reason_user_invalid)
            )
            return None
