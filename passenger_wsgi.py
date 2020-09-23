import os
import sys

INTERP = os.path.dirname(os.path.realpath(__file__)) + "/venv/bin/python"
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# these imports need to happen after changing the interpreter
from dw_quote.bot import dp  # noqa
from dw_quote.web import app as application  # noqa


application.config["dispatcher"] = dp
