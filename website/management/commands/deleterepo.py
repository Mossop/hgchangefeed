# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from website.models import *
from website.management.cli import UI

from optparse import make_option

DATABASE_ENGINE = settings.DATABASES['default']['ENGINE']

class Command(BaseCommand):
    help = "Delete an existing repository."
    args = "name"

    option_list = BaseCommand.option_list + (
        make_option("--changesets",
            dest = "onlychangesets",
            action = "store_true",
            default = False,
            help = "Only delete changesets."
        ),
    )

    @transaction.commit_on_success()
    def handle(self, *args, **kwargs):
        ui = UI(self.stdout, self.stderr, kwargs["verbosity"])

        if len(args) != 1:
            raise CommandError("You must provide the name for the repository.")
        name = args[0]

        try:
            repository = Repository.objects.get(name = name)

            pushes = Push.objects.filter(repository = repository)
            ui.status("deleting %d pushes\n" % len(pushes))
            pushes.delete()

            if DATABASE_ENGINE == 'django.db.backends.sqlite3':
                # A bug in django makes it impossible to delete a large set of objects
                # that are referenced by foreign keys, delete them one at a time for
                # safety. See https://code.djangoproject.com/ticket/16426
                changeset_count = Changeset.objects.filter(pushes__isnull = True).count()
                remains = changeset_count
                count = 0
                while (remains - count) > 0:
                    changesets = Changeset.objects.filter(pushes__isnull = True)[:500]
                    ui.progress("deleting changesets", count, total = changeset_count)
                    for changeset in changesets:
                        changeset.delete()
                    count = count + len(changesets)
                ui.progress("deleting changesets")
            else:
                changesets = Changeset.objects.filter(pushes__isnull = True)
                ui.status("deleting %d changesets\n" % len(changesets))
                changesets.delete()

            if kwargs["onlychangesets"]:
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
                    paths = Path.objects.filter(repositories__isnull = True).order_by("id")[:500]
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
