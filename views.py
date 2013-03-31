# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.shortcuts import get_object_or_404, render

from website.models import *

TYPEMAP = {
    "added": "A",
    "removed": "R",
    "modified": "M",
}

def path_cmp(a, b):
    if a.is_dir == b.is_dir:
        return cmp(a.path, b.path)
    return -1 if a.is_dir else 1

def index(request):
    repositories = Repository.objects.order_by('name')
    context = { "repositories": repositories }
    return render(request, "index.html", context)

def path(request, repository_name, path_name):
    repository = get_object_or_404(Repository, name = repository_name)
    path = get_object_or_404(Path, repository = repository, path = path_name)

    queryparams = {
        "changes__pathlist__path": path,
    }

    if "types" in request.GET:
        types = [TYPEMAP[t] for t in request.GET["types"].split(",")]
        queryparams["changes__type__in"] = types

    changesets = Changeset.objects.filter(**queryparams).distinct()

    query = request.GET.urlencode()
    if query:
        query = "?" + query

    context = {
      "repository": repository,
      "path": path,
      "changesets": changesets[:200],
      "paths": sorted(path.children.all(), path_cmp),
      "query": query,
    }
    return render(request, "path.html", context)

def changeset(request, repository_name, changeset_id):
    repository = get_object_or_404(Repository, name = repository_name)
    changeset = get_object_or_404(Changeset, repository = repository, hex__startswith = changeset_id)
    context = {
      "repository": repository,
      "changeset": changeset,
      "changes": changeset.changes.order_by("path__path"),
    }
    return render(request, "changeset.html", context)
