#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

DEFAULT_RANGE = 604800

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

from django.db import transaction, connection
from django.db.models import Max
from django.utils.tzinfo import FixedOffset
from django.conf import settings

from pytz import timezone, utc

from website.models import *
from website.http import OrderedHttpQueue, HttpQueue, http_fetch
from website.cli import UI
from website.patch import Patch

DATABASE_ENGINE = settings.DATABASES['default']['ENGINE']

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

@transaction.commit_manually()
def add_paths(ui, repository):
    root = repository.root

    pushes = fetch_pushes(repository.url)
    cset = pushes[-1]['changesets'][-1]

    queue = HttpQueue()
    queue.fetch("%sfile/%s/?style=raw" % (repository.url, cset), [root])

    totalpaths = 1
    complete = 0
    ui.progress("indexing paths", complete, totalpaths)

    try:
        (response, parentlist) = queue.next()
        while response:
            directory = parentlist[-1]
            paths = Path.objects.filter(parent = directory)
            contents = { p.name: p for p in paths}

            for line in response.split("\n"):
                line = line.strip()
                if len(line) == 0:
                    continue
                matches = re.match('(d)(?:[r-][w-][x-]){3} (.*)|-(?:[r-][w-][x-]){3} (?:\d+) (.*)', line)
                if not matches:
                    raise Exception("Unable to parse directory entry '%s'" % line)

                is_dir = matches.group(1) == 'd'
                name = matches.group(2) if is_dir else matches.group(3)

                if name in contents:
                    path = contents[name]
                else:
                    path = Path(id = Path.next_id(), name = name, parent = directory, is_dir = is_dir)
                    path.save()

                    depth = len(parentlist)
                    ancestors = []
                    for ancestor in parentlist:
                        ancestors.append(Ancestor(path = path, ancestor = ancestor, depth = depth))
                        depth = depth - 1
                    ancestors.append(Ancestor(path = path, ancestor = path, depth = 0))
                    Ancestor.objects.bulk_create(ancestors)

                path.repositories.add(repository)

                if is_dir:
                    newlist = list(parentlist)
                    newlist.append(path)
                    fullpath = "/".join([p.name for p in newlist[1:]])
                    queue.fetch("%sfile/%s/%s/?style=raw" % (repository.url, cset, fullpath), newlist)
                    totalpaths = totalpaths + 1

            complete = complete + 1
            transaction.commit()
            ui.progress("indexing paths", complete, totalpaths)
            (response, parentlist) = queue.next()

    except:
        ui.traceback()
        transaction.rollback()
    finally:
        ui.progress("indexing paths")

def get_path(repository, path, is_dir = False):
    try:
        path = Path.get_by_path(path = path)
        paths = path.parentlist()
        paths.append(path)
        repository.paths.add(*paths)
        return path
    except Path.DoesNotExist:
        print("Creating %s" % path)
        parts = path.rsplit("/", 1)
        parent = get_path(repository, parts[0] if len(parts) > 1 else '', True)
        result = Path(id = Path.next_id(), path = path, name = parts[-1], parent = parent, is_dir = is_dir)
        result.save()
        result.repositories.add(repository)

        ancestor = Ancestor(path = result, ancestor = result, depth = 0)
        ancestor.save()

        depth = 1
        for parent in result.parentlist():
            ancestor = Ancestor(path = result, ancestor = parent, depth = depth)
            ancestor.save()
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

    try:
        for pushdata in pushes:
            push = Push(push_id = pushdata['id'], repository = repository, user = pushdata['user'], date = pushdata['date'])
            push.save()

            changes = []
            for cset in pushdata['changesets']:
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

                    try:
                        changeset = Changeset.objects.get(hex = patches[0].hex)
                        changeset.pushes.add(push)
                    except Changeset.DoesNotExist:
                        changeset = Changeset(hex = patches[0].hex,
                                              author = patches[0].user,
                                              date = patches[0].date,
                                              tzoffset = patches[0].tzoffset,
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
                                changeset.save()
                                changeset.pushes.add(push)

                            path = get_path(repository, file)
                            change = Change(id = Change.next_id(), changeset = changeset, path = path, type = changetype)
                            changes.append(change)

                    complete = complete + 1
                    ui.progress("indexing changesets", complete, changeset_count)

                except:
                    ui.warn("failed indexing changeset %s\n" % cset)
                    ui.traceback()
                    transaction.rollback()
                    raise

            Change.objects.bulk_create(changes)
            transaction.commit()
    except:
        ui.traceback()
        transaction.rollback()
    finally:
        ui.progress("indexing changesets")

def expire_changesets(ui, repository):
    oldest = datetime.now(utc) - timedelta(seconds = repository.range)

    pushes = Push.objects.filter(repository = repository, date__lt = oldest)
    ui.status("deleting %d pushes\n" % len(pushes))
    pushes.delete()

    changesets = Changeset.objects.filter(pushes__isnull = True)
    ui.status("deleting %d changesets\n" % len(changesets))
    changesets.delete()

def update_repository(ui, repository):
    start = dict()
    last_push = Push.objects.filter(repository = repository).aggregate(Max("push_id"))["push_id__max"]
    if last_push:
        start['id'] = last_push
    else:
        start['date'] = datetime.now(utc) - timedelta(seconds = repository.range)

    pushes = fetch_pushes(repository.url, start)
    add_pushes(ui, repository, pushes)
    expire_changesets(ui, repository)

def init(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)
    except Repository.DoesNotExist:
        url = args.url
        if url[-1] != '/':
            url = url + '/'
        repository = Repository(url = url, name = args.name, range = args.range)
        repository.save()

    if "related" in args:
        try:
            related = Repository.objects.get(name = args.related)

            paths = Path.objects.filter(repositories = related)
            CHUNK = 500
            count = 0
            while count < len(paths):
                ui.progress("indexing paths", count, len(paths))
                items = paths[count:count + CHUNK]
                repository.paths.add(*items)
                count = count + len(items)
            ui.progress("indexing paths")
            return
        except Repository.DoesNotExist:
            ui.warn("Unknown repository %s, loading file structure from source\n" % args.related)

    add_paths(ui, repository)

def update(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)

        update_repository(ui, repository)

        repository.hidden = False
        repository.save()
    except Repository.DoesNotExist:
        raise Exception("Repository doesn't exist in the database")

def updateall(ui, args):
    types = dict()
    if args.hidden:
        types['hidden'] = True
    elif args.visible:
        types['hidden'] = False
    repositories = Repository.objects.filter(**types)
    for repository in repositories:
        ui.status("updating %s\n" % repository.name)
        update_repository(ui, repository)

@transaction.commit_on_success()
def delete(ui, args):
    try:
        repository = Repository.objects.get(name = args.name)

        pushes = Push.objects.filter(repository = repository)
        ui.status("deleting %d pushes\n" % len(pushes))
        pushes.delete()

        changesets = Changeset.objects.filter(pushes__isnull = True)
        ui.status("deleting %d changesets\n" % len(changesets))
        changesets.delete()

        if args.onlychangesets:
            return

        repository.delete()
        ui.status("repository deleted\n")

        if DATABASE_ENGINE == 'django.db.backends.sqlite3':
            # A bug in django makes it impossible to delete a large set of objects
            # that are referenced by foreign keys, delete them one at a time for
            # safety. See https://code.djangoproject.com/ticket/16426
            path_count = Path.objects.filter(repositories__isnull = True).count()
            remains = path_count
            count = 0
            while (remains - count) > 0:
                paths = Path.objects.filter(repositories__isnull = True).order_by("-path")[:500]
                ui.progress("deleting paths", count, total = path_count)
                for path in paths:
                    path.delete()
                count = count + len(paths)
            ui.progress("deleting paths")
        else:
            paths = Path.objects.filter(repositories__isnull = True)
            ui.status("deleting %d paths\n" % len(paths))
            paths.delete()

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
    init_parser.add_argument("--related", dest = "related", type = str,
                             default = argparse.SUPPRESS,
                             help = "The name of a related repository to load the file structure from.")

    update_parser = subparsers.add_parser('update', help='Update an existing repository.')
    update_parser.set_defaults(func = update)
    update_parser.add_argument("name", type = str,
                               help = "The name of the repository.")

    updateall_parser = subparsers.add_parser('updateall', help='Updates all repositories.')
    updateall_parser.set_defaults(func = updateall)
    group = updateall_parser.add_mutually_exclusive_group()
    group.add_argument("--hidden", dest = "hidden", action = 'store_const',
                        const = True, default = False,
                        help = "Only update hidden repositories.")
    group.add_argument("--visible", dest = "visible", action = 'store_const',
                        const = True, default = False,
                        help = "Only update visible repositories.")

    delete_parser = subparsers.add_parser('delete', help='Delete an existing repository.')
    delete_parser.set_defaults(func = delete)
    delete_parser.add_argument("name", type = str,
                               help = "The name of the repository.")
    delete_parser.add_argument("--changesets", dest = "onlychangesets", action = 'store_const',
                               const = True, default = False,
                               help = "Only delete/reset changesets.")

    args = parser.parse_args()

    try:
        args.func(ui, args)
    except:
        ui.traceback()
        sys.exit(1)

if __name__ == "__main__":
    cmdline()
