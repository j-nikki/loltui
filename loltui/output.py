import os

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

_outbuf = []

def out_init():
    os.system('clear')

def out(*args):
    _outbuf.append('\t'.join(map(str, args)))
    print(_outbuf[-1])

def out_sz() -> int:
    return len(_outbuf)

def out_rm(n: int = 1):
    del _outbuf[-n:]
    os.system('clear')
    if _outbuf:
        print('\n'.join(_outbuf))

#
# Columned table
#

def aligned(l: list[str]):
    idx = [x.find('\0') for x in l]
    if (m := max(idx, default=-1)) == -1:
        return l
    for i, j in enumerate(idx):
        if j != -1:
            l[i] = f'{l[i][:j]}{" "*(m - j)}{l[i][j+1:]}'
    return aligned(l)

# https://en.wikipedia.org/wiki/Box-drawing_character
def box(*l, post=lambda i, x: x, min_width=40, title=None):
    l = aligned([str(x).rstrip() for x in l])
    title = f'╼{title}╾' if title else ""
    w = max((min_width, len(title), *map(len, l)))
    res = cgray(f'╭{title}{"─"*(w-len(title) +2)}╮')
    for i, ln in enumerate(l):
        res = f'{res}\n{cgray("│ ")}{post(i, ln)}{" "*(w-len(ln))} {cgray("│")}'
    out(f'{res}\n{cgray("╰"+"─"*(w+2)+"╯")}')
