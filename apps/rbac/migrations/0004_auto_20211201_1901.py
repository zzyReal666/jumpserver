import time
from django.db import migrations

from rbac.builtin import BuiltinRole


def migrate_system_role_binding(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    user_model = apps.get_model('users', 'User')
    role_binding_model = apps.get_model('rbac', 'SystemRoleBinding')
    users = user_model.objects.using(db_alias).all()

    grouped_users = [users[i:i+1000] for i in range(0, len(users), 1000)]
    for i, group in enumerate(grouped_users):
        role_bindings = []
        start = time.time()
        for user in group:
            role = BuiltinRole.get_system_role_by_old_name(user.role)
            role_binding = role_binding_model(scope='system', user_id=user.id, role_id=role.id)
            role_bindings.append(role_binding)
        role_binding_model.objects.bulk_create(role_bindings, ignore_conflicts=True)
        print("Create role binding: {}-{} using: {:.2f}s".format(
            i*1000, i*1000 + len(group), time.time()-start
        ))


def migrate_org_role_binding(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    org_member_model = apps.get_model('orgs', 'OrganizationMember')
    role_binding_model = apps.get_model('rbac', 'RoleBinding')
    members = org_member_model.objects.using(db_alias)\
        .only('role', 'user_id', 'org_id')\
        .all()

    grouped_members = [members[i:i+1000] for i in range(0, len(members), 1000)]
    for i, group in enumerate(grouped_members):
        role_bindings = []
        start = time.time()
        for member in group:
            role = BuiltinRole.get_org_role_by_old_name(member.role)
            role_binding = role_binding_model(
                scope='org',
                user_id=member.user_id,
                role_id=role.id,
                org_id=member.org_id
            )
            role_bindings.append(role_binding)
        role_binding_model.objects.bulk_create(role_bindings, ignore_conflicts=True)
        print("Create role binding: {}-{} using: {:.2f}s".format(
            i*1000, i*1000 + len(group), time.time()-start
        ))


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0003_auto_20211130_1037'),
    ]

    operations = [
        migrations.RunPython(migrate_system_role_binding),
        migrations.RunPython(migrate_org_role_binding)
    ]
