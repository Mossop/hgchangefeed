from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse

from website.models import *

class PathFeed(Feed):
    description_template = 'pathfeed.html'

    def get_object(self, request, repository_name, path_name):
        repository = get_object_or_404(Repository, name = repository_name)
        return get_object_or_404(Path, repository = repository, path = path_name)

    def title(self, path):
        return "Changes in %s %s" % (path.repository, path)

    def link(self, path):
        return reverse('path', args=[path.repository, path])

    def description(self, path):
        return "Changes recently made to %s in %s" % (path, path.repository)

    def items(self, path):
        return Changeset.objects.filter(changes__pathlist__in = [path]).distinct()[:20]

    def item_title(self, changeset):
        return "Changeset %s" % changeset

    def item_author_name(self, changeset):
        return changeset.user.name

    def item_pubdate(self, changeset):
        return changeset.localdate
