# -*- coding:utf-8 -*-
from django.core.urlresolvers import RegexURLPattern, RegexURLResolver
from django.core.exceptions import ImproperlyConfigured

__all__ = ['handler404', 'handler500', 'include', 'patterns', 'url']

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

def include(arg, namespace=None, app_name=None):
    if isinstance(arg, tuple):
        # callable returning a namespace hint
        if namespace:
            raise ImproperlyConfigured('Cannot override the namespace for a dynamic module that provides a namespace')
        urlconf_module, app_name, namespace = arg
    else:
        # No namespace hint - use manually provided namespace
        urlconf_module = arg
    return (urlconf_module, app_name, namespace)

def patterns(prefix, *args):
    """
    :param prefix:
    :param args:
    :return:

    用法:
    urlpatterns = patterns('',
            url(r'^mall/', include('mall.urls')),
            url(r'^community/', include('community.urls')),
            url(r'^personal_doctor/', include('personal_doctor.urls')),
            # URLs 4 chunyu website:
            url(r'^$', index, {}, name='index'),
            url(r'^wapindex$', index, {}, name='wapindex'),
            ....

    """
    pattern_list = []
    for t in args:
        # include等返回的为list
        if isinstance(t, (list, tuple)):
            t = url(prefix=prefix, *t)
        # url返回的为 RegexPattern或RgexURLResolver
        elif isinstance(t, RegexURLPattern):
            t.add_prefix(prefix)

        pattern_list.append(t)
    return pattern_list

def url(regex, view, kwargs=None, name=None, prefix=''):
    """
    :param regex:
    :param view:
    :param kwargs:
    :param name:
    :param prefix:
    :return:


    """
    if isinstance(view, (list,tuple)):
        # For include(...) processing.
        urlconf_module, app_name, namespace = view
        return RegexURLResolver(regex, urlconf_module, kwargs, app_name=app_name, namespace=namespace)
    else:
        if isinstance(view, basestring):
            if not view:
                raise ImproperlyConfigured('Empty URL pattern view name not permitted (for pattern %r)' % regex)
            if prefix:
                view = prefix + '.' + view
        return RegexURLPattern(regex, view, kwargs, name)

