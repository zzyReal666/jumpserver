from rest_framework import serializers
from perms.models import Action
from orgs.mixins.serializers import BulkOrgResourceModelSerializer

__all__ = ['ActionsDisplayField', 'ActionsField', 'BasePermissionSerializer']


class ActionsField(serializers.MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = Action.CHOICES
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        return Action.value_to_choices(value)

    def to_internal_value(self, data):
        if data is None:
            return data
        return Action.choices_to_value(data)


class ActionsDisplayField(ActionsField):
    def to_representation(self, value):
        values = super().to_representation(value)
        choices = dict(Action.CHOICES)
        return [choices.get(i) for i in values]


class BasePermissionSerializer(BulkOrgResourceModelSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_actions_field()

    def set_actions_field(self):
        actions = self.fields.get('actions')
        if not actions:
            return
        choices = actions._choices
        choices = self._filter_actions_choices(choices)
        actions._choices = choices
        actions.default = list(choices.keys())

    def _filter_actions_choices(self, choices):
        return choices
