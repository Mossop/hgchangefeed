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

class ManagedPrimaryKey(models.Model):
    @classmethod
    def next_id(cls):
        if not hasattr(cls, "max_id"):
            max_id = cls.objects.aggregate(models.Max('id'))["id__max"]
            if max_id is None:
                max_id = 0
            setattr(cls, "max_id", max_id)
        cls.max_id = cls.max_id + 1
        return cls.max_id

    class Meta:
        abstract = True

class Repository(models.Model):
    localpath = models.CharField(max_length = 255, unique = True)
    url = models.TextField(null = True)
    name = models.CharField(max_length = 50, unique = True)
    hidden = models.BooleanField(default = True)

    @property
    def root(self):
        return Path.objects.get(repository = self, parent = None)

    def get_absolute_url(self):
        return self.url

    def __unicode__(self):
        return self.name

class Path(ManagedPrimaryKey):
    id = models.IntegerField(primary_key = True)
    name = models.TextField()
    path = models.TextField()
    parent = models.ForeignKey("self", null = True, related_name = "children")
    repository = models.ForeignKey(Repository)
    is_dir = models.BooleanField()

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

class Ancestor(models.Model):
    path = models.ForeignKey(Path, related_name = "ancestors")
    ancestor = models.ForeignKey(Path, related_name = "+")
    depth = models.IntegerField()

    class Meta:
        unique_together = ("path", "ancestor")

class Changeset(ManagedPrimaryKey):
    id = models.IntegerField(primary_key = True)
    repository = models.ForeignKey(Repository, related_name = "changesets")
    rev = models.IntegerField()
    hex = models.CharField(max_length = 40)
    author = models.TextField()
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

class Change(ManagedPrimaryKey):
    id = models.IntegerField(primary_key = True)
    changeset = models.ForeignKey(Changeset, related_name = "changes")
    path = models.ForeignKey(Path, related_name = "changes")
    type = models.CharField(max_length = 1, choices = CHANGE_TYPES)

    def __unicode__(self):
        return "%s %s" % (self.type, self.path.path)

    class Meta:
        unique_together = ("changeset", "path")
