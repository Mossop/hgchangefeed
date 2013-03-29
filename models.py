from django.db import models

CHANGE_TYPES = (
    ("A", "Addition"),
    ("M", "Modification"),
    ("D", "Deleted"),
)

class Repository(models.Model):
    url = models.TextField(unique = True)
    name = models.TextField(unique = True)

    @property
    def root(self):
        return Path.objects.get(repository = self, parent = None)

    def __unicode__(self):
        return self.name

class Path(models.Model):
    name = models.TextField()
    path = models.TextField()
    parent = models.ForeignKey('self', related_name = "children", null = True)
    repository = models.ForeignKey(Repository)

    def __unicode__(self):
        return self.path

    class Meta:
        unique_together = (("repository", "path"), ("parent", "name"))

class User(models.Model):
    user = models.TextField(unique = True)

    @property
    def name(self):
        return self.user.split(" <")[0]

    def __unicode__(self):
        return self.name

class Changeset(models.Model):
    repository = models.ForeignKey(Repository)
    rev = models.IntegerField()
    hex = models.CharField(max_length = 40)
    user = models.ForeignKey(User)
    date = models.DateTimeField()
    description = models.TextField()
    paths = models.ManyToManyField(Path, through = "PathChanges")

    @property
    def shorthex(self):
        return self.hex[0:12]

    @property
    def url(self):
        return "%srev/%s" % (self.repository.url, self.shorthex)

    def __unicode__(self):
        return self.shorthex

    class Meta:
        unique_together = (("repository", "rev"), ("repository", "hex"))
        ordering = ["-rev"]

class Change(models.Model):
    changeset = models.ForeignKey(Changeset)
    path = models.ForeignKey(Path)
    type = models.CharField(max_length=1, choices=CHANGE_TYPES)

    def __unicode__(self):
        return "%s %s" % (self.type, self.path.path)

    class Meta:
        unique_together = ("changeset", "path")

class PathChanges(models.Model):
    changeset = models.ForeignKey(Changeset)
    path = models.ForeignKey(Path)
    changes = models.ManyToManyField(Change)

    class Meta:
        unique_together = ("changeset", "path")

