# coding: utf-8
import os
import subprocess
import time

from django.conf import settings
from celery import shared_task, subtask

from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _, gettext

from common.utils import get_logger, get_object_or_none, get_log_keep_day
from orgs.utils import tmp_to_root_org, tmp_to_org
from .celery.decorator import (
    register_as_period_task, after_app_shutdown_clean_periodic,
    after_app_ready_start
)
from .celery.utils import (
    create_or_update_celery_periodic_tasks, get_celery_periodic_task,
    disable_celery_periodic_task, delete_celery_periodic_task
)
from .models import Task, CommandExecution, CeleryTask
from .notifications import ServerPerformanceCheckUtil

logger = get_logger(__file__)


def rerun_task():
    pass


@shared_task(queue="ansible")
def run_ansible_task(tid, callback=None, **kwargs):
    """
    :param tid: is the tasks serialized data
    :param callback: callback function name
    :return:
    """
    with tmp_to_root_org():
        task = get_object_or_none(Task, id=tid)
    if not task:
        logger.error("No task found")
        return
    with tmp_to_org(task.org):
        result = task.run()
        if callback is not None:
            subtask(callback).delay(result, task_name=task.name)
        return result


@shared_task(soft_time_limit=60, queue="ansible")
def run_command_execution(cid, **kwargs):
    with tmp_to_root_org():
        execution = get_object_or_none(CommandExecution, id=cid)
    if not execution:
        logger.error("Not found the execution id: {}".format(cid))
        return
    with tmp_to_org(execution.run_as.org):
        try:
            os.environ.update({
                "TERM_ROWS": kwargs.get("rows", ""),
                "TERM_COLS": kwargs.get("cols", ""),
            })
            execution.run()
        except SoftTimeLimitExceeded:
            logger.error("Run time out")


@shared_task
@after_app_shutdown_clean_periodic
@register_as_period_task(interval=3600*24, description=_("Clean task history period"))
def clean_tasks_adhoc_period():
    logger.debug("Start clean task adhoc and run history")
    tasks = Task.objects.all()
    for task in tasks:
        adhoc = task.adhoc.all().order_by('-date_created')[5:]
        for ad in adhoc:
            ad.execution.all().delete()
            ad.delete()


@shared_task
@after_app_shutdown_clean_periodic
@register_as_period_task(interval=3600*24, description=_("Clean celery log period"))
def clean_celery_tasks_period():
    logger.debug("Start clean celery task history")
    expire_days = get_log_keep_day('TASK_LOG_KEEP_DAYS')
    days_ago = timezone.now() - timezone.timedelta(days=expire_days)
    tasks = CeleryTask.objects.filter(date_start__lt=days_ago)
    tasks.delete()
    tasks = CeleryTask.objects.filter(date_start__isnull=True)
    tasks.delete()
    command = "find %s -mtime +%s -name '*.log' -type f -exec rm -f {} \\;" % (
        settings.CELERY_LOG_DIR, expire_days
    )
    subprocess.call(command, shell=True)
    command = "echo > {}".format(os.path.join(settings.LOG_DIR, 'celery.log'))
    subprocess.call(command, shell=True)


@shared_task
@after_app_ready_start
def clean_celery_periodic_tasks():
    """清除celery定时任务"""
    need_cleaned_tasks = [
        'handle_be_interrupted_change_auth_task_periodic',
    ]
    logger.info('Start clean celery periodic tasks: {}'.format(need_cleaned_tasks))
    for task_name in need_cleaned_tasks:
        logger.info('Start clean task: {}'.format(task_name))
        task = get_celery_periodic_task(task_name)
        if task is None:
            logger.info('Task does not exist: {}'.format(task_name))
            continue
        disable_celery_periodic_task(task_name)
        delete_celery_periodic_task(task_name)
        task = get_celery_periodic_task(task_name)
        if task is None:
            logger.info('Clean task success: {}'.format(task_name))
        else:
            logger.info('Clean task failure: {}'.format(task))


@shared_task
@after_app_ready_start
def create_or_update_registered_periodic_tasks():
    from .celery.decorator import get_register_period_tasks
    for task in get_register_period_tasks():
        create_or_update_celery_periodic_tasks(task)


@shared_task
@register_as_period_task(interval=3600)
def check_server_performance_period():
    ServerPerformanceCheckUtil().check_and_publish()


@shared_task(queue="ansible")
def hello(name, callback=None):
    from users.models import User
    import time

    count = User.objects.count()
    print(gettext("Hello") + ': ' + name)
    print("Count: ", count)
    time.sleep(1)
    return gettext("Hello")


@shared_task
# @after_app_shutdown_clean_periodic
# @register_as_period_task(interval=30)
def hello123():
    return None


@shared_task
def hello_callback(result):
    print(result)
    print("Hello callback")


@shared_task
def add(a, b):
    time.sleep(5)
    return a + b


@shared_task
def add_m(x):
    from celery import chain
    a = range(x)
    b = [a[i:i + 10] for i in range(0, len(a), 10)]
    s = list()
    s.append(add.s(b[0], b[1]))
    for i in b[1:]:
        s.append(add.s(i))
    res = chain(*tuple(s))()
    return res

