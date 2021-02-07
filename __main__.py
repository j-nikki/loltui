import json
import os
import re
import sys
import tempfile
import time
from itertools import chain
from typing import Optional
from urllib.request import urlopen
from .devkey import DEV_KEY

import psutil
import requests
import riotwatcher as rw

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
    def __get_exe():
        out(f'waiting for client, press {ctell("Ctrl+C")} to abort')
        while True:
            try:
                res = next(p.exe() for p in psutil.process_iter()
                           if p.name() == 'LeagueClient.exe')
                out_rm()
                return res
            except StopIteration:
                time.sleep(2)

    def __init__(self):
        certfd, self.__cert = tempfile.mkstemp(suffix='.pem')
        os.write(certfd, urlopen(
            'https://static.developer.riotgames.com/docs/lol/riotgames.pem').read())
        os.close(certfd)

        dir_, _ = os.path.split(self.__get_exe())
        with open(os.path.join(dir_, 'lockfile'), 'r') as f:
            _, _, self.__port, self.__token, _ = f.read().split(':')

        reg = self.get_dict('riotclient/region-locale')['region']
        global platf
        platf = __class__.__reg2platf.get(reg, reg)
        out(f"using region {ctell(reg)} (platform {ctell(platf)})")

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

client = Client()

#
# Champion data
#

lw = rw.LolWatcher(DEV_KEY)
vdata = json.loads(
    urlopen('https://ddragon.leagueoflegends.com/realms/euw.json').read())['v']
out(f'game data version is {ctell(vdata)}')
champions = {int(x['key']): x for x in lw.data_dragon.champions(
    vdata)['data'].values()}

#
# Queue data
#

qdata = {x['queueId']: x for x in json.loads(urlopen(
    'https://static.developer.riotgames.com/docs/lol/queues.json').read())}

#
# Summoner data
#

def wins_losses(acc) -> list[bool]:
    try:
        ms = lw.match.matchlist_by_account(
            platf, acc, {420, 440}, end_index=5)['matches']
    except BaseException:
        return []
    res = [False for _ in range(5)]
    for i, m in enumerate(lw.match.by_id(platf, x['gameId']) for x in ms):
        pi = next(x['participantId'] for x in m['participantIdentities']
                  if x['player']['accountId'] == acc)
        ti = next(x['teamId']
                  for x in m['participants'] if x['participantId'] == pi)
        res[i] = next(x['win'] == 'Win' for x in m['teams']
                      if x['teamId'] == ti)
    return res

def id2player(d) -> tuple[str, str, list[dict]]:  # -> id, name, masteries
    # Since V4, Riot API expects per-project encrypted IDs. As client does not
    # thus give IDs in a satisfactory format, we query champion names through
    # client and use that to retrieve summoner data.
    dto = lw.summoner.by_name(platf, client.get_dict(
        f'lol-summoner/v1/summoners/{d["summonerId"]}')['internalName'])
    return dto, dto['name'], lw.champion_mastery.by_summoner(platf, dto['id'])

#
# Champ select info
#

class ChampSelect():
    __ppts = re.compile(r'\S+')

    def __get_data(self) -> tuple[dict, str]:
        if DEBUG:
            from .debugdata import champ_select
            return champ_select
        out(f'waiting for champ select, press {ctell("Ctrl+C")} to abort')
        while True:
            if d := self.__cl.get_dict(
                    'lol-lobby-team-builder/champ-select/v1/session'):
                out_rm()
                out('champ select detected, collecting stats')
                return d, qdata[self.__cl.get_dict(
                    'lol-lobby-team-builder/v1/matchmaking')['queueId']]['description'].rstrip(' games')
            time.sleep(2)

    def __init__(self, cl: Client):
        self.__cl = cl
        self.__champs = []
        d, self.__q = self.__get_data()
        self.__ps = [*map(id2player, d['myTeam'])]
        self.__wl = [[] for _ in self.__ps]
        self.__seek = out_sz()
        self.update(d)
        for i, wl in enumerate(wins_losses(
                x[0]['accountId']) for x in self.__ps):
            self.__wl[i] = wl
            self.__update()

    def __info(self, i: int):
        '''
        Returns a list of strings with info on player at given index
        '''
        T = '\0 '  # 0-terminator, used for aligning info
        _, name, champs = self.__ps[i]
        if (idx := self.__champidx[i]) > 9:
            champs = champs[:]
            champs[8] = None
            champs[9] = {
                'championId': self.__champs[i],
                'championPoints': 0 if idx == -1 else self.__ps[i][2][idx]['championPoints']}
        return f'{name}{T}│ {T.join(champions[c["championId"]]["name"] if c else "..." for c in champs[:10])}', \
            f'.....{T}│ {T.join(str(c["championPoints"]//1000)+"K" if c else "" for c in champs[:10])}'

    def __update(self):
        '''
        Constructs and presents champ select box to the user
        '''
        def post_wl(i):  # win-loss post-processing
            if not self.__wl[i]:
                return '     '
            wl = [cgray('•'), ctell('•')]
            return ''.join(wl[x] for x in self.__wl[i])

        def post_pts(i, x):  # mastery points post-processing
            a, b = list(map(re.Match.span, self.__ppts.finditer(x)))[
                self.__champidx[i] + 1 if 0 <= self.__champidx[i] <= 9 else 9]
            return f'{cgray(x[:a])}{x[a:b]}{cgray(x[b:])}'

        def post(i, x: str):  # post-processing main
            t, g = ctell, cgray
            if i % 2:  # odd line idx
                if i == len(self.__champs) * 2 - 1:
                    out_rm(-self.__seek)
                j = i // 2  # player idx
                return f'{post_wl(j)}{post_pts(j, x[5:])}' if i % 2 else t(x)
            sep = x.rindex('│')
            if (ell := x.find('...', sep)) == -1:
                return t(f'{t(x[:sep])}{g("│")}{t(x[sep+1:])}')
            return t(
                f'{t(x[:sep])}{g("│")}{t(x[sep+1:ell])}{g(x[ell:ell+3])}{t(x[ell+3:])}')

        box(*chain.from_iterable(map(self.__info, range(len(self.__champs)))),
            post=post, title=self.__q)

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
                return False
        champs = [x['championId'] for x in d['myTeam']]

        if champs != self.__champs:
            self.__champs = champs
            self.__champidx = [next((i for i, c in enumerate(
                y[2]) if x == c['championId']), -1) for x, y in zip(champs, self.__ps)]
            self.__update()

        return True

cs = ChampSelect(client)
while cs.update():
    time.sleep(0.25)  # we can do this often as no outbound requests are done
