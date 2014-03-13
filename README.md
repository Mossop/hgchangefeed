# HG Change Feed #

This is a django app for display changesets that affected directories in
mecurial repositories. It is made up of two pieces. A set of management commands
for building the database of changes. These must be run periodically to keep
up to date with changes in the repository. Then there is the website itself
to display them.

# Setup #

Clone this reporitory and update the submodules. Create a python virtualenv and
pip install -r requirements.txt.

If you want a custom database create a config.ini file that looks like this:

    [general]
    database=mysql://<username>:<password>@<host>/<database>

Otherwise a sqlite3 database is created.

    ./manage.py syncdb
    ./manage.py collectstatic
    ./manage.py runserver

## Managing Repositories ##

The management comments can be called from the command line to set up
repositories to track. Make sure that you run it in the virtualenv.

There are four commands:

`initrepo` is used to register a new repository to track. It will download the
file structure of the repository which can take a while.

`updaterepo` will add new changesets to the database. The first time you run it
it will download a weeks worth of data, this range can be configured when
running the `init` command. After that it will download any new changesets and
remove any old ones.

`deleterepo` will delete the repository from the database.

`updateall` will run `update` for every repository. This command is designed to
be run regularly to keep all the repositories up to date. You can also pass
--hidden to only update repositories that have never been updated before or
--visible to only update repositories that have been updated before. The latter
is recommended for cron jobs.

You run the commands from the virtualenv command line:

    ./manage.py initrepo mozilla-central https://hg.mozilla.org/mozilla-central
