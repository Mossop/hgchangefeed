# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import re
from datetime import datetime, timedelta
from urllib import urlencode

from pytz import timezone, utc

from django.db.models import Max
from django.db import transaction

from base.utils import config

from website.models import *
from website.management.http import http_fetch
from website.management.patch import Patch

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

def get_path(repository, path, is_dir = False):
    names = path.split("/")
    paths = [repository.root]
    while len(names) > 0:
        try:
            paths.append(Path.objects.get(parent = paths[-1], name = names[0]))
            names = names[1:]
        except Path.DoesNotExist:
            break

    if len(names):
        newpaths = []
        ancestors = []
        while len(names) > 0:
            is_dir = is_dir if len(names) == 1 else True
            path = Path(id = Path.next_id(), name = names[0], parent = paths[-1], is_dir = is_dir)
            names = names[1:]
            newpaths.append(path)

            depth = len(paths)
            for ancestor in paths:
                ancestors.append(Ancestor(path = path, ancestor = ancestor, depth = depth))
                depth = depth - 1
            ancestors.append(Ancestor(path = path, ancestor = path, depth = 0))

            paths.append(path)

        Path.objects.bulk_create(newpaths)
        Ancestor.objects.bulk_create(ancestors)

    repository.paths.add(*paths)

    return paths[-1]

def merge_changes(a, b):
    # If both sides have the same change then the merge introduced it
    if a == b:
        return a
    # If either side of the merge has no change then the merge introduced no changes
    if a is None or b is None:
        return None
    # If the changes differ then a modification has been made in the merge
    return "M"

@transaction.commit_manually()
def add_pushes(ui, repository, pushes):
    if len(pushes) == 0:
        ui.status("no new changesets to index\n")
        return

    changeset_count = reduce(lambda s, p: s + len(p['changesets']), pushes, 0)
    complete = 0
    added = 0
    ui.progress("indexing changesets", complete, changeset_count)

    ignore = []
    if config.has_option("hgchangefeed", "ignore"):
        ignore = config.get("hgchangefeed", "ignore").split(",")

    try:
        for pushdata in pushes:
            push = Push(push_id = pushdata['id'], repository = repository, user = pushdata['user'], date = pushdata['date'])
            push.save()

            changes = []
            index = 0
            for cset in pushdata['changesets']:
                if cset[0:12] in ignore:
                    ui.warn("Ignoring changeset %s" % cset)
                    continue
                try:
                    try:
                        changeset = Changeset.objects.get(hex = cset)
                    except Changeset.DoesNotExist:
                        url = "%sraw-rev/%s" % (repository.url, cset)
                        patches = [Patch(http_fetch(url).split("\n"))]

                        for parent in patches[0].parents[1:]:
                            url = "%sraw-rev/%s:%s" % (repository.url, parent, cset)
                            patches.append(Patch(http_fetch(url).split("\n")))

                        allfiles = set()

                        for patch in patches:
                            if patch.hex != cset:
                                raise Exception("Saw unexpected changeset %s, expecting %s" % (patch.hex, cset))
                            allfiles.update(patch.files.keys())

                        changeset = Changeset(hex = patches[0].hex,
                                              author = patches[0].user,
                                              date = patches[0].date,
                                              tzoffset = patches[0].tzoffset,
                                              description = patches[0].description)
                        changeset.save()
                        added = added + 1

                        for parent in patches[0].parents:
                            cp = ChangesetParent(changeset = changeset, parenthex = parent)
                            cp.save()

                        for file in allfiles:
                            changetypes = [p.files.get(file, None) for p in patches]
                            changetype = reduce(merge_changes, changetypes)

                            if changetype is None:
                                continue

                            path = get_path(repository, file)
                            change = Change(id = Change.next_id(), changeset = changeset, path = path, type = changetype)
                            changes.append(change)

                    pc = PushChangeset(push = push, changeset = changeset, index = index)
                    pc.save()
                    index = index + 1

                    complete = complete + 1
                    ui.progress("indexing changesets", complete, changeset_count)

                except:
                    ui.warn("failed indexing changeset %s\n" % cset)
                    raise

            Change.objects.bulk_create(changes)
            transaction.commit()
    except:
        ui.traceback()
        transaction.rollback()
    finally:
        ui.progress("indexing changesets")
        ui.status("added %d changesets\n" % added)

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
