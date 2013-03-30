#!/usr/bin/env python

from mercurial import demandimport;
demandimport.disable()

import os
import sys

project = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if project not in sys.path:
    sys.path.insert(0, project)
os.environ['DJANGO_SETTINGS_MODULE'] = 'hgchangefeed.settings'

from datetime import datetime

from mercurial.encoding import encoding

from django.db import transaction
from django.utils.tzinfo import FixedOffset

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
        change.pathlist.add(path)
        path = path.parent

@transaction.commit_on_success
def hook(ui, repo, node, **kwargs):
    repository = get_repository(kwargs["url"])

    # All changesets from node to "tip" inclusive are part of this push.
    rev = repo.changectx(node).rev()
    tip = repo.changectx("tip").rev()

    for i in xrange(rev, tip + 1):
        changectx = repo.changectx(i)

        tz = FixedOffset(-changectx.date()[1] / 60)
        date = datetime.fromtimestamp(changectx.date()[0], tz)

        try:
            changeset = Changeset.objects.get(repository = repository, hex = changectx.hex())
            changeset.delete()
            ui.warn("Deleting stale information for changeset %s\n" % changeset)
        except:
            pass

        changeset = Changeset(repository = repository,
                              rev = changectx.rev(),
                              hex = changectx.hex(),
                              user = get_user(changectx.user()),
                              date = date,
                              tz = -changectx.date()[1] / 60,
                              description = unicode(changectx.description(), encoding))
        changeset.save()

        parents = changectx.parents()

        count = 0
        for file in changectx.files():
            path = get_path(repository, file)

            type = "M"

            if not file in changectx:
                if all([file in c for c in parents]):
                    type = "R"
                else:
                    continue
            else:
                filectx = changectx[file]
                if not any([file in c for c in parents]):
                    type = "A"
                elif all([filectx.cmp(c[file]) for c in parents]):
                    type = "M"
                else:
                    continue

            count = count + 1
            change = Change(changeset = changeset, path = path, type = type)
            change.save()

            add_change(change)

        if count == 0:
            changeset.delete()

    return False
