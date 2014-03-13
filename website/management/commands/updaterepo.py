# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand, CommandError

from website.models import *
from website.management.cli import UI
from website.management.repo import update_repository

from optparse import make_option

class Command(BaseCommand):
    help = "Update an existing repository."
    args = "name"

    def handle(self, *args, **kwargs):
        ui = UI(self.stdout, self.stderr, kwargs["verbosity"])

        if len(args) != 1:
            raise CommandError("You must provide the name for the repository.")
        name = args[0]

        try:
            repository = Repository.objects.get(name = name)

            update_repository(ui, repository)

            repository.hidden = False
            repository.save()
        except Repository.DoesNotExist:
            raise Exception("Repository doesn't exist in the database")
