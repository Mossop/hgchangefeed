import sys

class UI(object):
    quiet = False

    def __init__(self):
        if not sys.stdout.isatty():
            self.quiet = True
        self.width = 78

    def output(self, stream, str):
        try:
            pos = str.index("\n")
            line1 = str[0:pos]
            rest = str[pos]
            self.output(stream, line1)
            stream.write(rest)
        except ValueError:
            stream.write("\r%s%s" % (str, ' ' * (self.width - len(str))))

    def status(self, str):
        if self.quiet:
            return

        self.output(sys.stdout, str)

    def warn(self, str):
        self.output(sys.stderr, str)

    def progress(self, str, pos = None, total = None):
        if self.quiet:
            return

        if pos is not None:
            if total:
                self.output(sys.stdout, "%s: %d/%d" % (str, pos, total))
            else:
                self.output(sys.stdout, "%s: %d" % (str, pos))
        else:
            self.output(sys.stdout, "%s: complete\n" % str)
