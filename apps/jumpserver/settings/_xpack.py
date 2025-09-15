# -*- coding: utf-8 -*-
#

import datetime
import os

from .base import INSTALLED_APPS, TEMPLATES
from .. import const

current_year = datetime.datetime.now().year
corporation = f'PAM 特权账号管理 © 2014-{current_year}'

XPACK_DIR = os.path.join(const.BASE_DIR, 'xpack')
XPACK_DISABLED = os.environ.get('XPACK_ENABLED') in ['0', 'false', 'False', 'no', 'No']
XPACK_ENABLED = False
if not XPACK_DISABLED:
    XPACK_ENABLED = os.path.isdir(XPACK_DIR)
XPACK_TEMPLATES_DIR = []
XPACK_CONTEXT_PROCESSOR = []
XPACK_LICENSE_IS_VALID = True   # Xpack 许可证有效
XPACK_LICENSE_EDITION = "professional"  # 设置为专业版
XPACK_LICENSE_EDITION_ULTIMATE = False
XPACK_LICENSE_INFO = {
    'corporation': corporation,
    'edition': 'professional',
    'count': 1000,
    'valid': True,
}

XPACK_LICENSE_CONTENT = 'professional'

if XPACK_ENABLED:
    from xpack.utils import get_xpack_templates_dir, get_xpack_context_processor

    INSTALLED_APPS.insert(0, 'xpack.apps.XpackConfig')
    XPACK_TEMPLATES_DIR = get_xpack_templates_dir(const.BASE_DIR)
    XPACK_CONTEXT_PROCESSOR = get_xpack_context_processor()
    TEMPLATES[0]['DIRS'].extend(XPACK_TEMPLATES_DIR)
    TEMPLATES[0]['OPTIONS']['context_processors'].extend(XPACK_CONTEXT_PROCESSOR)
