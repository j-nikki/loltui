import json
import os
import tempfile
import time
from contextlib import suppress
from typing import Optional
from urllib import request
from urllib.request import urlopen

import psutil
import requests

from loltui.output import *

_divs = ['I', 'II', 'III', 'IV', 'V']

def _get(*args, **kwargs) -> requests.Response:
    while (res := requests.get(*args, **kwargs)).status_code == 429:
        # https://developer.riotgames.com/docs/portal#web-apis_4xx-error-codes
        retry_after = float(res.headers['Retry-After'])
        time.sleep(retry_after)
    return res

def _get_port_and_token() -> tuple[str, str]:
    out(f'waiting for client, press {ctell("Ctrl+C")} to abort')
    while True:
        with suppress(FileNotFoundError, StopIteration, psutil.NoSuchProcess):
            p = psutil.Process
            exe = next(p(c.pid).exe() for c in psutil.net_connections('tcp4') if p(
                c.pid).name() == 'LeagueClient.exe' and c.status == 'LISTEN')
            with open(os.path.join(os.path.dirname(exe), 'lockfile'), 'r') as f:
                _, _, port, token, _ = f.read().split(':')
            out_rm()
            return port, token
        time.sleep(2)

class Client:
    def __init__(self):
        certfd, self.__cert = tempfile.mkstemp(suffix='.pem')
        os.write(certfd, urlopen(
            'https://static.developer.riotgames.com/docs/lol/riotgames.pem').read())
        os.close(certfd)
        self.__port, self.__token = _get_port_and_token()
        self.__v = json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/realms/{self.get_dict("riotclient/region-locale")["region"].lower()}.json').read())['v']
        self.__cs = {int(x['key']): x for x in json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/cdn/{self.__v}/data/en_US/champion.json').read())['data'].values()}

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        try:
            return _get(f'https://127.0.0.1:{self.__port}/{endpoint}', params={**kwargs}, headers={
                'Accept': 'application/json'}, auth=('riot', self.__token), verify=self.__cert)
        except Exception as e:
            out(f'{cyell(e.__class__.__name__)}: {ctell(e)}')
            exit(1)

    def get_dict(self, endpoint: str, **kwargs) -> dict:
        if (resp := self.get(endpoint, **kwargs)).status_code != 404:
            return json.loads(resp.content)
        return {}

    def game(self, endpoint: str, **kwargs) -> Optional[dict]:
        port = 2999  # fixed port per Riot docs
        with suppress(requests.ConnectionError):
            res = _get(f'https://127.0.0.1:{port}/{endpoint}', params=kwargs, headers={
                'Accept': 'application/json'}, verify=self.__cert)
            if res.status_code == 200:
                return json.loads(res.content)

    def wins_losses(self, info) -> list[bool]:
        '''
        Gets outcome of ranked games from 20 last games
        '''
        acc = info['accountId']
        ml = self.get_dict(f'lol-match-history/v1/friend-matchlists/{acc}')
        gs = [g for g in ml['games']['games']
              [::-1] if g['queueId'] in (420, 440)]
        def f(g):
            with suppress(StopIteration):
                pi = next(x['participantId'] for x in g['participantIdentities']
                          if x['player']['accountId'] == acc)
                return next(x['stats']['win']
                            for x in g['participants'] if x['participantId'] == pi)
        return list(filter(lambda x: x is not None, map(f, gs)))

    def id2player(self, sid: str) -> tuple[str, str, list]:
        '''
        Returns summoner info, rank, and masteries
        '''
        d = self.get_dict(f'lol-summoner/v1/summoners/{sid}')
        q = self.get_dict(
            f'lol-ranked/v1/ranked-stats/{d["puuid"]}')['queueMap']['RANKED_SOLO_5x5']
        def fmt(t: str, d: str):
            return f'{t[0].upper()}{_divs.index(d)+1}' if d != 'NA' else ''
        rank = f'{fmt(q["previousSeasonEndTier"], q["previousSeasonEndDivision"])}→{fmt(q["tier"], q["division"])}'
        cm = self.get_dict(
            f'lol-collections/v1/inventories/{d["summonerId"]}/champion-mastery')
        return d, rank if rank != '→' else '', cm

    def __del__(self):
        os.remove(self.__cert)

    @property
    def version(self) -> str:
        return self.__v

    @property
    def champions(self) -> dict[int, dict]:
        return self.__cs

qdata = {x['queueId']: x for x in json.loads(urlopen(
    'https://static.developer.riotgames.com/docs/lol/queues.json').read())}
