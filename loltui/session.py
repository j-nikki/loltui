import threading
import time
from contextlib import suppress
from itertools import chain
from typing import Callable, Iterable, Optional, Union

from loltui.client import client, qdata
from loltui.output import *
from loltui.playerinfo import PlayerInfo
from loltui.runes import apply_runes, get_runes

#
# Rune retrieval
#

_lk = threading.Lock()
_runes = dict()
_rune_work = set()

_roles = ['Top', 'Jungle', 'Middle', 'Support', 'ADC']
def _rune_fetch():
    val = next(iter(_rune_work))
    with suppress(StopIteration):
        while True:
            cid, role = next(iter(_rune_work))
            cname = client.champions[cid]['name']
            val = get_runes(cname, _roles[role].lower())
            with _lk:
                _runes[(cid, role)] = val
                _rune_work.remove((cid, role))
                val = next(iter(_rune_work))

def _get_rune(key) -> Optional[Union[list[int], str]]:
    with _lk:
        if val := _runes.get(key):
            return val
        elif key not in _rune_work:
            if not _rune_work:
                threading.Thread(target=_rune_fetch).start()
            _rune_work.add(key)

#
# Session tab-keeper
#

def _buts(cur: Optional[int]) -> str:
    return f'\033[38;5;46m▏RUNES: {" ".join(f"{cbut(r[0])}{r[1:]}" if i != cur else f"{CSI}38;5;46m{r}{CSI}0m" for i, r in enumerate(_roles))}'
class Session:
    def __init__(self, q: str, geom: tuple[int, int], sids: Iterable[int], cids_getter: Callable[[
    ], Optional[list[int]]], *, runes: bool = False):
        self.__q = q
        self.__pi = PlayerInfo(geom, sids, self.__present)
        self.__runes = runes
        self.__cg = cids_getter

    def __present(self):
        '''
        Constructs and presents champ select box to the user
        '''
        box(*self.__pi.get(), post=self.__pi.post, title=self.__q)

    def loop(self, interval: float):

        #
        # Show player info only
        #

        if not self.__runes:
            while cids := self.__cg():
                self.__pi.update(cids)
                time.sleep(interval)
            self.__pi.clear()
            return

        #
        # Additionally show runes
        #

        global _role
        _update = False
        prev_cc = None
        prev_role = None
        runemsg = [_buts(_role)]
        def cb(i: int):
            global _role
            _role = i
        buts = button(runemsg[0], cb)

        while cids := self.__cg():
            # Update presented summoner info
            if self.__pi.update(cids):
                _update = True

            # Update runes
            if _role and (cc := int(client.get(
                    'lol-champ-select/v1/current-champion').content)):
                if prev_cc == cc and prev_role == _role:
                    if _update:
                        out(runemsg)
                        _update = False
                elif runes := _get_rune((cc, _role)):
                    prev_cc = cc
                    prev_role = _role
                    if not _update:
                        out_rm(len(runemsg))
                    _update = False
                    runename = f'{client.champions[cc]["name"]} {_roles[_role]}'
                    runemsg = [
                        _buts(_role), *map(lambda x:f'\033[38;5;46m▏ {x}', apply_runes(runename, runes))]
                    out(runemsg)
            elif prev_role != _role:
                prev_role = _role
                if not _update:
                    out_rm(len(runemsg))
                _update = False
                runemsg = [_buts(_role)]
                out(runemsg)
            elif _update:
                _update = False
                out(runemsg)

            # Periodical polling for champs
            time.sleep(interval)

        button_unsub(buts)
        self.__pi.clear()
        _role = None

#
# Session awaiting
#

def _get_gd_q() -> tuple[dict, str]:
    gd = client.get_json('lol-gameflow/v1/session')['gameData']
    return gd, qdata[qid]['description'].removesuffix(' games') if (
        qid := gd['queue']['id']) != -1 else 'Custom'

def _ingame() -> bool:
    return client.get(
        'lol-gameflow/v1/gameflow-phase').content == b'"InProgress"'
_champ2id = {v['name']: k for k, v in client.champions.items()}
def _get_ingame_session() -> Optional[Session]:
    '''
    In-game: info given on all players
    '''
    if _ingame() and (d := client.game('liveclientdata/allgamedata')):
        d = {x['summonerName']: x['championName'] for x in d['allPlayers']}
        gd, q = _get_gd_q()
        ps = [[y for y in x if 'summonerId' in y]
              for x in (gd['teamOne'], gd['teamTwo'])]
        g = list(map(len, ps))
        ps = list(chain.from_iterable(ps))
        cids = [_champ2id[d[x['summonerName']]] for x in ps]
        return Session(q, g, [int(x['summonerId'])
                              for x in ps], lambda: _ingame() and cids)

_pos = ['top', 'jungle', 'middle', 'utility', 'bottom']
def _get_champsel_session() -> Optional[Session]:
    '''
    Champ selection: only teammates revealed, rune helper
    '''
    def get_team():
        if (d := client.get_json(
                'lol-champ-select/v1/session')) and 'myTeam' in d:
            return d['myTeam']
    def get_cids() -> Optional[list[int]]:
        if d := get_team():
            return [x['championId'] for x in d]
    if d := get_team():
        _, q = _get_gd_q()

        cs = client.get_json('lol-summoner/v1/current-summoner')['summonerId']
        cspos = next(x['assignedPosition'] for x in d if x['summonerId'] == cs)
        global _role
        _role = _pos.index(cspos) if cspos in _pos else None

        return Session(q, (len(d), 0), [x['summonerId']
                                        for x in d], get_cids, runes=True)

def _try_get_ses() -> Optional[Session]:
    if (gf := client.get('lol-gameflow/v1/gameflow-phase').content) == b'"ChampSelect"':
        return _get_champsel_session()
    elif gf == b'"InProgress"':
        return _get_ingame_session()

def get_session(interval: float) -> Session:
    '''
    Returns a Session representing either a champ select or in-progress game
    '''
    while not (ses := _try_get_ses()):
        time.sleep(interval)
    return ses
