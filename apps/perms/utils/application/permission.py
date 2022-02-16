import time
from functools import reduce

from django.db.models import Q

from common.utils import get_logger
from perms.models import ApplicationPermission, Action

logger = get_logger(__file__)


def get_user_all_app_perm_ids(user) -> set:
    app_perm_ids = set()
    user_perm_id = ApplicationPermission.users.through.objects \
        .filter(user_id=user.id) \
        .values_list('applicationpermission_id', flat=True) \
        .distinct()
    app_perm_ids.update(user_perm_id)

    group_ids = user.groups.through.objects \
        .filter(user_id=user.id) \
        .values_list('usergroup_id', flat=True) \
        .distinct()
    group_ids = list(group_ids)
    groups_perm_id = ApplicationPermission.user_groups.through.objects \
        .filter(usergroup_id__in=group_ids) \
        .values_list('applicationpermission_id', flat=True) \
        .distinct()
    app_perm_ids.update(groups_perm_id)

    app_perm_ids = ApplicationPermission.objects.filter(
        id__in=app_perm_ids).valid().values_list('id', flat=True)
    app_perm_ids = set(app_perm_ids)
    return app_perm_ids


def validate_permission(user, application, system_user, action='connect'):
    app_perm_ids = get_user_all_app_perm_ids(user)
    app_perm_ids = ApplicationPermission.applications.through.objects.filter(
        applicationpermission_id__in=app_perm_ids,
        application_id=application.id
    ).values_list('applicationpermission_id', flat=True)
    app_perm_ids = set(app_perm_ids)
    app_perm_ids = ApplicationPermission.system_users.through.objects.filter(
        applicationpermission_id__in=app_perm_ids,
        systemuser_id=system_user.id
    ).values_list('applicationpermission_id', flat=True)
    app_perm_ids = set(app_perm_ids)
    app_perms = ApplicationPermission.objects.filter(
        id__in=app_perm_ids
    ).order_by('-date_expired')

    if app_perms:
        actions = set()
        actions_values = app_perms.values_list('actions', flat=True)
        for value in actions_values:
            _actions = Action.value_to_choices(value)
            actions.update(_actions)
        actions = list(actions)
        app_perm: ApplicationPermission = app_perms.first()
        expire_at = app_perm.date_expired.timestamp()
    else:
        actions = []
        expire_at = time.time()

    # TODO: 组件改造API完成后统一通过actions判断has_perm
    has_perm = action in actions
    return has_perm, actions, expire_at


def get_application_system_user_ids(user, application):
    queryset = ApplicationPermission.objects.valid()\
        .filter(
            Q(users=user) | Q(user_groups__users=user),
            Q(applications=application)
        ).values_list('system_users', flat=True)
    return queryset


def has_application_system_permission(user, application, system_user):
    system_user_ids = get_application_system_user_ids(user, application)
    return system_user.id in system_user_ids


def get_application_actions(user, application, system_user):
    perm_ids = get_user_all_app_perm_ids(user)
    actions = ApplicationPermission.objects.filter(
        applications=application, system_users=system_user,
        id__in=list(perm_ids)
    ).values_list('actions', flat=True)

    actions = reduce(lambda x, y: x | y, actions, 0)
    return actions
