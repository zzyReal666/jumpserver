import time

from django.core.cache import cache
from django.utils import timezone
from django.utils.timesince import timesince
from django.db.models import Count, Max
from django.http.response import JsonResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from collections import Counter
from rest_framework.response import Response

from users.models import User
from assets.models import Asset
from terminal.models import Session
from terminal.utils import ComponentsPrometheusMetricsUtil
from orgs.utils import current_org
from common.utils import lazyproperty
from orgs.caches import OrgResourceStatisticsCache


__all__ = ['IndexApi']


class DatesLoginMetricMixin:
    @lazyproperty
    def days(self):
        query_params = self.request.query_params
        if query_params.get('monthly'):
            return 30
        return 7

    @lazyproperty
    def sessions_queryset(self):
        days = timezone.now() - timezone.timedelta(days=self.days)
        sessions_queryset = Session.objects.filter(date_start__gt=days)
        return sessions_queryset

    @lazyproperty
    def session_dates_list(self):
        now = timezone.now()
        dates = [(now - timezone.timedelta(days=i)).date() for i in range(self.days)]
        dates.reverse()
        # dates = self.sessions_queryset.dates('date_start', 'day')
        return dates

    def get_dates_metrics_date(self):
        dates_metrics_date = [d.strftime('%m-%d') for d in self.session_dates_list] or ['0']
        return dates_metrics_date

    @staticmethod
    def get_cache_key(date, tp):
        date_str = date.strftime("%Y%m%d")
        key = "SESSION_DATE_{}_{}_{}".format(current_org.id, tp, date_str)
        return key

    def __get_data_from_cache(self, date, tp):
        if date == timezone.now().date():
            return None
        cache_key = self.get_cache_key(date, tp)
        count = cache.get(cache_key)
        return count

    def __set_data_to_cache(self, date, tp, count):
        cache_key = self.get_cache_key(date, tp)
        cache.set(cache_key, count, 3600*24*7)

    @staticmethod
    def get_date_start_2_end(d):
        time_min = timezone.datetime.min.time()
        time_max = timezone.datetime.max.time()
        tz = timezone.get_current_timezone()
        ds = timezone.datetime.combine(d, time_min).replace(tzinfo=tz)
        de = timezone.datetime.combine(d, time_max).replace(tzinfo=tz)
        return ds, de

    def get_date_login_count(self, date):
        tp = "LOGIN"
        count = self.__get_data_from_cache(date, tp)
        if count is not None:
            return count
        ds, de = self.get_date_start_2_end(date)
        count = Session.objects.filter(date_start__range=(ds, de)).count()
        self.__set_data_to_cache(date, tp, count)
        return count

    def get_dates_metrics_total_count_login(self):
        data = []
        for d in self.session_dates_list:
            count = self.get_date_login_count(d)
            data.append(count)
        if len(data) == 0:
            data = [0]
        return data

    def get_date_user_count(self, date):
        tp = "USER"
        count = self.__get_data_from_cache(date, tp)
        if count is not None:
            return count
        ds, de = self.get_date_start_2_end(date)
        count = len(set(Session.objects.filter(date_start__range=(ds, de)).values_list('user_id', flat=True)))
        self.__set_data_to_cache(date, tp, count)
        return count

    def get_dates_metrics_total_count_active_users(self):
        data = []
        for d in self.session_dates_list:
            count = self.get_date_user_count(d)
            data.append(count)
        return data

    def get_date_asset_count(self, date):
        tp = "ASSET"
        count = self.__get_data_from_cache(date, tp)
        if count is not None:
            return count
        ds, de = self.get_date_start_2_end(date)
        count = len(set(Session.objects.filter(date_start__range=(ds, de)).values_list('asset', flat=True)))
        self.__set_data_to_cache(date, tp, count)
        return count

    def get_dates_metrics_total_count_active_assets(self):
        data = []
        for d in self.session_dates_list:
            count = self.get_date_asset_count(d)
            data.append(count)
        return data

    @lazyproperty
    def dates_total_count_active_users(self):
        count = len(set(self.sessions_queryset.values_list('user_id', flat=True)))
        return count

    @lazyproperty
    def dates_total_count_inactive_users(self):
        total = current_org.get_members().count()
        active = self.dates_total_count_active_users
        count = total - active
        if count < 0:
            count = 0
        return count

    @lazyproperty
    def dates_total_count_disabled_users(self):
        return current_org.get_members().filter(is_active=False).count()

    @lazyproperty
    def dates_total_count_active_assets(self):
        return len(set(self.sessions_queryset.values_list('asset', flat=True)))

    @lazyproperty
    def dates_total_count_inactive_assets(self):
        total = Asset.objects.all().count()
        active = self.dates_total_count_active_assets
        count = total - active
        if count < 0:
            count = 0
        return count

    @lazyproperty
    def dates_total_count_disabled_assets(self):
        return Asset.objects.filter(is_active=False).count()

    # 以下是从week中而来
    def get_dates_login_times_top5_users(self):
        users = self.sessions_queryset.values_list('user_id', flat=True)
        users = [
            {'user': user, 'total': total}
            for user, total in Counter(users).most_common(5)
        ]
        return users

    def get_dates_total_count_login_users(self):
        return len(set(self.sessions_queryset.values_list('user_id', flat=True)))

    def get_dates_total_count_login_times(self):
        return self.sessions_queryset.count()

    def get_dates_login_times_top10_assets(self):
        assets = self.sessions_queryset.values("asset") \
                     .annotate(total=Count("asset")) \
                     .annotate(last=Max("date_start")).order_by("-total")[:10]
        for asset in assets:
            asset['last'] = str(asset['last'])
        return list(assets)

    def get_dates_login_times_top10_users(self):
        users = self.sessions_queryset.values("user_id") \
                    .annotate(total=Count("user_id")) \
                    .annotate(user=Max('user')) \
                    .annotate(last=Max("date_start")).order_by("-total")[:10]
        for user in users:
            user['last'] = str(user['last'])
        return list(users)

    def get_dates_login_record_top10_sessions(self):
        sessions = self.sessions_queryset.order_by('-date_start')[:10]
        for session in sessions:
            session.avatar_url = User.get_avatar_url("")
        sessions = [
            {
                'user': session.user,
                'asset': session.asset,
                'is_finished': session.is_finished,
                'date_start': str(session.date_start),
                'timesince': timesince(session.date_start)
            }
            for session in sessions
        ]
        return sessions


class IndexApi(DatesLoginMetricMixin, APIView):
    http_method_names = ['get']
    rbac_perms = {
        'GET': 'view_auditview'
    }

    def get(self, request, *args, **kwargs):
        data = {}

        query_params = self.request.query_params

        caches = OrgResourceStatisticsCache(current_org)

        _all = query_params.get('all')

        if _all or query_params.get('total_count') or query_params.get('total_count_users'):
            data.update({
                'total_count_users': caches.users_amount,
            })

        if _all or query_params.get('total_count') or query_params.get('total_count_assets'):
            data.update({
                'total_count_assets': caches.assets_amount,
            })

        if _all or query_params.get('total_count') or query_params.get('total_count_online_users'):
            data.update({
                'total_count_online_users': caches.total_count_online_users,
            })

        if _all or query_params.get('total_count') or query_params.get('total_count_online_sessions'):
            data.update({
                'total_count_online_sessions': caches.total_count_online_sessions,
            })

        if _all or query_params.get('dates_metrics'):
            data.update({
                'dates_metrics_date': self.get_dates_metrics_date(),
                'dates_metrics_total_count_login': self.get_dates_metrics_total_count_login(),
                'dates_metrics_total_count_active_users': self.get_dates_metrics_total_count_active_users(),
                'dates_metrics_total_count_active_assets': self.get_dates_metrics_total_count_active_assets(),
            })

        if _all or query_params.get('dates_total_count_users'):
            data.update({
                'dates_total_count_active_users': self.dates_total_count_active_users,
                'dates_total_count_inactive_users': self.dates_total_count_inactive_users,
                'dates_total_count_disabled_users': self.dates_total_count_disabled_users,
            })

        if _all or query_params.get('dates_total_count_assets'):
            data.update({
                'dates_total_count_active_assets': self.dates_total_count_active_assets,
                'dates_total_count_inactive_assets': self.dates_total_count_inactive_assets,
                'dates_total_count_disabled_assets': self.dates_total_count_disabled_assets,
            })

        if _all or query_params.get('dates_total_count'):
            data.update({
                'dates_total_count_login_users': self.get_dates_total_count_login_users(),
                'dates_total_count_login_times': self.get_dates_total_count_login_times(),
            })

        if _all or query_params.get('dates_login_times_top5_users'):
            data.update({
                'dates_login_times_top5_users': self.get_dates_login_times_top5_users(),
            })

        if _all or query_params.get('dates_login_times_top10_assets'):
            data.update({
                'dates_login_times_top10_assets': self.get_dates_login_times_top10_assets(),
            })

        if _all or query_params.get('dates_login_times_top10_users'):
            data.update({
                'dates_login_times_top10_users': self.get_dates_login_times_top10_users(),
            })

        if _all or query_params.get('dates_login_record_top10_sessions'):
            data.update({
                'dates_login_record_top10_sessions': self.get_dates_login_record_top10_sessions()
            })

        return JsonResponse(data, status=200)


class HealthApiMixin(APIView):
    pass

    # 先去掉 Health Api 的权限校验，方便各组件直接调用

    # def is_token_right(self):
    #     token = self.request.query_params.get('token')
    #     ok_token = settings.HEALTH_CHECK_TOKEN
    #     if ok_token and token != ok_token:
    #         return False
    #     return True

    # def is_localhost(self):
    #     ip = get_request_ip(self.request)
    #     return ip in ['localhost', '127.0.0.1']

    # def check_permissions(self, request):
    #      if self.is_token_right():
    #          return
    #      if self.is_localhost():
    #          return
    #      msg = '''
    #      Health check token error,
    #      Please set query param in url and
    #      same with setting HEALTH_CHECK_TOKEN.
    #      eg: $PATH/?token=$HEALTH_CHECK_TOKEN
    #      '''
    #      self.permission_denied(request, message={'error': msg}, code=403)


class HealthCheckView(HealthApiMixin):
    permission_classes = (AllowAny,)

    @staticmethod
    def get_db_status():
        t1 = time.time()
        try:
            User.objects.first()
            t2 = time.time()
            return True, t2 - t1
        except:
            t2 = time.time()
            return False, t2 - t1

    def get_redis_status(self):
        key = 'HEALTH_CHECK'

        t1 = time.time()
        try:
            value = '1'
            cache.set(key, '1', 10)
            got = cache.get(key)
            t2 = time.time()
            if value == got:
                return True, t2 -t1
            return False, t2 -t1
        except:
            t2 = time.time()
            return False, t2 - t1

    def get(self, request):
        redis_status, redis_time = self.get_redis_status()
        db_status, db_time = self.get_db_status()
        status = all([redis_status, db_status])
        data = {
            'status': status,
            'db_status': db_status,
            'db_time': db_time,
            'redis_status': redis_status,
            'redis_time': redis_time,
            'time': int(time.time())
        }
        return Response(data)


class PrometheusMetricsApi(HealthApiMixin):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        util = ComponentsPrometheusMetricsUtil()
        metrics_text = util.get_prometheus_metrics_text()
        return HttpResponse(metrics_text, content_type='text/plain; version=0.0.4; charset=utf-8')

