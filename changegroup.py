#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

DEFAULT_CHANGESETS = 1000
BATCH_SIZE = 500

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
from django.db.models import Max
from django.utils.tzinfo import FixedOffset

from website.models import *

max_path_id = Path.objects.aggregate(Max('id'))["id__max"]
if max_path_id is None:
    max_path_id = -1
def get_next_path_id():
    global max_path_id
    max_path_id = max_path_id + 1
    return max_path_id

def add_paths(ui, repository, files):
    root = Path(id = get_next_path_id(), repository = repository, name = '', path = '', parent = None)
    paths = [root]
    parentlist = [root]
    path_count = 1

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
            path = parentlist[-1].path
            if path:
                path = path + "/"
            path = path + remains[0]
            remains.pop(0)

            newpath = Path(id = get_next_path_id(),
                           repository = repository,
                           name = name,
                           path = path,
                           parent = parentlist[-1],
                           is_dir = True if len(remains) else False)
            paths.append(newpath)
            path_count = path_count + 1

            if len(paths) >= BATCH_SIZE:
                Path.objects.bulk_create(paths)
                paths = []

            if len(remains):
                parentlist.append(newpath)

        pos = pos + 1

    if len(paths):
        Path.objects.bulk_create(paths)

    ui.progress("indexing files", None)
    ui.status("added %d files to database\n" % path_count)

def get_path(repository, path, is_dir = False):
    try:
        return Path.objects.get(repository = repository, path = path)
    except Path.DoesNotExist:
        parts = path.rsplit("/", 1)
        parent = get_path(repository, parts[0] if len(parts) > 1 else '', True)
        result = Path(id = get_next_path_id(), repository = repository, path = path, name = parts[-1], parent = parent, is_dir = is_dir)
        result.save()
        return result

def get_author(author):
    result, created = Author.objects.get_or_create(author = unicode(author, encoding))
    return result

def add_changesets(ui, repo, repository, rev, tip):
    changeset_count = 0
    changes = []
    change_count = 0

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
                              author = get_author(changectx.user()),
                              date = date,
                              tz = -changectx.date()[1] / 60,
                              description = unicode(changectx.description(), encoding))
        changeset.save()

        parents = changectx.parents()

        added = False
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

            added = True
            changes.append(Change(changeset = changeset, path = path, type = type))
            change_count = change_count + 1

            if len(changes) >= BATCH_SIZE:
                Change.objects.bulk_create(changes)
                changes = []

        if not added:
            changeset.delete()
        else:
            changeset_count = changeset_count + 1

    if len(changes):
        Change.objects.bulk_create(changes)

    ui.progress("indexing changesets", None)
    ui.status("added %d changesets with changes to %d files to database\n" % (changeset_count, change_count))

@transaction.commit_on_success
def hook(ui, repo, node, **kwargs):
    max_changesets = int(ui.config("hgchangefeed", "changesets", default = DEFAULT_CHANGESETS))

    url = ui.config("hgchangefeed", "url", default = kwargs["url"])
    tip = repo.changectx("tip")

    try:
        repository = Repository.objects.get(url = url)

        # Existing repository, only add new changesets
        # All changesets from node to "tip" inclusive are part of this push.
        rev = max(tip.rev() - max_changesets, repo.changectx(node).rev())
        add_changesets(ui, repo, repository, rev, tip.rev())

        oldsets = Changeset.objects.all()[max_changesets:]
        pos = 0
        for changeset in oldsets:
            ui.progress("expiring changesets", pos, changectx.hex(), total = len(oldsets))
            changeset.delete()
            pos = pos + 1
        ui.progress("expiring changesets", None)
        if len(oldsets) > 0:
            ui.status("expired %d changesets from database\n" % len(oldsets))

    except Repository.DoesNotExist:
        name = ui.config("hgchangefeed", "name")

        if name is None:
            stripped = url
            if url[-1] == "/":
                stripped = url[:-1]
            name = stripped.split("/")[-1]

        repository = Repository(url = url, name = name)
        repository.save()

        add_paths(ui, repository, [f for f in tip])

        # New repository, attempt to add the maximum number of changesets
        rev = tip.rev() + 1 - max_changesets
        add_changesets(ui, repo, repository, rev, tip.rev())

    return False
