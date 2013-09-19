# HG Change Feed #

This is a simple mercurial hook and django app for display changesets that
affected directories in mecurial repositories.

# Requirements #

* Mercurial, maybe 2.5
* Django 1.5
* Python 2.7
* PyTz

# Setup #

You're going to want to set up a python virtualenv and pip install mercurial,
pytz and django at the least into it. Might be others I've forgotten.

## Django project ##

Follow the django tutorial to create a basic project, then checkout this
repository as an app named "website" in it. Set your settings accordingly, I
use sqlite for local testing and mysql (with InnoDB tables) on the website. I
also disabled the auth app and middleware from settings.py. If you aren't using
runserver for testing then make sure to use `manage.py collectstatic` to set up
the static files. You should be able to load the main page and have it tell you
it doesn't know about any repositories.

## Managing Repositories ##

The `hg.py` script can be called from the command line to set up repositories to
track.  Make sure that you run it in the virtualenv that has both mercurial and
django installed.

It has four commands.

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
