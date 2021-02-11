import json
import os
import tempfile
import time
from contextlib import suppress
from functools import wraps
from typing import Optional
from urllib.request import urlopen

import psutil
import requests
from requests.models import Response

from loltui.output import *

_divs = ['I', 'II', 'III', 'IV', 'V']

def retrying_request(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        while (res := f(*args, **kwargs)).status_code == 429:
            # https://developer.riotgames.com/docs/portal#web-apis_4xx-error-codes
            retry_after = float(res.headers['Retry-After'])
            time.sleep(retry_after)
        return res
    return wrap

_get = retrying_request(requests.get)
_post = retrying_request(requests.post)
_put = retrying_request(requests.put)
_patch = retrying_request(requests.patch)
_delete = retrying_request(requests.delete)

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
    def __make_requester(self, f):
        def wrap(endpoint: str, *args, **kwargs) -> Response:
            try:
                return f(f'https://127.0.0.1:{self.__port}/{endpoint}', *args, **kwargs, headers={
                    'Accept': 'application/json'}, auth=('riot', self.__token), verify=self.__cert)
            except Exception as e:
                out(f'{cyell(e.__class__.__name__)}: {ctell(e)}')
                exit(1)
        return wrap

    def __init__(self):
        certfd, self.__cert = tempfile.mkstemp(suffix='.pem')
        os.write(certfd, urlopen(
            'https://static.developer.riotgames.com/docs/lol/riotgames.pem').read())
        os.close(certfd)
        self.__port, self.__token = _get_port_and_token()
        def request(f):
            def wrap(endpoint: str, *args, **kwargs) -> Response:
                try:
                    resp = f(f'https://127.0.0.1:{self.__port}/{endpoint}', *args, **kwargs, headers={
                        'Accept': 'application/json'}, auth=('riot', self.__token), verify=self.__cert)
                    if resp.status_code // 100 == 2:
                        return resp
                    out(
                        f'got response code {cyell(resp.status_code)} from LeagueClient.exe {cgray(f"({endpoint=})")}')
                    exit(1)
                except Exception as e:
                    out(f'{cyell(e.__class__.__name__)}: {ctell(e)}')
                    exit(1)
            return wrap
        self.get, self.post, self.put, self.patch, self.delete = tuple(
            map(self.__make_requester, (_get, _post, _put, _patch, _delete)))
        self.__v = json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/realms/{self.get_json("riotclient/region-locale")["region"].lower()}.json').read())['v']
        self.__cs = {int(x['key']): x for x in json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/cdn/{self.__v}/data/en_US/champion.json').read())['data'].values()}

    def get_json(self, endpoint: str, **kwargs) -> dict:
        return self.get(endpoint, **kwargs).json()

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
        ml = self.get_json(f'lol-match-history/v1/friend-matchlists/{acc}')
        gs = [g for g in ml['games']['games']
              [::-1] if g['queueId'] in (420, 440)]
        def f(g):
            with suppress(StopIteration):
                pi = next(x['participantId'] for x in g['participantIdentities']
                          if x['player']['accountId'] == acc)
                return next(x['stats']['win']
                            for x in g['participants'] if x['participantId'] == pi)
        return list(filter(lambda x: x is not None, map(f, gs)))

    def id2player(self, sid: str) -> tuple[dict, str, list]:
        '''
        Returns summoner info, rank, and masteries
        '''
        d = self.get_json(f'lol-summoner/v1/summoners/{sid}')
        q = self.get_json(
            f'lol-ranked/v1/ranked-stats/{d["puuid"]}')['queueMap']['RANKED_SOLO_5x5']
        def fmt(t: str, d: str):
            return f'{t[0].upper()}{_divs.index(d)+1}' if d != 'NA' else ''
        rank = f'{fmt(q["previousSeasonEndTier"], q["previousSeasonEndDivision"])}→{fmt(q["tier"], q["division"])}'
        cm = self.get_json(
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

client = Client()
