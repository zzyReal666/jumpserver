#  coding: utf-8
#

import uuid
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.db.models import Q
from django.utils import timezone
from orgs.mixins.models import OrgModelMixin

from common.db.models import UnionQuerySet, BitOperationChoice
from common.utils import date_expired_default, lazyproperty
from orgs.mixins.models import OrgManager

__all__ = [
    'BasePermission', 'BasePermissionQuerySet', 'Action'
]


class BasePermissionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def valid(self):
        return self.active().filter(date_start__lt=timezone.now()) \
            .filter(date_expired__gt=timezone.now())

    def inactive(self):
        return self.filter(is_active=False)

    def invalid(self):
        now = timezone.now()
        q = (Q(is_active=False) | Q(date_start__gt=now) | Q(date_expired__lt=now))
        return self.filter(q)


class BasePermissionManager(OrgManager):
    def valid(self):
        return self.get_queryset().valid()


class Action(BitOperationChoice):
    ALL = 0xff

    CONNECT = 0b1
    UPLOAD = 0b1 << 1
    DOWNLOAD = 0b1 << 2
    CLIPBOARD_COPY = 0b1 << 3
    CLIPBOARD_PASTE = 0b1 << 4
    UPDOWNLOAD = UPLOAD | DOWNLOAD
    CLIPBOARD_COPY_PASTE = CLIPBOARD_COPY | CLIPBOARD_PASTE

    DB_CHOICES = (
        (ALL, _('All')),
        (CONNECT, _('Connect')),
        (UPLOAD, _('Upload file')),
        (DOWNLOAD, _('Download file')),
        (UPDOWNLOAD, _("Upload download")),
        (CLIPBOARD_COPY, _('Clipboard copy')),
        (CLIPBOARD_PASTE, _('Clipboard paste')),
        (CLIPBOARD_COPY_PASTE, _('Clipboard copy paste'))
    )

    NAME_MAP = {
        ALL: "all",
        CONNECT: "connect",
        UPLOAD: "upload_file",
        DOWNLOAD: "download_file",
        UPDOWNLOAD: "updownload",
        CLIPBOARD_COPY: 'clipboard_copy',
        CLIPBOARD_PASTE: 'clipboard_paste',
        CLIPBOARD_COPY_PASTE: 'clipboard_copy_paste'
    }

    NAME_MAP_REVERSE = {v: k for k, v in NAME_MAP.items()}
    CHOICES = []
    for i, j in DB_CHOICES:
        CHOICES.append((NAME_MAP[i], j))


class BasePermission(OrgModelMixin):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=128, verbose_name=_('Name'))
    users = models.ManyToManyField('users.User', blank=True, verbose_name=_("User"), related_name='%(class)ss')
    user_groups = models.ManyToManyField(
        'users.UserGroup', blank=True, verbose_name=_("User group"), related_name='%(class)ss')
    actions = models.IntegerField(choices=Action.DB_CHOICES, default=Action.ALL, verbose_name=_("Actions"))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    date_start = models.DateTimeField(default=timezone.now, db_index=True, verbose_name=_("Date start"))
    date_expired = models.DateTimeField(default=date_expired_default, db_index=True, verbose_name=_('Date expired'))
    created_by = models.CharField(max_length=128, blank=True, verbose_name=_('Created by'))
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_('Date created'))
    comment = models.TextField(verbose_name=_('Comment'), blank=True)
    from_ticket = models.BooleanField(default=False, verbose_name=_('From ticket'))

    objects = BasePermissionManager.from_queryset(BasePermissionQuerySet)()

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    @property
    def id_str(self):
        return str(self.id)

    @property
    def is_expired(self):
        if self.date_expired > timezone.now() > self.date_start:
            return False
        return True

    @property
    def is_valid(self):
        if not self.is_expired and self.is_active:
            return True
        return False

    @property
    def all_users(self):
        from users.models import User

        users_query = self._meta.get_field('users').related_query_name()
        user_groups_query = self._meta.get_field('user_groups').related_query_name()

        users_q = Q(**{
            f'{users_query}': self
        })

        user_groups_q = Q(**{
            f'groups__{user_groups_query}': self
        })

        return User.objects.filter(users_q | user_groups_q).distinct()

    def get_all_users(self):
        from users.models import User
        user_ids = self.users.all().values_list('id', flat=True)
        group_ids = self.user_groups.all().values_list('id', flat=True)

        user_ids = list(user_ids)
        group_ids = list(group_ids)

        qs1 = User.objects.filter(id__in=user_ids).distinct()
        qs2 = User.objects.filter(groups__id__in=group_ids).distinct()

        qs = UnionQuerySet(qs1, qs2)
        return qs

    @lazyproperty
    def users_amount(self):
        return self.users.count()

    @lazyproperty
    def user_groups_amount(self):
        return self.user_groups.count()
