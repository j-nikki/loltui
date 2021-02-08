import json
import os
import queue
import re
import sys
import tempfile
import threading
import time
from contextlib import suppress
from itertools import chain
from typing import Iterable, Optional
from urllib.request import urlopen

import psutil
import requests

#
# Process args
#

DEBUG = '--debug' in sys.argv

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

outbuf = []
os.system('clear')
def out(*args):
    outbuf.append('\t'.join(map(str, args)))
    print(outbuf[-1])

def out_sz() -> int:
    return len(outbuf)

def out_rm(n: int = 1):
    del outbuf[-n:]
    os.system('clear')
    if outbuf:
        print('\n'.join(outbuf))

#
# Columned table
#

def aligned(l: list[str]):
    idx = [x.find('\0') for x in l]
    m = max(0, *idx)
    for i, j in enumerate(idx):
        if j != -1:
            l[i] = f'{l[i][:j]}{" "*(m - j)}{l[i][j+1:]}'
    return m and aligned(l) or l

# https://en.wikipedia.org/wiki/Box-drawing_character
def box(*l, post=lambda i, x: x, min_width=40, title=None):
    l = aligned([str(x).rstrip() for x in l])
    w = max(min_width, *map(len, l))
    title = f'╼{title}╾' if title else ""
    res = cgray(f'╭{title}{"─"*(w-len(title) +2)}╮')
    for i, ln in enumerate(l):
        res = f'{res}\n{cgray("│ ")}{post(i, ln)}{" "*(w-len(ln))} {cgray("│")}'
    out(f'{res}\n{cgray("╰"+"─"*(w+2)+"╯")}')

#
# Client interfacing
#

class Client:
    __reg2platf = {
        "BR": "BR1",
        "UNE": "EUN1",
        "EUW": "EUW1",
        "LAN": "LA1",
        "LAS": "LA2",
        "NA": "NA1",
        "OCE": "OC1",
        "TR": "TR1",
        "JP": "JP1"}

    @staticmethod
    def __get_port_and_token() -> tuple[str, str]:
        out(f'waiting for client, press {ctell("Ctrl+C")} to abort')
        while True:
            with suppress(FileNotFoundError, StopIteration):
                proc = psutil.Process
                exe = next(proc(c.pid).exe() for c in psutil.net_connections('tcp4') if proc(
                    c.pid).name() == 'LeagueClient.exe' and c.status == 'LISTEN')
                with open(os.path.join(os.path.dirname(exe), 'lockfile'), 'r') as f:
                    _, _, port, token, _ = f.read().split(':')
                out_rm()
                return port, token
            time.sleep(2)

    def __init__(self):
        certfd, self.__cert = tempfile.mkstemp(suffix='.pem')
        os.write(certfd, urlopen(
            'https://static.developer.riotgames.com/docs/lol/riotgames.pem').read())
        os.close(certfd)

        self.__port, self.__token = self.__get_port_and_token()

        self.__reg = self.get_dict('riotclient/region-locale')['region']
        global platf
        platf = __class__.__reg2platf.get(self.__reg, self.__reg)
        out(f"using region {ctell(self.__reg)} (platform {ctell(platf)})")

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        try:
            return requests.get(f'https://127.0.0.1:{self.__port}/{endpoint}', params=kwargs, headers={
                                'Accept': 'application/json'}, auth=('riot', self.__token), verify=self.__cert)
        except Exception as e:
            out(f'{cyell(e.__class__.__name__)}: {ctell(e)}')
            exit(1)

    def get_dict(self, endpoint: str, **kwargs) -> dict:
        resp = self.get(endpoint, **kwargs)
        return {} if resp.status_code == 404 else json.loads(
            self.get(endpoint, **kwargs).content)

    def __del__(self):
        os.remove(self.__cert)

    @property
    def region(self) -> str:
        return self.__reg

client = Client()

#
# Champion data
#

vdata = json.loads(urlopen(
    f'https://ddragon.leagueoflegends.com/realms/{client.region.lower()}.json').read())['v']
out(f'game data version is {ctell(vdata)}')
champions = {int(x['key']): x for x in json.loads(urlopen(
    f'https://ddragon.leagueoflegends.com/cdn/{vdata}/data/en_US/champion.json').read())['data'].values()}

#
# Queue data
#

qdata = {x['queueId']: x for x in json.loads(urlopen(
    'https://static.developer.riotgames.com/docs/lol/queues.json').read())}

#
# Summoner data
#

def wins_losses(info) -> list[bool]:
    '''
    Gets outcome of ranked games from 20 last games
    '''
    acc = info['accountId']
    ml = client.get_dict(f'lol-match-history/v1/friend-matchlists/{acc}')
    gs = [g for g in ml['games']['games'][::-1] if g['queueId'] in (420, 440)]
    def f(g):
        pi = next(x['participantId'] for x in g['participantIdentities']
                  if x['player']['accountId'] == acc)
        return next(x['stats']['win']
                    for x in g['participants'] if x['participantId'] == pi)
    return [f(g) for g in gs]

divs = ['I', 'II', 'III', 'IV', 'V']
def id2player(sid: str) -> tuple[str, str, list]:
    '''
    Returns summoner info, rank, and masteries
    '''
    d = client.get_dict(f'lol-summoner/v1/summoners/{sid}')
    q = client.get_dict(
        f'lol-ranked/v1/ranked-stats/{d["puuid"]}')['queueMap']['RANKED_SOLO_5x5']
    rank = f'{q["tier"][0].upper()}{divs.index(q["division"])+1}' if q['division'] != 'NA' else ''
    cm = client.get_dict(
        f'lol-collections/v1/inventories/{d["summonerId"]}/champion-mastery')
    return d, rank, cm

#
# Player info presenter
#

champions[-1] = {'name': '...'}  # dummy champion (e.g. when none picked)
crank = {  # rank colorizers
    'I': colorizer(8),
    'B': colorizer(95),
    'S': colorizer(102),
    'G': colorizer(179),
    'P': colorizer(7),
    'D': colorizer(14),
    'M': colorizer(12),
    'C': colorizer(50)}
class PlayerInfo():
    __ppts = re.compile(r'\S+')

    def __wl_calc(self):
        for i, wl in enumerate(wins_losses(x[0]) for x in self.__ps):
            if wl:
                self.__q.put((i, wl))

    def __init__(self, cl: Client, summoner_ids: Iterable[str], show_fn):
        self.__ps = [id2player(x) for x in summoner_ids]
        self.__wl = [[] for _ in self.__ps]
        self.__seek = out_sz()
        self.__champs = []
        self.__show_fn = show_fn
        self.__q = queue.Queue()
        threading.Thread(target=self.__wl_calc, daemon=True).start()

    def __get(self, i: int) -> tuple[str, str]:
        T = '\0 '  # 0-terminator, used for aligning info
        info, rank, champs = self.__ps[i]
        name = info['displayName'] + '\t' + rank
        if not 0 <= (idx := self.__champidx[i]) <= 9:
            champs = champs[:8]
            champs.append({
                'championId': -1,
                'championPoints': -1})
            champs.append({
                'championId': self.__champs[i],
                'championPoints': 0 if idx == -1 else self.__ps[i][2][idx]['championPoints']})
        return f'{name}{T}│ {T.join(champions[c["championId"]]["name"] for c in champs[:10])}', \
            f'{"".join("01"[y] for y in self.__wl[i])}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in champs[:10])}'

    def get(self) -> Iterable[str]:
        '''
        Returns all lines of the table. Use self.post() for post-processing.
        '''
        return chain.from_iterable(map(self.__get, range(len(self.__champs))))

    def clear(self):
        out_rm(-self.__seek)

    def update(self, champs: Iterable[int]):
        '''
        Updates the presented table to match given champ selections
        '''
        while not self.__q.empty():
            i, wl = self.__q.get()
            self.__wl[i] = wl
            self.__champs = []
        if self.__champs != champs:
            self.__champs = champs
            self.__champidx = [next((i for i, c in enumerate(
                y[2]) if x == c['championId']), -1) for x, y in zip(champs, self.__ps)]
            self.__show_fn()

    def post(self, i: int, x: str):
        '''
        Applies post-processing effects (e.g. coloring) to given line
        '''
        t, g = ctell, cgray
        j = i // 2  # player idx

        def pts(i, x: str):  # line 2: mastery points
            if (m1k := x.find('-1K')) != -1:
                return f'{g(x[:m1k])}   {x[m1k+3:]}'
            b = x.index('K') + 1
            for _ in range(self.__champidx[j]):
                b = x.index('K', b) + 1
            a = x.rindex(' ', 0, b)
            return f'{g(x[:a])}{x[a:b]}{g(x[b:])}'

        def champ(x: str):  # line 1: champ names
            key = champions[self.__champs[j]]['name']
            a = x.index(key)
            b = a + len(key)
            return f'{g(x[:a])}{t(x[a:b])}{g(x[b:])}'

        if i % 2:  # odd line idx
            if i == len(self.__champs) * 2 - 1:
                self.clear()
            nwl = x.index(' ')
            wl = ''.join((t if y == '1' else g)('•') for y in x[:nwl])
            return f'{wl}{pts(j, x[nwl:])}'

        rank = x.index('\t')
        rstr = c(x[rank + 1:rank + 3]) if (c := crank.get(x[rank + 1])) else ''
        return f'{t(x[:rank])} {rstr}{champ(x[rank+(3 if rstr else 1):])}'

#
# Champ select inspector
#

class ChampSelect():
    def __get_data(self) -> tuple[dict, str]:
        if DEBUG:
            from loltui.debugdata import champ_select
            return champ_select
        out(f'waiting for champ select, press {ctell("Ctrl+C")} to abort')
        while True:
            if d := self.__cl.get_dict(
                    'lol-lobby-team-builder/champ-select/v1/session'):
                out_rm()
                return d, qdata[self.__cl.get_dict(
                    'lol-lobby-team-builder/v1/matchmaking')['queueId']]['description'].rstrip(' games')
            time.sleep(2)

    def __init__(self, cl: Client):
        self.__cl = cl
        d, self.__q = self.__get_data()
        self.__pi = PlayerInfo(cl, [x['summonerId']
                                    for x in d['myTeam']], self.__present)
        self.update(d)

    def __present(self):
        '''
        Constructs and presents champ select box to the user
        '''
        box(*self.__pi.get(), post=self.__pi.post, title=self.__q)

    def update(self, d: Optional[dict] = None) -> bool:
        '''
        Returns whether update was possible
        '''
        if not d:
            if DEBUG:
                return False
            d = self.__cl.get_dict(
                'lol-lobby-team-builder/champ-select/v1/session')
            if not d:
                self.__pi.clear()
                return False
        self.__pi.update([x['championId'] for x in d['myTeam']])
        return True

cs = ChampSelect(client)
while cs.update():
    time.sleep(0.25)  # we can do this often as no outbound requests are done

# TODO: load screen & in-game
