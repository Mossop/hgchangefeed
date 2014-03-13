# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand
from django.core.cache import cache

from website.management.command import UICommand

class Command(UICommand):
    def handle(self, *args, **kwargs):
        cache.clear()
        self.status('Cleared cache\n')
