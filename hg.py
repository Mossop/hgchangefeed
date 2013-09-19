#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

DEFAULT_RANGE = 604800
BATCH_SIZE = 500

from mercurial import demandimport;
demandimport.disable()

import os
import sys

project = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if project not in sys.path:
    sys.path.insert(0, project)
os.environ['DJANGO_SETTINGS_MODULE'] = 'hgchangefeed.settings'

from datetime import datetime, timedelta
import re
import json
from urllib import urlencode

from mercurial.encoding import encoding
from mercurial import hg
from mercurial import error
import mercurial.ui

from django.db import transaction
from django.db.models import Max
from django.utils.tzinfo import FixedOffset

from pytz import timezone, utc

from website.models import *
from website.http import OrderedHttpQueue, HttpQueue, http_fetch
from website.cli import UI
from website.patch import Patch

def utc_datetime(timestamp):
    return datetime.fromtimestamp(timestamp, utc)

def fetch_pushes(url, start = None):
    url = "%sjson-pushes" % url

    if start:
        query = dict()
        if 'date' in start:
            date = start['date'].astimezone(timezone('America/Los_Angeles'))
            query['startdate'] = date.strftime("%Y-%m-%d %H:%M:%S")
        elif 'changeset' in start:
            query['fromchange'] = start['changeset']
        elif 'id' in start:
            query['startID'] = start['id']
        url = url + '?' + urlencode(query)

    results = json.loads(http_fetch(url))
    ids = [int(k) for k in results.keys()]
    ids.sort()
    pushes = [dict(results[str(id)], id = id, date = utc_datetime(results[str(id)]['date'])) for id in ids]
    return pushes

def add_paths(ui, repository):
    def create_ancestors(ancestors, parentlist, path):
        depth = len(parentlist)
        for ancestor in parentlist:
            ancestors.append(Ancestor(path = path, ancestor = ancestor, depth = depth))
            depth = depth - 1
        ancestors.append(Ancestor(path = path, ancestor = path, depth = depth))

    paths = []
    ancestors = []

    pushes = fetch_pushes(repository.url)
    cset = pushes[-1]['changesets'][-1]

    queue = HttpQueue()
    queue.fetch("%sfile/%s/?style=raw" % (repository.url, cset), ('', []))

    totalpaths = 1
    complete = 0
    ui.progress("indexing paths", complete, totalpaths)

    (response, context) = queue.next()
    while response:
        (path, parentlist) = context
        name = path.split('/')[-1]
        parent = None
        if len(parentlist) > 0:
            parent = parentlist[-1]

        directory = Path(id = Path.next_id(), repository = repository,
                         name = name, path = path, parent = parent, is_dir = True)
        paths.append(directory)
        create_ancestors(ancestors, parentlist, directory)

        if path:
            path = path + '/'

        for line in response.split("\n"):
            line = line.strip()
            if len(line) == 0:
                continue
            matches = re.match('(d)(?:[r-][w-][x-]){3} (.*)|-(?:[r-][w-][x-]){3} (?:\d+) (.*)', line)
            if not matches:
                raise Exception("Unable to parse directory entry '%s'" % line)

            if matches.group(1) == 'd':
                name = matches.group(2)
                newlist = list(parentlist)
                newlist.append(directory)
                queue.fetch("%sfile/%s/%s/?style=raw" % (repository.url, cset, path + name), (path + name, newlist))
                totalpaths = totalpaths + 1
            else:
                name = matches.group(3)
                file = Path(id = Path.next_id(), repository = repository,
                            name = name, path = path + name,
                            parent = directory, is_dir = False)
                paths.append(file)
                create_ancestors(ancestors, parentlist, file)

        if len(paths) + len(ancestors) >= BATCH_SIZE:
            Path.objects.bulk_create(paths)
            Ancestor.objects.bulk_create(ancestors)
            paths = []
            ancestors = []

        complete = complete + 1
        ui.progress("indexing paths", complete, totalpaths)
        (response, context) = queue.next()

    Path.objects.bulk_create(paths)
    Ancestor.objects.bulk_create(ancestors)
    ui.progress("indexing paths")

def get_path(repository, path, is_dir = False):
    try:
        return Path.objects.get(repository = repository, path = path)
    except Path.DoesNotExist:
        parts = path.rsplit("/", 1)
        parent = get_path(repository, parts[0] if len(parts) > 1 else '', True)
        result = Path(id = Path.next_id(), repository = repository, path = path, name = parts[-1], parent = parent, is_dir = is_dir)
        result.save()

        ancestor = Ancestor(path = result, ancestor = result, depth = 0)
        ancestor.save()

        depth = 1
        while parent is not None:
            ancestor = Ancestor(path = result, ancestor = parent, depth = depth)
            ancestor.save()
            parent = parent.parent
            depth = depth + 1

        transaction.commit()
        return result

@transaction.commit_manually()
def add_pushes(ui, repository, pushes):
    if len(pushes) == 0:
        ui.status("no new changesets to index\n")
        return

    queue = OrderedHttpQueue()
    changeset_count = 0

    for push in pushes:
        changeset_count = changeset_count + len(push['changesets'])
        for changeset in push['changesets']:
            queue.fetch("%sraw-rev/%s" % (repository.url, changeset), changeset)

    complete = 0
    ui.progress("indexing changesets", complete, changeset_count)

    for push in pushes:
        changesets = []
        changes = []
        for cset in push['changesets']:
            try:
                (text, hex) = queue.next()
                if hex != cset:
                    raise Exception("Saw unexpected changeset %s, expecting %s" % (hex, cset))

                patches = [Patch(text.split("\n"))]
                for parent in patches[0].parents[1:]:
                    url = "%sraw-rev/%s:%s" % (repository.url, parent, cset)
                    patches.append(Patch(http_fetch(url).split("\n")))

                allfiles = set()

                for patch in patches:
                    if patch.hex != cset:
                        raise Exception("Saw unexpected changeset %s, expecting %s" % (patch.hex, cset))
                    allfiles.update(patch.files.keys())

                changeset = Changeset(Changeset.next_id(),
                                      repository = repository,
                                      hex = patches[0].hex,
                                      author = patches[0].user,
                                      date = patches[0].date,
                                      tzoffset = patches[0].tzoffset,
                                      push_user = push['user'],
                                      push_date = push['date'],
                                      push_id = push['id'],
                                      description = patches[0].description)

                added = False
                for file in allfiles:
                    changetype = ''
                    for patch in patches:
                        # No change against one parent means the change happened
                        # in an earlier changeset
                        if not file in patch.files:
                            changetype = "X"
                            break

                        patchchange = patch.files[file]
                        if not changetype:
                            changetype = patchchange
                        elif patchchange == "M":
                            changetype = patchchange

                    if changetype == "X":
                        continue

                    if not added:
                        added = True
                        changesets.append(changeset)

                    path = get_path(repository, file)
                    change = Change(id = Change.next_id(), changeset = changeset, path = path, type = changetype)
                    changes.append(change)

                complete = complete + 1
                ui.progress("indexing changesets", complete, changeset_count)

            except:
                transaction.rollback()
                ui.warn("failed indexing changeset %s\n" % cset)
                raise

        Changeset.objects.bulk_create(changesets)
        Change.objects.bulk_create(changes)
        transaction.commit()

    ui.progress("indexing changesets")

def expire_changesets(ui, repository):
    oldest = datetime.now(utc) - timedelta(seconds = repository.range)
    oldsets = Changeset.objects.filter(repository = repository, push_date__lt = oldest)
    pos = 0
    for changeset in oldsets:
        ui.progress("expiring changesets", pos, total = len(oldsets))
        changeset.delete()
        pos = pos + 1
    ui.progress("expiring changesets", None)

@transaction.commit_on_success()
def init(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)
        raise Exception("Repository already exists in the database")
    except Repository.DoesNotExist:
        url = args.url
        if url[-1] != '/':
            url = url + '/'
        repository = Repository(url = url, name = args.name, range = args.range)
        repository.save()

        add_paths(ui, repository)

def update(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)

        start = dict()
        last_push = Changeset.objects.filter(repository = repository).aggregate(Max("push_id"))["push_id__max"]
        if last_push:
            start['id'] = last_push
        else:
            start['date'] = datetime.now(utc) - timedelta(seconds = repository.range)

        pushes = fetch_pushes(repository.url, start)
        add_pushes(ui, repository, pushes)
        expire_changesets(ui, repository)

        repository.hidden = False
        repository.save()
    except Repository.DoesNotExist:
        raise Exception("Repository doesn't exist in the database")

@transaction.commit_manually()
def delete(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)

        from django.conf import settings
        count = 0
        changesets = Changeset.objects.filter(repository = repository)
        for c in changesets:
            ui.progress("deleting changesets", count, total = len(changesets))
            c.delete()
            count = count + 1
        transaction.commit()
        ui.progress("deleting changesets")

        if args.onlychangesets:
            return

        count = 0
        path_count = Path.objects.filter(repository = repository).count()
        remains = path_count
        while remains > 0:
            paths = Path.objects.filter(repository = repository).order_by("-path")[:BATCH_SIZE]
            for p in paths:
                ui.progress("deleting paths", count, total = path_count)
                p.delete()
                count = count + 1
            transaction.commit()
            remains = Path.objects.filter(repository = repository).count()
        ui.progress("deleting paths")

        repository.delete()
        transaction.commit()
        ui.status("deleted repository\n")

    except Repository.DoesNotExist:
        raise Exception("Repository doesn't exist in the database")

def cmdline():
    import argparse

    ui = UI()

    parser = argparse.ArgumentParser(description='Manage the hgchangefeed database.')
    subparsers = parser.add_subparsers(help='Commands')

    init_parser = subparsers.add_parser('init', help='Add a new repository.')
    init_parser.set_defaults(func = init)
    init_parser.add_argument("name", type = str,
                             help = "A name for the repository.")
    init_parser.add_argument("url", type = str,
                             help = "The remote URL for the repository.")
    init_parser.add_argument("--range", dest = "range", type = int,
                             default = DEFAULT_RANGE,
                             help = "The range of changesets to keep.")

    update_parser = subparsers.add_parser('update', help='Update an existing repository.')
    update_parser.set_defaults(func = update)
    update_parser.add_argument("name", type = str,
                               help = "The name of the repository.")

    delete_parser = subparsers.add_parser('delete', help='Delete an existing repository.')
    delete_parser.set_defaults(func = delete)
    delete_parser.add_argument("name", type = str,
                               help = "The name of the repository.")
    delete_parser.add_argument("--changesets", dest = "onlychangesets", action = 'store_const',
                               const = True, default = False,
                               help = "Only delete/reset changesets.")

    args = parser.parse_args()

    args.func(ui, args)

if __name__ == "__main__":
    cmdline()
