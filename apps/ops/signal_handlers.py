import ast

from celery import signals
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import pre_save
from django.db.utils import ProgrammingError
from django.dispatch import receiver
from django.utils import translation, timezone
from django.utils.translation import gettext as _

from common.db.utils import close_old_connections, get_logger
from .celery import app
from .models import CeleryTaskExecution, CeleryTask, Job

logger = get_logger(__name__)

TASK_LANG_CACHE_KEY = 'TASK_LANG_{}'
TASK_LANG_CACHE_TTL = 1800


@receiver(pre_save, sender=Job)
def on_account_pre_create(sender, instance, **kwargs):
    # 升级版本号
    instance.version += 1


@receiver(signals.worker_ready)
def sync_registered_tasks(*args, **kwargs):
    synced = cache.get('synced_registered_tasks', False)
    if synced:
        return
    cache.set('synced_registered_tasks', True, 60)
    with transaction.atomic():
        try:
            db_tasks = CeleryTask.objects.all()
            celery_task_names = [key for key in app.tasks]
            db_task_names = db_tasks.values_list('name', flat=True)

            db_tasks.exclude(name__in=celery_task_names).delete()
            not_in_db_tasks = set(celery_task_names) - set(db_task_names)
            tasks_to_create = [CeleryTask(name=name) for name in not_in_db_tasks]
            CeleryTask.objects.bulk_create(tasks_to_create)
        except ProgrammingError:
            pass


@signals.before_task_publish.connect
def before_task_publish(headers=None, **kwargs):
    task_id = headers.get('id')
    current_lang = translation.get_language()
    key = TASK_LANG_CACHE_KEY.format(task_id)
    cache.set(key, current_lang, 1800)


@signals.task_prerun.connect
def on_celery_task_pre_run(task_id='', **kwargs):
    # 更新状态
    CeleryTaskExecution.objects.filter(id=task_id) \
        .update(state='RUNNING', date_start=timezone.now())
    # 关闭之前的数据库连接
    close_old_connections()

    # 保存 Lang context
    key = TASK_LANG_CACHE_KEY.format(task_id)
    task_lang = cache.get(key)
    if task_lang:
        translation.activate(task_lang)


@signals.task_postrun.connect
def on_celery_task_post_run(task_id='', state='', **kwargs):
    close_old_connections()
    print(_("Task") + ": {} {}".format(task_id, state))

    CeleryTaskExecution.objects.filter(id=task_id).update(
        state=state, date_finished=timezone.now(), is_finished=True
    )


@signals.after_task_publish.connect
def task_sent_handler(headers=None, body=None, **kwargs):
    info = headers if 'task' in headers else body
    task = info.get('task')
    i = info.get('id')
    if not i or not task:
        logger.error("Not found task id or name: {}".format(info))
        return

    args = info.get('argsrepr', '()')
    kwargs = info.get('kwargsrepr', '{}')
    try:
        args = list(ast.literal_eval(args))
        kwargs = ast.literal_eval(kwargs)
    except (ValueError, SyntaxError):
        args = []
        kwargs = {}

    data = {
        'id': i,
        'name': task,
        'state': 'PENDING',
        'is_finished': False,
        'args': args,
        'kwargs': kwargs
    }
    CeleryTaskExecution.objects.create(**data)
    CeleryTask.objects.filter(name=task).update(date_last_publish=timezone.now())
