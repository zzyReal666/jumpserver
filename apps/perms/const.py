# -*- coding: utf-8 -*-
#

from django.utils.translation import ugettext_lazy as _

__all__ = [
    'PERMS_ACTION_NAME_ALL', 'PERMS_ACTION_NAME_CONNECT',
    'PERMS_ACTION_NAME_DOWNLOAD_FILE', 'PERMS_ACTION_NAME_UPLOAD_FILE',
    'PERMS_ACTION_NAME_CHOICES'
]

PERMS_ACTION_NAME_ALL = 'all'
PERMS_ACTION_NAME_CONNECT = 'connect'
PERMS_ACTION_NAME_UPLOAD_FILE = 'upload_file'
PERMS_ACTION_NAME_DOWNLOAD_FILE = 'download_file'

PERMS_ACTION_NAME_CHOICES = (
    (PERMS_ACTION_NAME_ALL, _('All')),
    (PERMS_ACTION_NAME_CONNECT, _('Connect')),
    (PERMS_ACTION_NAME_UPLOAD_FILE, _('Upload file')),
    (PERMS_ACTION_NAME_DOWNLOAD_FILE, _('Download file')),
)
