from itertools import chain
from typing import Callable

from loltui.client import *
from loltui.playerinfo import *

#
# Session tab-keeper
#

class Session:
    def __init__(
            self, q: str, geom: tuple[int, int], sids: Iterable[int], cids: Iterable[int]):
        self.__q = q
        self.__pi = PlayerInfo(geom, sids, self.__present)
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

champ2id = {v['name']: k for k, v in client.champions.items()}
def get_session_params(interval: float) -> tuple[tuple, Callable]:
    '''
    Returns the params to Session instance as well as a champion ID querier
    '''

    def ingame() -> bool:
        return client.get('lol-gameflow/v1/gameflow-phase').content == b'"InProgress"'

    def get_ses():
        if (d := client.get_json(
                'lol-lobby-team-builder/champ-select/v1/session')) and 'myTeam' in d:
            return d

    while True:
        if d := get_ses():
            q = qdata[client.get_json(
                'lol-lobby-team-builder/v1/matchmaking')['queueId']]['description'].rstrip(' games')
            def get_cids():
                if d := get_ses():
                    return [x['championId'] for x in d['myTeam']]
            return (q, (len(d['myTeam']), 0), [x['summonerId'] for x in d['myTeam']], [
                x['championId'] for x in d['myTeam']]), get_cids

        if d := client.game('liveclientdata/allgamedata'):
            d = {x['summonerName']: x['championName'] for x in d['allPlayers']}
            gd = client.get_json('lol-gameflow/v1/session')['gameData']
            ps = [[y for y in x if 'summonerId' in y]
                  for x in (gd['teamOne'], gd['teamTwo'])]
            g = list(map(len, ps))
            ps = list(chain.from_iterable(ps))
            q = qdata.get(gd['queue']['id'], {'description': 'Custom'})[
                'description'].removesuffix(' games')
            cids = [champ2id[d[x['summonerName']]] for x in ps]
            return (q, g, [int(x['summonerId'])
                           for x in ps], cids), lambda: ingame() and cids

        time.sleep(interval)
