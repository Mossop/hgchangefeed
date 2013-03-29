#!/usr/bin/env python

import os
import sys

project = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if project not in sys.path:
    sys.path.insert(0, project)
os.environ['DJANGO_SETTINGS_MODULE'] = 'hgchangefeed.settings'

from datetime import datetime

from mercurial.encoding import encoding

from django.db import transaction

from website.models import *

def get_repository(url):
    try:
        return Repository.objects.get(url = url)
    except Repository.DoesNotExist:
        stripped = url
        if url[-1] == "/":
            stripped = url[:-1]
        name = stripped.split("/")[-1]

        repository = Repository(url = url, name = name)
        repository.save()

        root = Path(repository = repository, name = '', path = '')
        root.save()

        return repository

def get_path(repository, path):
    try:
        return Path.objects.get(repository = repository, path = path)
    except Path.DoesNotExist:
        parts = path.rsplit("/", 1)
        parent = get_path(repository, parts[0] if len(parts) > 1 else '')
        result = Path(repository = repository, path = path, name = parts[-1], parent = parent)
        result.save()
        return result

def get_user(username):
    user, created = User.objects.get_or_create(user = unicode(username, encoding))
    return user

def add_change(change):
    path = change.path
    while path is not None:
        pathchanges, created = PathChanges.objects.get_or_create(path = path, changeset = change.changeset)
        pathchanges.changes.add(change)

        path = path.parent

@transaction.commit_on_success
def hook(ui, repo, node, **kwargs):
    repository = get_repository(kwargs["url"])

    # All changesets from node to "tip" inclusive are part of this push.
    rev = repo.changectx(node).rev()
    tip = repo.changectx("tip").rev()

    for i in xrange(rev, tip + 1):
        changectx = repo.changectx(i)

        changeset = Changeset(repository = repository,
                              rev = changectx.rev(),
                              hex = changectx.hex(),
                              user = get_user(changectx.user()),
                              date = datetime.utcfromtimestamp(changectx.date()[0]),
                              description = changectx.description())
        changeset.save()

        parents = changectx.parents()

        ui.status("%s\n" % changeset)

        for file in changectx.files():
            path = get_path(repository, file)

            type = "A"
            if not file in changectx:
                type = "R"
            elif any([file in c for c in parents]):
                type = "M"

            change = Change(changeset = changeset, path = path, type = type)
            change.save()

            add_change(change)

            ui.status("%s\n" % change)

        ui.status("\n")

    return False
