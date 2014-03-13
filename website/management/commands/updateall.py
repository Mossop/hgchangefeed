# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand, CommandError

from website.models import *
from website.management.command import UICommand
from website.management.repo import update_repository

from optparse import make_option

class Command(UICommand):
    help = "Updates all repositories."

    option_list = BaseCommand.option_list + (
        make_option("--hidden",
            dest = "hidden",
            action = "store_true",
            default = False,
            help = "Only update hidden repositories."
        ),
        make_option("--visible",
            dest = "visible",
            action = "store_true",
            default = False,
            help = "Only update visible repositories."
        ),
    )

    def handle(self, *args, **kwargs):
        if kwargs["visible"] and kwargs["hidden"]:
            raise CommandError("You cannot pass --hidden and --visible at the same time")

        types = dict()
        if kwargs["hidden"] != kwargs["visible"]:
            types["hidden"] = kwargs["hidden"]

        repositories = Repository.objects.filter(**types)
        for repository in repositories:
            self.status("updating %s\n" % repository.name)
            update_repository(self, repository)
