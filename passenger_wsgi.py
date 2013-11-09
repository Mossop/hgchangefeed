import sys, os

sys.path.append(os.getcwd())

from base.utils import path

INTERP = path('bin', 'python')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

from base.wsgi import application
