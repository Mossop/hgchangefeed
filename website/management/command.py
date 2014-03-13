# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.management.base import BaseCommand

WIDTH = 78

def verbosity(value):
    def _verbosity(f):
        def wrapper(self, *args, **kwargs):
            if self.verbosity < value:
                return
            return f(self, *args, **kwargs)
        return wrapper
    return _verbosity

def line_output(f):
    def wrapper(self, *args, **kwargs):
        if self.inprogress:
            self.stdout.write("\n")
        result = f(self, *args, **kwargs)
        if self.inprogress:
            self.progress(*self.inprogress)
        return result
    return wrapper

class UICommand(BaseCommand):
    inprogress = None

    @verbosity(1)
    @line_output
    def status(self, str):
        self.stdout.write(str)

    @verbosity(2)
    @line_output
    def info(self, str):
        self.stdout.write(str)

    @verbosity(3)
    @line_output
    def log(self, str):
        self.stdout.write(str)

    @line_output
    def warn(self, str):
        self.stderr.write(str, self.style.ERROR)

    @line_output
    def error(self, str):
        self.stderr.write(str, self.style.ERROR)

    @line_output
    def traceback(self):
        import traceback
        (type, value, tb) = sys.exc_info()
        self.warn("%s: %s\n" % (type.__name__, value))
        self.warn("".join(traceback.format_tb(tb)))

    @verbosity(1)
    def progress(self, str, pos = None, total = None):
        if pos is not None:
            if total:
                line = "%s: %d/%d" % (str, pos, total)
            else:
                line = "%s: %d" % (str, pos)
            self.inprogress = (str, pos, total)
        else:
            line = "%s: complete" % str
            self.inprogress = None

        self.stdout.write("\r%s%s" % (line, ' ' * (WIDTH - len(line))), ending = '')
        if pos is None:
            self.stdout.write("\n")

    def execute(self, *args, **options):
        self.verbosity = int(options["verbosity"])
        try:
            super(UICommand, self).execute(*args, **options)
        finally:
            if self.inprogress:
                self.stdout.write("\n")
