import sys
from typing import Iterable

#
# Colored output
#

# https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
def colorizer(code: int):
    return lambda x: '\033[38;5;' + str(code) + 'm' + str(x) + '\033[0m'
cyell = colorizer(129)
ctell = colorizer(214)
cgray = colorizer(239)

#
# Mutable display output
#

_buf = []
_w = sys.stdout.write
CSI, LF = '\033[', '\n'

def out_init():
    pass

def out(x: Iterable[str]):
    start = len(_buf)
    _buf.extend([x] if isinstance(x, str) else x)
    _w(f'{LF.join(_buf[start:])}{LF}')

def out_sz() -> int:
    return len(_buf)

# https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
def out_rm(n: int = 1):
    assert n > 0
    del _buf[-n:]
    _w(f'{CSI}{n}A{CSI}J{LF.join(_buf)}')

#
# Columned table
#

def _aligned(l: list[str]):
    idx = [x.find('\0') for x in l]
    if (m := max(idx, default=-1)) == -1:
        return l
    for i, j in enumerate(idx):
        if j != -1:
            l[i] = f'{l[i][:j]}{" "*(m - j)}{l[i][j+1:]}'
    return _aligned(l)

# https://en.wikipedia.org/wiki/Box-drawing_character
def box(*l, post=lambda i, x: x, title=None):
    l = _aligned([str(x).rstrip() for x in l])
    title = f'╼{title}╾' if title else ""
    w = max((len(title), *map(len, l)))
    out([
        cgray(f'╭{title}{"─"*(w-len(title) +2)}╮'),
        *[f'{cgray("│ ")}{post(i, ln)}{" "*(w-len(ln))} {cgray("│")}' for i,
          ln in enumerate(l)],
        f'{cgray("╰"+"─"*(w+2)+"╯")}'])
