import queue
import re
import threading
from typing import Iterable

from loltui.client import *
from loltui.dict import *
from loltui.runes import *

#
# Player info presenter
#

_prank = re.compile(r'\t(\w\d)?(→)?(\w\d)?')
_crank = {  # rank colorizers
    'I': colorizer(8),
    'B': colorizer(95),
    'S': colorizer(102),
    'G': colorizer(179),
    'P': colorizer(7),
    'D': colorizer(14),
    'M': colorizer(12),
    'C': colorizer(50)}
_runes = Dict()
_rune_work = set()

class PlayerInfo:
    def __wl_calc(self):
        for i, wl in enumerate(client.wins_losses(x[0]) for x in self.__ps):
            if wl:
                self.__qwl.put((i, ''.join(map(str, map(int, wl)))))

    def __init__(self, geom: tuple[int, int],
                 summoner_ids: Iterable[str], show_fn):
        self.__sep = geom[0]
        self.__ps = [client.id2player(x) for x in summoner_ids]
        self.__cid2mi = [{x['championId']: i for i,
                          x in enumerate(cm)} for _, _, cm in self.__ps]
        self.__wl = ['' for _ in self.__ps]
        self.__seek = out_sz()
        self.__champs = []
        self.__csc = None
        self.__runemsg = ''
        self.__show_fn = show_fn
        self.__qwl = queue.Queue()
        cs_sid = client.get_json(
            'lol-summoner/v1/current-summoner')['summonerId']
        self.__csidx = next(i for i, (d, _, _) in enumerate(
            self.__ps) if d['summonerId'] == cs_sid)
        threading.Thread(target=self.__wl_calc, daemon=True).start()

    def get(self) -> Iterable[str]:
        '''
        Returns all lines of the table. Use self.post() for post-processing.
        '''
        T = '\0 '  # 0-terminator, used for aligning info
        cg = client.champions.__getitem__
        def cname(c: int) -> str:
            return cg(c)['name']
        for i in range(len(self.__champs)):
            info, rank, cs = self.__ps[i]
            idx = self.__champidx[i]
            name = info['displayName'] + '\t' + rank
            if i == self.__sep:
                yield '\0 ┼' + '\0' * 11
            if self.__champs[i] and (idx is None or idx > 9):
                yield f'{name}{T}│ {T.join(cname(c["championId"]) for c in cs[:8])}{T}...{T}{cname(self.__champs[i])}{T}'
                pts = cs[idx]['championPoints'] // 1000 if idx else 0
                yield f'{self.__wl[i]}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in cs[:8])}{T}...{T}{pts}K{T}'
            else:
                yield f'{name}{T}│ {T.join(cname(c["championId"]) for c in cs[:10])}{T}'
                yield f'{self.__wl[i]}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in cs[:10])}{T}'

    def clear(self):
        if n := out_sz() - self.__seek:
            out_rm(n)

    def __rune_fetch(self):
        with suppress(KeyError):
            while True:
                cid = _rune_work.pop()
                cname = client.champions[cid]['name']
                if runes := get_runes(cname):
                    _runes.write(cid, runes)
        self.__champs = []

    def update(self, cids: list[int]):
        '''
        Updates the presented table to match given champ selections
        '''

        # Get any finished win-loss calculations
        while not self.__qwl.empty():
            i, wl = self.__qwl.get()
            self.__wl[i] = wl
            self.__champs = []

        # Re-render if necessary
        if self.__champs != cids:
            self.__champs = cids
            self.__champidx = list(x.get(y)
                                   for x, y in zip(self.__cid2mi, cids))
            self.__show_fn()
            csc = cids[self.__csidx]
            if csc:
                if _runes.write(csc, [], False):
                    if not _rune_work:
                        threading.Thread(target=self.__rune_fetch).start()
                    _rune_work.add(csc)
                elif runes := _runes[csc]:
                    if self.__csc != csc:
                        self.__runemsg = apply_runes(
                            client.champions[csc]["name"], runes)
                        self.__csc = csc
                    out(self.__runemsg)

    def post(self, i: int, x: str):
        '''
        Applies post-processing effects (e.g. coloring) to given line
        '''
        t, g = ctell, cgray

        if i == self.__sep * 2:
            return g(x.replace(' ', '─'))
        if i > self.__sep * 2:
            i -= 1
        j = i // 2  # player idx

        # Line 2: mastery points
        def pts(i, x: str):
            if (ell := x.find('...')) != -1:
                return f'{g(x[:ell])}   {x[ell+3:]}'
            if (idx := self.__champidx[j]) is None:
                return g(x)
            b = x.index('K') + 1
            while idx:
                b = x.index('K', b) + 1
                idx = idx - 1
            a = x.rindex(' ', 0, b)
            return f'{g(x[:a])}{x[a:b]}{g(x[b:])}'

        # Line 1: champ names
        def champ(x: str):
            if not self.__champs[j]:
                return g(x)
            key = client.champions[self.__champs[j]]['name']
            a = x.index(key)
            b = a + len(key)
            return f'{g(x[:a])}{t(x[a:b])}{g(x[b:])}'

        if i % 2:  # odd idx => line 2
            if i == len(self.__champs) * 2 - 1:
                self.clear()
            nwl = x.index(' ')
            wl = ''.join((t if y == '1' else g)('•') for y in x[:nwl])
            return f'{wl}{pts(j, x[nwl:])}'
        else:  # even idx => line 1
            m = _prank.search(x)
            def color(y): return _crank[y[0]](y)
            rank = f'{color(m[1]) if m[1] else ""}{cgray(m[2]) if m[2] else ""}{color(m[3]) if m[3] else ""}'
            a, b = m.span()
            return f'{t(x[:a])} {rank}{champ(x[b:])}'
