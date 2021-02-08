import json
import os
import queue
import re
import tempfile
import threading
import time
from argparse import ArgumentParser
from contextlib import suppress
from itertools import chain
from typing import Iterable, Optional
from urllib.request import urlopen

import psutil
import requests

#
# Process args
#

ap = ArgumentParser(
    description="gives info about the players you're playing with")
ap.add_argument('--debug', '-d', action='store_true',
                help='supply the program with demo data')
args = ap.parse_args()

DEBUG = args.debug

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
            with suppress(FileNotFoundError, StopIteration, psutil.NoSuchProcess):
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

    def game(self, endpoint: str, **kwargs) -> Optional[dict]:
        port = 2999  # fixed port per Riot docs
        with suppress(requests.ConnectionError):
            res = requests.get(f'https://127.0.0.1:{port}/{endpoint}', params=kwargs, headers={
                'Accept': 'application/json'}, verify=self.__cert)
            if res.status_code == 200:
                return json.loads(res.content)

    def __del__(self):
        os.remove(self.__cert)

client = Client()

#
# Champion data
#

vdata = json.loads(urlopen(
    f'https://ddragon.leagueoflegends.com/realms/{client.get_dict("riotclient/region-locale")["region"].lower()}.json').read())['v']
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
    def fmt(t: str, d: str):
        return f'{t[0].upper()}{divs.index(d)+1}' if d != 'NA' else ''
    rank = f'{fmt(q["previousSeasonEndTier"], q["previousSeasonEndDivision"])}→{fmt(q["tier"], q["division"])}'
    cm = client.get_dict(
        f'lol-collections/v1/inventories/{d["summonerId"]}/champion-mastery')
    return d, rank if rank != '→' else '', cm

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
    __prank = re.compile(r'\t(\w\d)?(→)?(\w\d)?')

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
        (info, rank, champs), idx = self.__ps[i], self.__champidx[i]
        name = info['displayName'] + '\t' + rank
        if not 0 <= idx <= 9:
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

    def update(self, cids: list[int]):
        '''
        Updates the presented table to match given champ selections
        '''
        while not self.__q.empty():
            i, wl = self.__q.get()
            self.__wl[i] = wl
            self.__champs = []
        if self.__champs != cids:
            self.__champs = cids
            self.__champidx = [next((i for i, c in enumerate(
                y[2]) if x == c['championId']), -1) for x, y in zip(cids, self.__ps)]
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

        m = self.__prank.search(x)
        def color(y): return crank[y[0]](y)
        rank = f'{color(m[1]) if m[1] else ""}{cgray(m[2]) if m[2] else ""}{color(m[3]) if m[3] else ""}'
        a, b = m.span()
        return f'{t(x[:a])} {rank}{champ(x[b:])}'

#
# Session tab-keeper
#

class Session():
    def __init__(self, q: str, sids: Iterable[int], cids: Iterable[int]):
        self.__q = q
        self.__pi = PlayerInfo(client, sids, self.__present)
        self.__pi.update(cids)

    def __present(self):
        '''
        Constructs and presents champ select box to the user
        '''
        box(*self.__pi.get(), post=self.__pi.post, title=self.__q)

    def loop(self, cids_getter, interval: float):
        while cids := cids_getter():
            self.__pi.update(cids)
            time.sleep(interval)
        self.__pi.clear()

#
# Session awaiting
#

champ2id = {v['name']: k for k, v in champions.items()}
def get_session_params(interval: float):

    if DEBUG:
        # Debug stats (champ select sample)
        from loltui.debugdata import champ_select
        d, q = champ_select
        cids = [x['championId'] for x in d['myTeam']]
        return q, [x['summonerId'] for x in d['myTeam']], cids, lambda: cids

    def ingame() -> bool:
        return client.get(
            'lol-gameflow/v1/gameflow-phase').content == b'"InProgress"'

    while True:
        if d := client.get_dict(
                'lol-lobby-team-builder/champ-select/v1/session'):
            q = qdata[client.get_dict(
                'lol-lobby-team-builder/v1/matchmaking')['queueId']]['description'].rstrip(' games')
            def get_cids():
                if d := client.get_dict(
                        'lol-lobby-team-builder/champ-select/v1/session'):
                    return [x['championId'] for x in d['myTeam']]
            return q, [x['summonerId'] for x in d['myTeam']], [
                x['championId'] for x in d['myTeam']], get_cids

        if d := client.game('liveclientdata/allgamedata'):
            d = {x['summonerName']: x['championName'] for x in d['allPlayers']}
            gd = client.get_dict('lol-gameflow/v1/session')['gameData']
            ps = list(chain(gd['teamOne'], gd['teamTwo']))
            q = qdata.get(gd['queue']['id'], {'description': 'Custom'})[
                'description'].removesuffix(' games')
            cids = [champ2id[d[x['summonerName']]] for x in ps]
            return q, [int(x['summonerId'])
                       for x in ps], cids, lambda: ingame() and cids

        time.sleep(interval)

#
# Main loop
#

try:
    while True:
        out(f'waiting for session, press {ctell("Ctrl+C")} to abort')
        q, sids, cids, cids_getter = get_session_params(1)
        out_rm()
        ses = Session(q, sids, cids)
        ses.loop(cids_getter, 1)
except KeyboardInterrupt:
    pass
