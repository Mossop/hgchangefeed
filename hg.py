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
from mercurial import hg
from mercurial import error
import mercurial.ui

from django.db import transaction
from django.utils.tzinfo import FixedOffset

from website.models import *

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
    descendants = []
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
            change = Change(id = get_next_change_id(), changeset = changeset, path = path, type = type)
            changes.append(change)
            change_count = change_count + 1

            depth = 0
            while path is not None:
                descendants.append(DescendantChange(change = change, path = path, depth = depth))
                path = path.parent
                depth = depth + 1

            if len(changes) >= BATCH_SIZE:
                Change.objects.bulk_create(changes)
                DescendantChange.objects.bulk_create(descendants)
                changes = []
                descendants = []

        if not added:
            changeset.delete()
        else:
            changeset_count = changeset_count + 1

    Change.objects.bulk_create(changes)
    DescendantChange.objects.bulk_create(descendants)

    ui.progress("indexing changesets", None)
    ui.status("added %d changesets with changes to %d files to database\n" % (changeset_count, change_count))

def get_config(ui, repo, url = None):
    config = {}
    config["max_changesets"] = int(ui.config("hgchangefeed", "changesets", default = DEFAULT_CHANGESETS))
    config["url"] = ui.config("hgchangefeed", "url", default = url)
    config["name"] = ui.config("hgchangefeed", "name")

    if config["name"] is None:
        config["name"] = os.path.basename(repo.root)

    return config

def add_repository(ui, repo, config):
    repository = Repository(localpath = repo.root, url = config["url"], name = config["name"])
    repository.save()

    tip = repo.changectx("tip")
    add_paths(ui, repository, [f for f in tip])

    # New repository, attempt to add the maximum number of changesets
    rev = tip.rev() + 1 - config["max_changesets"]
    add_changesets(ui, repo, repository, rev, tip.rev())

@transaction.commit_on_success
def pretxnchangegroup(ui, repo, node, **kwargs):
    config = get_config(ui, repo, kwargs["url"])

    try:
        repository = Repository.objects.get(localpath = repo.root)
        if repository.url is None and config["url"] is not None:
            repository.url = config["url"]
            repository.save()

        # Existing repository, only add new changesets
        # All changesets from node to "tip" inclusive are part of this push.
        tip = repo.changectx("tip")
        rev = max(tip.rev() - config["max_changesets"], repo.changectx(node).rev())
        add_changesets(ui, repo, repository, rev, tip.rev())

        oldsets = Changeset.objects.all()[config["max_changesets"]:]
        pos = 0
        for changeset in oldsets:
            ui.progress("expiring changesets", pos, changectx.hex(), total = len(oldsets))
            changeset.delete()
            pos = pos + 1
        ui.progress("expiring changesets", None)
        if len(oldsets) > 0:
            ui.status("expired %d changesets from database\n" % len(oldsets))

    except Repository.DoesNotExist:
        add_repository(ui, repo, config)

    return False

@transaction.commit_on_success
def init(ui, repo, config, args):
    try:
        repository = Repository.objects.get(localpath = repo.root)
        raise Exception("Repository already exists in the database")
    except Repository.DoesNotExist:
        add_repository(ui, repo, config)

@transaction.commit_on_success
def reset(ui, repo, config, args):
    try:
        delete(ui, repo, config, args)
        init(ui, repo, config, args)
    except Repository.DoesNotExist:
        raise Exception("Repository doesn't exist in the database")

@transaction.commit_on_success
def delete(ui, repo, config, args):
    try:
        repository = Repository.objects.get(localpath = repo.root)

        from django.conf import settings
        if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
            ui.status("Using slow deletion path due to django ticket 16426\n")
            count = 0
            changesets = Changeset.objects.filter(repository = repository)
            for c in changesets:
                ui.progress("deleting changesets", count, c.hex, total = len(changesets))
                c.delete()
                count = count + 1
            ui.progress("deleting changesets", None)
            ui.status("deleted changesets\n")

            count = 0
            paths = [p for p in reversed(sorted(Path.objects.filter(repository = repository)))]
            for p in paths:
                ui.progress("deleting paths", count, p, total = len(paths))
                p.delete()
                count = count + 1
            ui.progress("deleting paths", None)
            ui.status("deleted paths\n")

        repository.delete()
        ui.status("deleted repository\n")

    except Repository.DoesNotExist:
        raise Exception("Repository doesn't exist in the database")

def cmdline():
    import argparse

    ui = mercurial.ui.ui()
    try:
        repo = hg.repository(ui, os.getcwd())
        ui = repo.ui

        parser = argparse.ArgumentParser(description='Bootstrap hgchangefeed database for a mercurial repository.')
        parser.add_argument("command", metavar = "cmd", type = str, choices = ["init", "reset", "delete"],
                            help = "Command to run (init|reset|delete)")
        args = parser.parse_args()
        config = get_config(ui, repo)

        if args.command == "init":
            init(ui, repo, config, args)
        elif args.command == "reset":
            reset(ui, repo, config, args)
        elif args.command == "delete":
            delete(ui, repo, config, args)

    except error.RepoError:
        ui.warn("%s is not a mercurial repository.\n" % os.getcwd())

if __name__ == "__main__":
    cmdline()
