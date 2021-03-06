# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from django.utils import feedgenerator
from django.http import HttpResponse
from django.template.loader import render_to_string

from website.models import *
from website.shared import *

def path(request, repository_name, path_name):
    path = Path.get_by_path(path_name)
    repository = get_object_or_404(Repository, name = repository_name, paths = path, hidden = False)

    queryparams = {
        "pushes__push__repository": repository,
    }

    if path.parent is not None:
        queryparams["changes__path__ancestors__ancestor"] = path

    if "types" in request.GET:
        types = [TYPEMAP[t] for t in request.GET["types"].split(",")]
        queryparams["changes__type__in"] = types

    changesets = Changeset.objects.filter(**queryparams).distinct().order_by("-pushes__push__push_id", "-pushes__index")
    changesets = list(changesets[:20])
    if len(changesets):
        tag = "feed:%s/%s:%s:%s" % (repository_name, path_name, changesets[0].hex, changesets[-1].hex)
    else:
        tag = "feed:%s/%s::" % (repository_name, path_name)

    return tag_cached(render_path, tag, request, repository, path, changesets)

def render_path(request, repository, path, changesets):
    feed = feedgenerator.Rss201rev2Feed(
        title = "Changes in %s %s" % (repository, path),
        description = "Changes recently made to %s in %s" % (path, repository),
        link = reverse('path', args=[repository, path])
    )

    for changeset in changesets:
        feed.add_item(
            title = "Changeset %s" % changeset,
            description = render_to_string("pathfeed.html", { "changeset": changeset }),
            link = "%srev/%s" % (repository.url, changeset),
            author_name = changeset.author.split(" <")[0],
            pubdate = changeset.localdate,
        )

    return HttpResponse(feed.writeString('UTF-8'), content_type=feed.mime_type)
