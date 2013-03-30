from django.conf.urls import patterns, url

from website import views
from website import feeds

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^(?P<repository_name>[^/]+)/file/(?P<path_name>.*)$', views.path, name='path'),
    url(r'^(?P<repository_name>[^/]+)/feed/(?P<path_name>.*)$', feeds.PathFeed(), name='feed'),
    url(r'^(?P<repository_name>[^/]+)/rev/(?P<changeset_id>.*)$', views.changeset, name='changeset'),
)
