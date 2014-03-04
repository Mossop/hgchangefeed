# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.db import models
from django.conf import settings
from pytz import FixedOffset

DATABASE_ENGINE = settings.DATABASES['default']['ENGINE']

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
    url = models.TextField(null = True)
    name = models.CharField(max_length = 50, unique = True)
    range = models.IntegerField()
    hidden = models.BooleanField(default = True)

    @property
    def root(self):
        return Path.get_by_path('')

    def get_absolute_url(self):
        return self.url

    def __unicode__(self):
        return self.name

class Path(ManagedPrimaryKey):
    id = models.IntegerField(primary_key = True)
    name = models.CharField(max_length = 100)
    parent = models.ForeignKey("self", null = True, related_name = "children")
    repositories = models.ManyToManyField(Repository, related_name = "paths")
    is_dir = models.BooleanField()

    def parentlist(self):
        if self.parent:
            return [a.ancestor for a in Ancestor.objects.filter(path = self).exclude(ancestor = self)]
        return []

    @classmethod
    def get_by_path(cls, path):
        if path == '':
            return Path.objects.get(parent = None)

        names = path.split('/')

        filter = dict()
        rel = ""
        for name in reversed(names):
            filter[rel + "name"] = name
            rel = "parent__" + rel
        filter[rel + "parent"] = None

        return Path.objects.get(**filter)

    @property
    def path(self):
        if self.parent:
            paths = self.parentlist()[1:]
            paths.append(self)
            return '/'.join([p.name for p in paths])
        return ''

    def __unicode__(self):
        return self.path

    class Meta:
        unique_together = ("parent", "name")
        ordering = ["name"]

class Ancestor(models.Model):
    path = models.ForeignKey(Path, related_name = "ancestors")
    ancestor = models.ForeignKey(Path, related_name = "+")
    depth = models.IntegerField()

    class Meta:
        unique_together = ("path", "ancestor")

class Push(models.Model):
    push_id = models.IntegerField()
    repository = models.ForeignKey(Repository, related_name = "pushes")
    user = models.TextField()
    date = models.DateTimeField()

    class Meta:
        unique_together = ("repository", "push_id")

class Changeset(models.Model):
    hex = models.CharField(max_length = 40, primary_key = True)
    author = models.TextField()
    date = models.DateTimeField()
    tzoffset = models.IntegerField()
    description = models.TextField()

    @property
    def localdate(self):
        tz = FixedOffset(self.tzoffset)
        return self.date.astimezone(tz)

    @property
    def shorthex(self):
        return self.hex[0:12]

    @property
    def parents(self):
        return (p.parent for p in self.parentchangesets.all())

    @property
    def children(self):
        return (c.changeset for c in ChangesetParent.objects.filter(parenthex = self.hex))

    @property
    def changetypes(self):
        changes = set()
        for change in self.changes.all():
            changes.add(change.type)
        return changes

    def __unicode__(self):
        return self.shorthex

class ChangesetParent(models.Model):
    changeset = models.ForeignKey(Changeset, related_name = "parentchangesets")
    parenthex = models.CharField(max_length = 40, db_index = True)

    @property
    def parent(self):
        try:
            return Changeset.objects.get(hex = self.parenthex)
        except Changeset.DoesNotExist:
            return None

    class Meta:
        unique_together = ("changeset", "parenthex")

class PushChangeset(models.Model):
    push = models.ForeignKey(Push, related_name = "changesets")
    changeset = models.ForeignKey(Changeset, related_name = "pushes")
    index = models.IntegerField()

    class Meta:
        unique_together = (("push", "changeset"), ("push", "index"))

class Change(ManagedPrimaryKey):
    id = models.IntegerField(primary_key = True)
    changeset = models.ForeignKey(Changeset, related_name = "changes")
    path = models.ForeignKey(Path, related_name = "changes")
    type = models.CharField(max_length = 1, choices = CHANGE_TYPES)

    def __unicode__(self):
        return "%s %s" % (self.type, self.path.path)

    class Meta:
        unique_together = ("changeset", "path")
