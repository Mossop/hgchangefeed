from django.shortcuts import get_object_or_404, render

from website.models import *

TYPEMAP = {
    "added": "A",
    "removed": "R",
    "modified": "M",
}

def index(request):
    repositories = Repository.objects.order_by('name')
    context = { "repositories": repositories }
    return render(request, "index.html", context)

def path(request, repository_name, path_name):
    repository = get_object_or_404(Repository, name = repository_name)
    path = get_object_or_404(Path, repository = repository, path = path_name)

    changesets = Changeset.objects.filter(changes__pathlist__in = [path]).distinct()
    if "types" in request.GET:
        types = [TYPEMAP[t] for t in request.GET["types"].split(",")]
        changesets = [c for c in changesets if c.changes.filter(type__in = types).count() > 0]

    context = {
      "repository": repository,
      "path": path,
      "changesets": changesets[:100],
      "paths": path.children.all(),
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
