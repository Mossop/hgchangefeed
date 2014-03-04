# HG Change Feed #

This is a simple mercurial hook and django app for display changesets that
affected directories in mecurial repositories.

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

The `website/hg.py` script can be called from the command line to set up
repositories to track. Make sure that you run it in the virtualenv.

It has four commands:

`init` is used to register a new repository to track. It will download the file
structure of the repository which can take a while.

`update` will add new changesets to the database. The first time you run it it
will download a weeks worth of data, this range can be configured when running
the `init` command. After that it will download any new changesets and remove
any old ones.

`delete` will delete the repository from the database.

`updateall` will run `update` for every repository. This command is designed to
be run regularly to keep all the repositories up to date. You can also pass
--hidden to only update repositories that have never been updated before or
--visible to only update repositories that have been updated before. The latter
is recommended for cron jobs
