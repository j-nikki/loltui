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
import riotwatcher as rw

from loltui.devkey import DEV_KEY

#
# Process args
#

DEBUG = '--debug' in sys.argv

if '--exe' in sys.argv:
    import io
    import zipfile

    import PyInstaller.__main__

    with tempfile.TemporaryDirectory() as d_dst:
        r = requests.get(
            'https://github.com/upx/upx/releases/download/v3.96/upx-3.96-win64.zip')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extract('upx-3.96-win64/upx.exe', d_dst)
        old_env = os.environ.copy()
        os.environ['PYTHONOPTIMIZE'] = '1'
        try:
            d_src = os.path.dirname(sys.argv[0])
            PyInstaller.__main__.run([
                sys.argv[0],
                '-F',
                '--upx-dir',
                os.path.join(d_dst, 'upx-3.96-win64'),
                '--workpath',
                d_dst,
                '--specpath',
                d_dst,
                '--distpath',
                '.',
                '--clean',
                '-p',
                d_src,
                '-i',
                os.path.join(d_src, 'images', 'icon.ico')])
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        exit(0)

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
        res = [False for _ in range(5)]
        for i, m in enumerate(lw.match.by_id(platf, x['gameId']) for x in ms):
            pi = next(x['participantId'] for x in m['participantIdentities']
                      if x['player']['accountId'] == acc)
            ti = next(x['teamId']
                      for x in m['participants'] if x['participantId'] == pi)
            res[i] = next(x['win'] == 'Win' for x in m['teams']
                          if x['teamId'] == ti)
        return res
    except BaseException:
        return []

def id2player(sid: str) -> tuple[str, str, list[dict]]:  # -> id, name, masteries
    # Since V4, Riot API expects per-project encrypted IDs. As client does not
    # thus give IDs in a satisfactory format, we query champion names through
    # client and use that to retrieve summoner data.
    dto = lw.summoner.by_name(platf, client.get_dict(
        f'lol-summoner/v1/summoners/{sid}')['internalName'])
    return dto, dto['name'], lw.champion_mastery.by_summoner(platf, dto['id'])

#
# Player info presenter
#

champions[-1] = {'name': '...'}  # dummy champion (e.g. when none picked)
class PlayerInfo():
    __ppts = re.compile(r'\S+')

    def __wl_calc(self):
        for i, wl in enumerate(wins_losses(
                x[0]['accountId']) for x in self.__ps):
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
        _, name, champs = self.__ps[i]
        if not 0 <= (idx := self.__champidx[i]) <= 9:
            champs = champs[:8]
            champs.append({
                'championId': -1,
                'championPoints': -1})
            champs.append({
                'championId': self.__champs[i],
                'championPoints': 0 if idx == -1 else self.__ps[i][2][idx]['championPoints']})
        return f'{name}{T}│ {T.join(champions[c["championId"]]["name"] for c in champs[:10])}', \
            f'.....{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in champs[:10])}'

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

        def wl(i):
            if not self.__wl[i]:
                return '     '
            return ''.join((t if x else g)('•') for x in self.__wl[i])

        def pts(i, x: str):
            if (m1k := x.find('-1K')) != -1:
                return f'{g(x[:m1k])}   {x[m1k+3:]}'
            b = x.index('K') + 1
            for _ in range(self.__champidx[j]):
                b = x.index('K', b) + 1
            a = x.rindex(' ', 0, b)
            return f'{g(x[:a])}{x[a:b]}{g(x[b:])}'

        def champ(x: str):
            a, b = next(re.finditer(
                r'\b' + champions[self.__champs[j]]['name'] + r'\b', x)).span()
            return f'{g(x[:a])}{t(x[a:b])}{g(x[b:])}'

        if i % 2:  # odd line idx
            if i == len(self.__champs) * 2 - 1:
                self.clear()
            return f'{wl(j)}{pts(j, x[5:])}' if i % 2 else t(x)

        sep = x.rindex('│')
        return f'{t(x[:sep])}{champ(x[sep:])}'

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
