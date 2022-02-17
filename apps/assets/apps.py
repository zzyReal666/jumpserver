from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _

from django.apps import AppConfig


class AssetsConfig(AppConfig):
    name = 'assets'
    verbose_name = _('Assets')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def ready(self):
        super().ready()
        from . import signals_handler
