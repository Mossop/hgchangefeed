# HG Change Feed #

This is a simple mercurial hook and django app for display changesets that
affected directories in mecurial repositories.

# Requirements #

* Mercurial, maybe 2.5
* Django 1.5
* Python 2.7

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

## Repositories ##

Clone a mercurial repository somewhere. You can just skip to the end and install
the hook and let the first pull initialise the repository in the database but
since that will have to import a lot of changesets I do it this way.

The `hg.py` script can be called from the command line. Use it to initialise the
repository in the database. Make sure that you run it in the virtualenv that has
both mercurial and django installed.

    hg.py init --url=https://hg.mozilla.org/mozilla-central/ init

You can also skip the url argument since the first pull will set that correctly.
It will default to naming the repository after the directory it is in. You can
override that with the name command line argument. You can also set the name and
the number of changesets to cache in the repositories hgrc:

    [hgchangefeed]
    name = Mozilla Central
    maxchangesets = 2000

Then have the script update the database with the most recent changesets
(defaults to 1000):

    hg.py update

This may take a while. Like a long while. Sorry.

You should be able to view the repository and changes in the website now. To
make it update the database whenever you pull new changes simply install hg.py
as a hook in the repository's hgrc:

    [hooks]
    pretxnchangegroup = python:../path/to/website/hg.py:pretxnchangegroup

The hook (and other parts of the script) attempt to use transactions sanely to
commit complete changesets, but if anything fails the database may not have all
of the recent changesets in it. Running `hg.py update` should fix that (correctly
skipping over changesets the database already knows about).
