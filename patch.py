from datetime import datetime
from pytz import FixedOffset

def newline_stripped(i):
    for l in i:
        yield l.rstrip("\r\n")

class Patch(object):
    hex = None
    user = None
    date = None
    tzoffset = None
    parents = None
    description = None
    removed = None
    added = None
    modified = None
    files = None

    def __init__(self, lines):
        self.parents = []
        self.removed = []
        self.added = []
        self.modified = []
        self.files = dict()

        i = iter(newline_stripped(lines))

        try:
            # Skip over the intro
            line = i.next()
            while len(line) == 0:
                line = i.next()

            # Read patch headers
            while line.startswith("# "):
                args = line.split()
                if args[1] == "HG" and len(args) == 4:
                    pass
                elif args[1] == "User":
                    self.user = line[7:]
                elif args[1] == "Date" and len(args) == 4:
                    self.tzoffset = -int(args[3]) / 60
                    tz = FixedOffset(self.tzoffset)
                    self.date = datetime.fromtimestamp(int(args[2]), tz)
                elif args[1] == "Node" and args[2] == "ID" and len(args) == 4:
                    self.hex = line[10:]
                elif args[1] == "Parent": 
                    if len(args) == 3:
                        self.parents.append(args[2])
                    elif len(args) == 5 and args[3] == "Parent" and args[2].endswith("#"):
                        self.parents.append(args[2][0:-1])
                        self.parents.append(args[4])
                    else:
                        raise Exception("Malformed patch file at '%s'" % line)
                else:
                    raise Exception("Malformed patch file at '%s'" % line)

                line = i.next()

            # Read the description
            description = []
            while not line.startswith("diff --git "):
                description.append(line)
                line = i.next()
            self.description = "\n".join(description[0:-1])

            # Loop over the file changes
            while True:
                (oldfile, newfile) = line.split()[2:4]
                oldfile = oldfile[2:]
                newfile = newfile[2:]

                line = i.next()
                if line.startswith("rename from "):
                    if line != ("rename from " + oldfile):
                        raise Exception("Malformed patch file at '%s'" % line)
                    # A rename is a delete and addition
                    self.mark_removed(oldfile)
                    line = i.next()
                    if line != ("rename to " + newfile):
                        raise Exception("Malformed patch file at '%s'" % line)
                    self.mark_added(newfile)
                elif line.startswith("copy from "):
                    if line != ("copy from " + oldfile):
                        raise Exception("Malformed patch file at '%s'" % line)
                    # A copy is an addition
                    line = i.next()
                    if line != ("copy to " + newfile):
                        raise Exception("Malformed patch file at '%s'" % line)
                    self.mark_added(newfile)
                elif line.startswith("deleted file "):
                    self.mark_removed(oldfile)
                elif line.startswith("new file "):
                    self.mark_added(newfile)
                elif line.startswith("Binary file ") and line.endswith(" has changed"):
                    filename = line[12:-12]
                    if filename != newfile:
                        raise Exception("Malformed patch file at '%s'" % line)
                    self.mark_modified(newfile)
                elif line.startswith("index "):
                    line = i.next()
                    if line != "GIT binary patch":
                        raise Exception("Malformed patch file at '%s'" % line)
                    self.mark_modified(newfile)
                else:
                    if not line.startswith("--- "):
                        raise Exception("Malformed patch file at '%s'" % line)
                    oldfile = line[4:]
                    line = i.next()
                    if not line.startswith("+++ "):
                        raise Exception("Malformed patch file at '%s'" % line)
                    newfile = line[4:]

                    # /dev/null indicated empty files so either adds or removes
                    # Note stripping the a/ and b/ from the front of names
                    if oldfile == '/dev/null':
                        self.mark_added(newfile[2:])
                    elif newfile == '/dev/null':
                        self.mark_removed(oldfile[2:])
                    else:
                        self.mark_modified(newfile[2:])

                line = i.next()

                while not line.startswith("diff --git "):
                    try:
                        line = i.next()
                    except StopIteration:
                        return
        except StopIteration:
            raise Exception("Patch file ended unexpectedly")

    def mark_added(self, filename):
        self.files[filename] = "A"
        self.added.append(filename)

    def mark_removed(self, filename):
        self.files[filename] = "R"
        self.removed.append(filename)

    def mark_modified(self, filename):
        if filename in self.files:
            return

        self.files[filename] = "M"
        self.modified.append(filename)

if __name__ == "__main__":
    import sys

    patch = Patch(sys.stdin)
    print("Changeset %s against parents %s" % (patch.hex, patch.parents))
    print("By %s at %s" % (patch.user, patch.date))
    print(patch.description)
    print("")

    if len(patch.removed):
        print("Deleted files:")
        for file in patch.removed:
            print("  %s" % file)

    if len(patch.added):
        print("Added files:")
        for file in patch.added:
            print("  %s" % file)

    if len(patch.modified):
        print("Modified files:")
        for file in patch.modified:
            print("  %s" % file)
