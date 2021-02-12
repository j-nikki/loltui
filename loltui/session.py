from itertools import chain
from typing import Callable

from loltui.client import *
from loltui.playerinfo import *

_runes = Dict()
_rune_work = set()

#
# Session tab-keeper
#

_roles = ['Top', 'Jungle', 'Middle', 'Support', 'ADC']
def _rune_fetch():
    with suppress(KeyError):
        while True:
            cid, role = _rune_work.pop()
            cname = client.champions[cid]['name']
            if runes := get_runes(cname, _roles[role].lower()):
                _runes.write((cid, role), runes)

def _buts(cur: Optional[int] = None) -> str:
    return f'\033[38;5;46m▌RUNES: {" ".join(f"{cbut(r[0])}{r[1:]}" if i != cur else ctell(r) for i, r in enumerate(_roles))}'
class Session:
    def __init__(
            self, q: str, geom: tuple[int, int], sids: Iterable[int], runes: bool = False):
        self.__q = q
        self.__pi = PlayerInfo(geom, sids, self.__present)
        self.__runes = runes

    def __present(self):
        '''
        Constructs and presents champ select box to the user
        '''
        box(*self.__pi.get(), post=self.__pi.post, title=self.__q)

    def loop(self, cids_getter, interval: float):

        #
        # Show player info only
        #

        if not self.__runes:
            while cids := cids_getter():
                self.__pi.update(cids)
                time.sleep(interval)
            self.__pi.clear()
            return

        #
        # Additionally show runes
        #

        global _role
        _role = None
        _update = False
        prev_cc = None
        prev_role = None
        runemsg = [_buts()]
        def cb(i: int):
            global _role
            _role = i
        buts = button(runemsg[0], cb)

        while cids := cids_getter():
            # Update presented summoner info
            if self.__pi.update(cids):
                _update = True

            # Update runes
            if _role and (cc := int(client.get(
                    'lol-champ-select/v1/current-champion').content)):
                key = (cc, _role)
                if prev_cc == cc and prev_role == _role:
                    if _update:
                        out(runemsg)
                        _update = False
                elif _runes.write(key, [], False):
                    if not _rune_work:
                        threading.Thread(target=_rune_fetch).start()
                    _rune_work.add(key)
                elif runes := _runes[key]:
                    prev_cc = cc
                    prev_role = _role
                    if not _update:
                        out_rm(len(runemsg))
                    _update = False
                    runename = f'{client.champions[cc]["name"]} {_roles[_role]}'
                    runemsg = [
                        _buts(_role), *map(lambda x:f'\033[38;5;46m▌ {x}', apply_runes(runename, runes))]
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

#
# Session awaiting
#

champ2id = {v['name']: k for k, v in client.champions.items()}
def get_session_params(interval: float) -> tuple[tuple, Callable]:
    '''
    Returns the params to Session instance as well as a champion ID querier
    '''

    def get_gfphase():
        return client.get('lol-gameflow/v1/gameflow-phase').content

    # Wait until a session is agoing
    while (phase := get_gfphase()) not in (b'"ChampSelect"', b'"InProgress"'):
        time.sleep(interval)

    # Get game data and queue type
    gd = client.get_json('lol-gameflow/v1/session')['gameData']
    q = qdata[qid]['description'].removesuffix(' games') if (
        qid := gd['queue']['id']) != -1 else 'Custom'

    def get_ses():
        if (d := client.get_json('lol-champ-select/v1/session')) and 'myTeam' in d:
            return d

    #
    # Champ select
    #

    if phase == b'"ChampSelect"':
        d = get_ses()
        def get_cids():
            if d := get_ses():
                return [x['championId'] for x in d['myTeam']]
        sids = [x['summonerId'] for x in d['myTeam']]
        return (q, (len(d['myTeam']), 0), sids, True), get_cids

    #
    # In-game
    #

    ps = [[y for y in x if 'summonerId' in y]  # filter out bots
          for x in (gd['teamOne'], gd['teamTwo'])]
    g = list(map(len, ps))
    ps = list(chain.from_iterable(ps))
    s2c = {x['summonerName']: x['championName']
           for x in client.game('liveclientdata/allgamedata')['allPlayers']}

    return (q, g, [int(x['summonerId']) for x in ps]), lambda: get_gfphase(
    ) == b'"InProgress"' and [champ2id[s2c[x['summonerName']]] for x in ps]
