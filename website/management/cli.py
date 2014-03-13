import sys

class UI(object):
    def __init__(self, stdout, stderr, verbosity):
        self.stdout = stdout
        self.stderr = stderr
        self.verbosity = verbosity
        self.width = 78

    def output(self, stream, str):
        try:
            pos = str.index("\n")
            line1 = str[0:pos]
            rest = str[pos:]
            self.output(stream, line1)
            stream.write(rest, ending = '')
        except ValueError:
            stream.write("\r%s%s" % (str, ' ' * (self.width - len(str))), ending = '')

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

    def traceback(self):
        import traceback
        (type, value, tb) = sys.exc_info()
        self.warn("%s: %s\n" % (type.__name__, value))
        self.warn("".join(traceback.format_tb(tb)))

    def warn(self, str):
        self.output(self.stderr, str)

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
