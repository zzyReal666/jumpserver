from django.db.models import TextChoices

from jumpserver.utils import has_valid_xpack_license
from .protocol import Protocol


class BaseType(TextChoices):
    """
    约束应该考虑代是对平台对限制，避免多余对选项，如: mysql 开启 ssh, 或者开启了也没有作用, 比如 k8s 开启了 domain，目前还不支持
    """
    @classmethod
    def get_constrains(cls):
        constrains = {}

        base = cls._get_base_constrains()
        protocols = cls._get_protocol_constrains()
        automation = cls._get_automation_constrains()

        base_default = base.pop('*', {})
        protocols_default = protocols.pop('*', {})
        automation_default = automation.pop('*', {})

        for k, v in cls.choices:
            tp_base = {**base_default, **base.get(k, {})}
            tp_auto = {**automation_default, **automation.get(k, {})}
            tp_protocols = {**protocols_default, **protocols.get(k, {})}
            tp_protocols = cls._parse_protocols(tp_protocols, k)
            tp_constrains = {**tp_base, 'protocols': tp_protocols, 'automation': tp_auto}
            constrains[k] = tp_constrains
        return constrains

    @classmethod
    def _parse_protocols(cls, protocol, tp):
        settings = Protocol.settings()
        choices = protocol.get('choices', [])
        if choices == '__self__':
            choices = [tp]
        protocols = [{'name': name, **settings.get(name, {})} for name in choices]
        protocols[0]['primary'] = True
        return protocols

    @classmethod
    def _get_base_constrains(cls) -> dict:
        raise NotImplementedError

    @classmethod
    def _get_protocol_constrains(cls) -> dict:
        raise NotImplementedError

    @classmethod
    def _get_automation_constrains(cls) -> dict:
        raise NotImplementedError

    @classmethod
    def internal_platforms(cls):
        raise NotImplementedError

    @classmethod
    def get_community_types(cls):
        raise NotImplementedError

    @classmethod
    def get_types(cls):
        tps = [tp for tp in cls]
        if not has_valid_xpack_license():
            tps = cls.get_community_types()
        return tps

    @classmethod
    def get_choices(cls):
        tps = cls.get_types()
        cls_choices = cls.choices
        return [
            choice for choice in cls_choices
            if choice[0] in tps
        ]


