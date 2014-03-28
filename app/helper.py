import colors
import sys, traceback

try:
    DEBUG
except NameError:
    # default to show DEBUG messages
    DEBUG = True
    #DEBUG = False

def info(*msg):
    msg = map(str, msg)
    print colors.bold(colors.green('INFO')), ' '.join(msg)

def err(*msg):
    msg = map(str, msg)
    print colors.bold(colors.red('ERROR')), ' '.join(msg)

def debug(*msg):
    if DEBUG:
        msg = map(str, msg)
        print colors.bold(colors.blue('DEBUG')), ' '.join(msg)

def warn(*msg):
    msg = map(str, msg)
    print colors.bold(colors.yellow('WARNING')), ' '.join(msg)

def print_traceback():
    t, v, tb = sys.exc_info()
    traceback.print_exception(t, v, tb)


def wrap_get_set_view(func):
    def wrap(self, *args, **kwargs):
        view, roll = self.get_view()
        r = func(self, *args, **kwargs)
        self.set_view(view, roll)
        return r
    return wrap
