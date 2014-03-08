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
    def __init__(self, repository, path, types):
        self.repository = repository
        self.path = path
        self.types = types

class ChangesetItem(object):
    def __init__(self, repository, changeset):
        self.repository = repository
        self.changeset = changeset

class PathFeed(Feed):
    description_template = 'pathfeed.html'

    def get_object(self, request, repository_name, path_name):
        path = Path.get_by_path(path_name)
        repository = get_object_or_404(Repository, name = repository_name, paths = path, hidden = False)
        types = None
        if "types" in request.GET:
            types = [TYPEMAP[t] for t in request.GET["types"].split(",")]
        return PathFeedRequest(repository, path, types)

    def title(self, req):
        return "Changes in %s %s" % (req.repository, req.path)

    def link(self, req):
        return reverse('path', args=[req.repository, req.path])

    def description(self, req):
        return "Changes recently made to %s in %s" % (req.path, req.repository)

    def items(self, req):
        queryparams = {
            "pushes__push__repository": req.repository
        }

        if req.path.parent is not None:
            queryparams["changes__path__ancestors__ancestor"] = req.path

        if req.types is not None:
            queryparams["changes__type__in"] = req.types

        changesets = Changeset.objects.filter(**queryparams).distinct().order_by("-pushes__push__push_id", "-pushes__index")[:20]
        return [ChangesetItem(req.repository, c) for c in changesets]

    def item_title(self, item):
        return "Changeset %s" % item.changeset

    def item_author_name(self, item):
        return item.changeset.author.split(" <")[0]

    def item_pubdate(self, item):
        return item.changeset.localdate

    def item_link(self, item):
        return "%srev/%s" % (item.repository.url, item.changeset)
