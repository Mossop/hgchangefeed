from django.shortcuts import get_object_or_404, render

from website.models import *

def index(request):
    repositories = Repository.objects.order_by('name')
    context = { "repositories": repositories }
    return render(request, "index.html", context)

def path(request, repository_name, path_name):
    repository = get_object_or_404(Repository, name = repository_name)
    path = get_object_or_404(Path, repository = repository, path = path_name)
    context = {
      "repository": repository,
      "path": path,
      "changesets": Changeset.objects.filter(changes__pathlist__in = [path]).distinct(),
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
      "paths": Path.objects.filter(allchanges__changeset = changeset).distinct(),
    }
    return render(request, "changeset.html", context)
