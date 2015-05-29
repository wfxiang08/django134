# -*- coding:utf-8 -*-
VERSION = (1, 3, 4, 'final-cyom', 0)

def get_version():
    version = '%s.%s' % (VERSION[0], VERSION[1])
    if VERSION[2]:
        version = '%s.%s' % (version, VERSION[2])
    if VERSION[3:] == ('alpha', 0):
        version = '%s pre-alpha' % version
    else:
        if VERSION[3] != 'final':
            version = '%s %s %s' % (version, VERSION[3], VERSION[4])
    from django.utils.version import get_svn_revision
    svn_rev = get_svn_revision()
    if svn_rev != u'SVN-unknown':
        version = "%s %s" % (version, svn_rev)
    return version

def is_chunyu_test_case():
    from django.conf import settings
    return hasattr(settings, "IS_FOR_TESTCASE") and settings.IS_FOR_TESTCASE

def is_app_label_delete_protected(app_label):
    from django.conf import settings
    return hasattr(settings, "DELETE_PROTECTED_APPS") and (app_label in settings.DELETE_PROTECTED_APPS)


# setattr(cls, "is_delete_protected", DeleteProtectedAttribute(related))
# class DeleteProtectedAttribute(object):
#     """
#     """
#     def __init__(self, app_label):
#         # 如果是TestCase则不保护，
#         self.is_delete_protected = not is_chunyu_test_case() and is_app_label_delete_protected(app_label)
#
#     def __get__(self, instance, owner):
#         """
#         Retrieves and caches the value from the datastore on the first lookup.
#         Returns the cached value.
#
#         如果instance为None, 表示是通过class来调用的
#         """
#         self.is_delete_protected
#
#
#     def __set__(self, instance, value):
#         """
#         Deferred loading attributes can be set normally (which means there will
#         never be a database lookup involved.
#         """
#         # 只是为了避免调用attribute函数
#         pass