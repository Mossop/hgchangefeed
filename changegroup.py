#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

MAX_CHANGESETS = 1000

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

def add_paths(ui, repository, files):
    root = Path(repository = repository, name = '', path = '', parentpath = '')
    paths = [root]
    parentlist = [root]

    pos = 0
    for file in files:
        ui.progress("indexing files", pos, item = file, total = len(files))

        while not file.startswith(parentlist[-1].path):
            parentlist.pop()

        remains = file[len(parentlist[-1].path):].split("/")
        if not remains[0]:
            remains.pop(0)

        while len(remains):
            name = remains[0]
            parentpath = parentlist[-1].path
            path = parentpath
            if path:
                path = path + "/"
            path = path + remains[0]
            remains.pop(0)

            newpath = Path(repository = repository,
                           name = name,
                           path = path,
                           parentpath = parentlist[-1].path,
                           is_dir = True if len(remains) else False)
            paths.append(newpath)

            if len(remains):
                parentlist.append(newpath)

        pos = pos + 1

    ui.progress("indexing files", None)
    Path.objects.bulk_create(paths)
    ui.status("added %d files to database\n" % len(paths))

def get_path(repository, path, is_dir = False):
    try:
        return Path.objects.get(repository = repository, path = path)
    except Path.DoesNotExist:
        parts = path.rsplit("/", 1)
        parent = get_path(repository, parts[0] if len(parts) > 1 else '', True)
        result = Path(repository = repository, path = path, name = parts[-1], parentpath = parent.path, is_dir = is_dir)
        result.save()
        return result

def get_user(username):
    user, created = User.objects.get_or_create(user = unicode(username, encoding))
    return user

def add_changesets(ui, repo, repository, rev, tip):
    changeset_count = 0
    changes = []

    for i in xrange(rev, tip + 1):
        changectx = repo.changectx(i)
        ui.progress("indexing changesets", i - rev, changectx.hex(), total = tip - rev + 1)

        tz = FixedOffset(-changectx.date()[1] / 60)
        date = datetime.fromtimestamp(changectx.date()[0], tz)

        try:
            changeset = Changeset.objects.get(repository = repository, hex = changectx.hex())
            ui.warn("deleting stale information for changeset %s\n" % changeset)
            changeset.delete()
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

            changes.append(Change(changeset = changeset, path = path, type = type))

        if len(changes) == 0:
            changeset.delete()
        else:
            changeset_count = changeset_count + 1

    ui.progress("indexing changesets", None)
    Change.objects.bulk_create(changes)
    ui.status("added %d changesets with changes to %d files to database\n" % (changeset_count, len(changes)))

    oldsets = Changeset.objects.all()[MAX_CHANGESETS:]
    pos = 0
    for changeset in oldsets:
        ui.progress("expiring changesets", pos, changectx.hex(), total = len(oldsets))
        changeset.delete()
        pos = pos + 1
    ui.progress("expiring changesets", None)
    if len(oldsets) > 0:
        ui.status("expired %d changesets from database\n" % len(oldsets))

    return False

@transaction.commit_on_success
def hook(ui, repo, node, **kwargs):
    url = kwargs["url"]
    tip = repo.changectx("tip")

    try:
        repository = Repository.objects.get(url = url)

        # Existing repository, only add new changesets
        # All changesets from node to "tip" inclusive are part of this push.
        rev = max(tip.rev() - MAX_CHANGESETS, repo.changectx(node).rev())
        add_changesets(ui, repo, repository, rev, tip.rev())

    except Repository.DoesNotExist:
        stripped = url
        if url[-1] == "/":
            stripped = url[:-1]
        name = stripped.split("/")[-1]

        repository = Repository(url = url, name = name)
        repository.save()

        add_paths(ui, repository, [f for f in tip])

        # New repository, attempt to add the maximum number of changesets
        rev = tip.rev() + 1 - MAX_CHANGESETS
        add_changesets(ui, repo, repository, rev, tip.rev())
