import json
import os
import tempfile
import time
from contextlib import suppress
from typing import Any, Optional, TypeVar
from urllib.request import urlopen

import psutil
import requests
from requests.models import Response

from loltui.output import *

_ReqFn = TypeVar('_ReqFn', bound=Callable[..., Any])
def _retrying_request(c, f: _ReqFn) -> _ReqFn:
    def wrap(endpoint: str, *args, **kwargs):
        while True:
            res = f(f'https://127.0.0.1:{c._port}/{endpoint}', *args, **kwargs, headers={
                'Accept': 'application/json'}, auth=('riot', c._token), verify=c._cert)
            # https://developer.riotgames.com/docs/portal#web-apis_4xx-error-codes
            if res.status_code != 429:
                return res
            time.sleep(float(res.headers['Retry-After']))
    return wrap

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
        certfd, self._cert = tempfile.mkstemp(suffix='.pem')
        os.write(certfd, urlopen(
            'https://static.developer.riotgames.com/docs/lol/riotgames.pem').read())
        os.close(certfd)
        self._port, self._token = _get_port_and_token()
        self.get = _retrying_request(self, requests.get)
        self.post = _retrying_request(self, requests.post)
        self.put = _retrying_request(self, requests.put)
        self.patch = _retrying_request(self, requests.patch)
        self.delete = _retrying_request(self, requests.delete)
        self.__v = json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/realms/{self.get_json("riotclient/region-locale")["region"].lower()}.json').read())['v']
        self.__cs = {int(x['key']): x for x in json.loads(urlopen(
            f'https://ddragon.leagueoflegends.com/cdn/{self.__v}/data/en_US/champion.json').read())['data'].values()}

    def get_json(self, endpoint: str, **kwargs) -> dict:
        return self.get(endpoint, **kwargs).json()

    def game(self, endpoint: str, **kwargs) -> Optional[dict]:
        port = 2999  # fixed port per Riot docs
        with suppress(requests.ConnectionError):
            res = requests.get(
                f'https://127.0.0.1:{port}/{endpoint}',
                params=kwargs,
                headers={
                    'Accept': 'application/json'},
                verify=self._cert)
            if res.status_code == 200:
                return json.loads(res.content)

    def __del__(self):
        os.remove(self._cert)

    @property
    def version(self) -> str:
        return self.__v

    @property
    def champions(self) -> dict[int, dict]:
        return self.__cs

qdata = {x['queueId']: x for x in json.loads(urlopen(
    'https://static.developer.riotgames.com/docs/lol/queues.json').read())}

client = Client()
