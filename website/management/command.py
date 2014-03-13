# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand

WIDTH = 78

class UICommand(BaseCommand):
    def output(self, stream, str):
        try:
            pos = str.index("\n")
            line1 = str[0:pos]
            rest = str[pos:]
            self.output(stream, line1)
            stream.write(rest, ending = '')
        except ValueError:
            stream.write("\r%s%s" % (str, ' ' * (WIDTH - len(str))), ending = '')

    def status(self, str):
        if self.verbosity < 1:
            return

        self.output(self.stdout, str)

    def info(self, str):
        if self.verbosity < 2:
            return

        self.output(self.stdout, str)

    def log(self, str):
        if self.verbosity < 3:
            return

        self.output(self.stdout, str)

    def warn(self, str):
        self.output(self.stderr, str)

    def error(self, str):
        self.output(self.stderr, str)

    def traceback(self):
        import traceback
        (type, value, tb) = sys.exc_info()
        self.warn("%s: %s\n" % (type.__name__, value))
        self.warn("".join(traceback.format_tb(tb)))

    def progress(self, str, pos = None, total = None):
        if self.verbosity < 1:
            return

        if pos is not None:
            if total:
                self.output(self.stdout, "%s: %d/%d" % (str, pos, total))
            else:
                self.output(self.stdout, "%s: %d" % (str, pos))
        else:
            self.output(self.stdout, "%s: complete\n" % str)

    def execute(self, *args, **options):
        self.verbosity = options["verbosity"]
        super(UICommand, self).execute(*args, **options)
