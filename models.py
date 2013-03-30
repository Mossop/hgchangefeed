# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.db import models
from django.utils.tzinfo import FixedOffset

CHANGE_TYPES = (
    ("A", "Added"),
    ("M", "Modified"),
    ("R", "Removed"),
)

class Repository(models.Model):
    url = models.CharField(max_length = 255, unique = True)
    name = models.CharField(max_length = 50, unique = True)

    @property
    def root(self):
        return Path.objects.get(repository = self, parent = None)

    def get_absolute_url(self):
        return self.url

    def __unicode__(self):
        return self.name

class Path(models.Model):
    name = models.TextField()
    path = models.TextField()
    parentpath = models.TextField()
    repository = models.ForeignKey(Repository)
    _children = None

    @property
    def parent(self):
        if not self.path:
            return None

        try:
            return Path.objects.get(repository = self.repository, path = self.parentpath)
        except Path.DoesNotExist:
            return None

    @property
    def children(self):
        if self._children is not None:
            return self._children
        self._children = [p for p in Path.objects.filter(repository = self.repository, parentpath = self.path)]
        return self._children

    def is_dir(self):
        return len(self.children) > 0

    def parentlist(self):
        result = []
        parent = self
        while parent is not None:
            result.insert(0, parent)
            parent = parent.parent
        result.pop(0)
        return result

    def __unicode__(self):
        return self.path

    class Meta:
        ordering = ["path"]

class User(models.Model):
    user = models.CharField(max_length = 255, unique = True)

    @property
    def name(self):
        return self.user.split(" <")[0]

    def __unicode__(self):
        return self.name

class Changeset(models.Model):
    repository = models.ForeignKey(Repository, related_name = "changesets")
    rev = models.IntegerField()
    hex = models.CharField(max_length = 40)
    user = models.ForeignKey(User, related_name = "changesets")
    date = models.DateTimeField()
    tz = models.IntegerField()
    description = models.TextField()

    @property
    def localdate(self):
        tz = FixedOffset(self.tz)
        return self.date.astimezone(tz)

    @property
    def shorthex(self):
        return self.hex[0:12]

    @property
    def url(self):
        return "%srev/%s" % (self.repository.url, self.shorthex)

    @property
    def pushlog(self):
        return "%spushloghtml?changeset=%s" % (self.repository.url, self.shorthex)

    @property
    def changetypes(self):
        changes = set()
        for change in self.changes.all():
            changes.add(change.type)
        return changes

    def get_absolute_url(self):
        return self.url

    def __unicode__(self):
        return self.shorthex

    class Meta:
        unique_together = (("repository", "rev"), ("repository", "hex"))
        ordering = ["-rev"]
        get_latest_by = "rev"

class Change(models.Model):
    changeset = models.ForeignKey(Changeset, related_name = "changes")
    path = models.ForeignKey(Path, related_name = "changes")
    type = models.CharField(max_length = 1, choices = CHANGE_TYPES)

    def __unicode__(self):
        return "%s %s" % (self.type, self.path.path)

    class Meta:
        unique_together = ("changeset", "path")
