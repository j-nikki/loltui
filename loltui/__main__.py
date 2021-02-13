import argparse
import time
from itertools import chain
from typing import Callable, Iterable

#
# Process args
#

ap = argparse.ArgumentParser(
    description="gives info about the players you're playing with")
ap.add_argument('--demo', '-d', type=argparse.FileType('r', encoding='U8'),
                help='supply the program with JSON file where ["myTeam"] = [{"summonerId":<id>, "championId":<id>}...]')
ap.add_argument('--exe', action='store_true',
                help='compile loltui to an executable')
args = ap.parse_args()

if args.exe:
    from loltui import exe

#
# Client interfacing
#

if True:
    from loltui.client import client
    from loltui.playerinfo import *
    from loltui.session import *

#
# Demo
#

if args.demo:
    with args.demo as f:
        d, q = json.load(f), 'Demo'
    cids = [x['championId'] for x in d['myTeam']]
    ses = Session(q, (5, 0), [x['summonerId'] for x in d['myTeam']])
    ses.loop(lambda: cids, 1)
    exit(0)

#
# Main loop
#

try:
    while True:
        sys.stdout.write(
            f'waiting for session, press {ctell("Ctrl+C")} to abort\r')
        ses = get_session(1)
        sys.stdout.write('\033[J')
        ses.loop(1)
except KeyboardInterrupt:
    pass
