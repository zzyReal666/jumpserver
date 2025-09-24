# -*- coding: utf-8 -*-
#
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from common.utils import get_logger

UserModel = get_user_model()
logger = get_logger(__file__)


@csrf_protect
@require_http_methods(["GET", "POST"])
def usb_key_login_view(request):
    """USB Key登录视图"""
    if request.method == 'GET':
        return render(request, 'authentication/login_usbkey.html')
    
    # POST请求处理USB Key认证
    signature = request.POST.get('sign_value')
    random_data = request.POST.get('random')
    
    if not signature or not random_data:
        return JsonResponse({'error': _('Missing signature or random data')}, status=400)
    
    # 使用USB Key认证后端进行认证
    from authentication.backends.usb_key import USBKeyAuthBackend
    backend = USBKeyAuthBackend()
    
    user = backend.authenticate(
        request=request,
        signature=signature,
        random_data=random_data
    )
    
    if user:
        auth_login(request, user, backend='authentication.backends.usb_key.USBKeyAuthBackend')
        return JsonResponse({'success': True, 'redirect_url': '/'})
    else:
        return JsonResponse({'error': _('USB Key authentication failed')}, status=400)