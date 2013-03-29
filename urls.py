from django.conf.urls import patterns, url

from website import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^(?P<repository_name>[^/]+)/file/(?P<path_name>.*)$', views.path, name='path'),
    url(r'^(?P<repository_name>[^/]+)/rev/(?P<changeset_id>.*)$', views.changeset, name='changeset'),
)
