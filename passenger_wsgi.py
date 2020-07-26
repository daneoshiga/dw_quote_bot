import sys, os
INTERP = os.path.dirname(os.path.realpath(__file__)) + "/venv/bin/python"
if sys.executable != INTERP: os.execl(INTERP, INTERP, *sys.argv)

from dw_quote.bot import dp
from dw_quote.web import app as application

application.config['dispatcher'] = dp