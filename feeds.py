# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse

from website.models import *

TYPEMAP = {
    "added": "A",
    "removed": "R",
    "modified": "M",
}

class PathFeedRequest(object):
    def __init__(self, path, types):
        self.path = path
        self.types = types

class PathFeed(Feed):
    description_template = 'pathfeed.html'

    def get_object(self, request, repository_name, path_name):
        repository = get_object_or_404(Repository, name = repository_name)
        path = get_object_or_404(Path, repository = repository, path = path_name)
        types = None
        if "types" in request.GET:
            types = [TYPEMAP[t] for t in request.GET["types"].split(",")]
        return PathFeedRequest(path, types)

    def title(self, req):
        return "Changes in %s %s" % (req.path.repository, req.path)

    def link(self, req):
        return reverse('path', args=[req.path.repository, req.path])

    def description(self, req):
        return "Changes recently made to %s in %s" % (req.path, req.path.repository)

    def items(self, req):
        changesets = Changeset.objects.filter(changes__pathlist__in = [req.path]).distinct()
        if req.types is not None:
            changesets = [c for c in changesets if c.changes.filter(type__in = req.types).count() > 0]
        return changesets[:20]

    def item_title(self, changeset):
        return "Changeset %s" % changeset

    def item_author_name(self, changeset):
        return changeset.user.name

    def item_pubdate(self, changeset):
        return changeset.localdate
