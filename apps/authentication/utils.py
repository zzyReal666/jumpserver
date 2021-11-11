# -*- coding: utf-8 -*-
#
import base64
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
from Cryptodome import Random

from django.conf import settings
from .notifications import DifferentCityLoginMessage
from audits.models import UserLoginLog
from audits.const import DEFAULT_CITY
from common.utils import get_request_ip
from common.utils import validate_ip, get_ip_city
from common.utils import get_logger

logger = get_logger(__file__)


def gen_key_pair():
    """ 生成加密key
    用于登录页面提交用户名/密码时，对密码进行加密（前端）/解密（后端）
    """
    random_generator = Random.new().read
    rsa = RSA.generate(1024, random_generator)
    rsa_private_key = rsa.exportKey().decode()
    rsa_public_key = rsa.publickey().exportKey().decode()
    return rsa_private_key, rsa_public_key


def rsa_encrypt(message, rsa_public_key):
    """ 加密登录密码 """
    key = RSA.importKey(rsa_public_key)
    cipher = PKCS1_v1_5.new(key)
    cipher_text = base64.b64encode(cipher.encrypt(message.encode())).decode()
    return cipher_text


def rsa_decrypt(cipher_text, rsa_private_key=None):
    """ 解密登录密码 """
    if rsa_private_key is None:
        # rsa_private_key 为 None，可以能是API请求认证，不需要解密
        return cipher_text

    key = RSA.importKey(rsa_private_key)
    cipher = PKCS1_v1_5.new(key)
    cipher_decoded = base64.b64decode(cipher_text.encode())
    # Todo: 弄明白为何要以下这么写，https://xbuba.com/questions/57035263
    if len(cipher_decoded) == 127:
        hex_fixed = '00' + cipher_decoded.hex()
        cipher_decoded = base64.b16decode(hex_fixed.upper())
    message = cipher.decrypt(cipher_decoded, b'error').decode()
    return message


def check_different_city_login_if_need(user, request):
    if not settings.SECURITY_CHECK_DIFFERENT_CITY_LOGIN:
        return

    ip = get_request_ip(request) or '0.0.0.0'

    if not (ip and validate_ip(ip)):
        city = DEFAULT_CITY
    else:
        city = get_ip_city(ip) or DEFAULT_CITY

    city_white = ['LAN', ]
    if city not in city_white:
        last_user_login = UserLoginLog.objects.exclude(city__in=city_white) \
            .filter(username=user.username, status=True).first()

        if last_user_login and last_user_login.city != city:
            DifferentCityLoginMessage(user, ip, city).publish_async()
