import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models


class MenuPermission(models.Model):
    """ 附加权限位类，用来定义无资源类的权限，不做实体资源 """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    class Meta:
        default_permissions = []
        verbose_name = _('Menu permission')
        permissions = [
            ('view_resourcestatistics', _('Can view resource statistics')),
            ('view_adminview', _('Can view console view')),
            ('view_auditview', _('Can view audit view')),
            ('view_userview', _('Can view workspace view')),
            ('view_webterminal', _('Can view web terminal')),
            ('view_filemanager', _('Can view file manager')),
        ]
