# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from website.models import *
from website.management.cli import UI
from website.management.http import HttpQueue
from website.management.repo import fetch_pushes

from optparse import make_option
import re

DEFAULT_RANGE = 604800

@transaction.commit_on_success()
def add_paths(ui, repository):
    root = repository.root

    pushes = fetch_pushes(repository.url)
    cset = pushes[-1]['changesets'][-1]

    queue = HttpQueue()
    queue.fetch("%sfile/%s/?style=raw" % (repository.url, cset), [root])

    totalpaths = 1
    complete = 0
    added = 0
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
                    added = added + 1

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
        ui.status("added %d paths\n" % added)

class Command(BaseCommand):
    help = "Add a new repository."
    args = "name url"

    option_list = BaseCommand.option_list + (
        make_option("--range",
            dest = "range",
            default = DEFAULT_RANGE,
            help = "The range of changesets to keep."
        ),
        make_option("--related",
            dest = "related",
            default = None,
            help = "The name of a related repository to load the file structure from."
        ),
    )

    def handle(self, *args, **kwargs):
        ui = UI(self.stdout, self.stderr, kwargs["verbosity"])

        if len(args) != 2:
            raise CommandError("You must provide a name and url for the repository.")
        (name, url) = args

        try:
            repository = Repository.objects.get(name = name)
        except Repository.DoesNotExist:
            url = url
            if url[-1] != '/':
                url = url + '/'
            repository = Repository(url = url, name = name, range = kwargs["range"])
            repository.save()

        if kwargs["related"]:
            try:
                related = Repository.objects.get(name = kwargs["related"])

                paths = Path.objects.filter(repositories = related)
                CHUNK = 500
                count = 0
                while count < len(paths):
                    ui.progress("copying paths", count, len(paths))
                    items = paths[count:count + CHUNK]
                    repository.paths.add(*items)
                    count = count + len(items)
                ui.progress("copying paths")
                return
            except Repository.DoesNotExist:
                ui.warn("Unknown repository %s, loading file structure from source\n" % args["related"])

        add_paths(ui, repository)
