# -*- coding:utf-8 -*-
"""
Creates permissions for all installed apps that need permissions.
"""

from django.contrib.auth import models as auth_app
from django.db.models import get_models, signals


def _get_permission_codename(action, opts):
    return u'%s_%s' % (action, opts.object_name.lower())

def _get_all_permissions(opts):
    "Returns (codename, name) for all permissions in the given opts."
    perms = []

    # 添加固定的权限
    for action in ('add', 'change', 'delete', 'view'):
        perms.append((_get_permission_codename(action, opts), u'Can %s %s' % (action, opts.verbose_name_raw)))

    # 自定义的权限
    return perms + list(opts.permissions)

all_perms = None

def create_permissions(app, created_models, verbosity, **kwargs):
    from django.contrib.contenttypes.models import ContentType

    app_models = get_models(app)

    # print "create_permissions--------->"

    # This will hold the permissions we're looking for as
    # (content_type, (codename, name))
    searched_perms = list()
    # The codenames and ctypes that should exist.
    ctypes = set()
    for klass in app_models:
        ctype = ContentType.objects.get_for_model(klass)
        ctypes.add(ctype)
        for perm in _get_all_permissions(klass._meta):
            searched_perms.append((ctype, perm)) # 将要生成的Permissions

    # Find all the Permissions that have a context_type for a model we're
    # looking for.  We don't need to check for codenames since we already have
    # a list of the ones we're going to create.
    global all_perms
    if not all_perms:
        # 一口气读取所有的Permission(假设Permission的个数不多)
        all_perms = set(auth_app.Permission.objects.all().values_list("content_type", "codename"))

    for ctype, (codename, name) in searched_perms:
        # If the permissions exists, move on.
        # codename比较紧凑
        if (ctype.pk, codename) in all_perms:
            continue
        # print "Add New Permission: ", ctype, codename, name
        p = auth_app.Permission.objects.create(
            codename=codename,
            name=name,
            content_type=ctype
        )
        if verbosity >= 2:
            print "Adding permission '%s'" % p


def create_superuser(app, created_models, verbosity, **kwargs):
    from django.core.management import call_command

    if auth_app.User in created_models and kwargs.get('interactive', True):
        msg = ("\nYou just installed Django's auth system, which means you "
            "don't have any superusers defined.\nWould you like to create one "
            "now? (yes/no): ")
        confirm = raw_input(msg)
        while 1:
            if confirm not in ('yes', 'no'):
                confirm = raw_input('Please enter either "yes" or "no": ')
                continue
            if confirm == 'yes':
                call_command("createsuperuser", interactive=True)
            break

# 在post_syncdb中调用 create_permissions
signals.post_syncdb.connect(create_permissions,dispatch_uid = "django.contrib.auth.management.create_permissions")
signals.post_syncdb.connect(create_superuser, sender=auth_app, dispatch_uid = "django.contrib.auth.management.create_superuser")
