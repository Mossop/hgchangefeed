# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.conf.urls import patterns, url

from website import views
from website import feeds

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^(?P<repository_name>[^/]+)/file/(?P<path_name>.*)$', views.path, name='path'),
    url(r'^(?P<repository_name>[^/]+)/feed/(?P<path_name>.*)$', feeds.path, name='feed'),
    url(r'^(?P<repository_name>[^/]+)/rev/(?P<changeset_id>.*)$', views.changeset, name='changeset'),
)
