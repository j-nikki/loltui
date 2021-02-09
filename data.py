import json
import os
import tempfile
from contextlib import suppress
from typing import Optional
from urllib.request import urlopen

import psutil
import requests

from loltui.output import *

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
