import queue
import re
import threading
from typing import Iterable, Union

from loltui.client import *

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

class PlayerInfo:
    def __wl_calc(self):
        for i, wl in enumerate(self.__cl.wins_losses(x[0]) for x in self.__ps):
            if wl:
                self.__q.put((i, ''.join(map(str, map(int, wl)))))

    def __init__(self, client: Client, geom: tuple[int, int],
                 summoner_ids: Iterable[str], show_fn):
        self.__cl = client
        self.__sep = geom[0]
        self.__ps = [client.id2player(x) for x in summoner_ids]
        self.__cid2mi = [{x['championId']: i for i,
                          x in enumerate(cm)} for _, _, cm in self.__ps]
        self.__wl = ['' for _ in self.__ps]
        self.__seek = out_sz()
        self.__champs = []
        self.__show_fn = show_fn
        self.__q = queue.Queue()
        threading.Thread(target=self.__wl_calc, daemon=True).start()

    def get(self) -> Iterable[str]:
        '''
        Returns all lines of the table. Use self.post() for post-processing.
        '''
        T = '\0 '  # 0-terminator, used for aligning info
        cg = self.__cl.champions.__getitem__
        def cname(c: int) -> str:
            return cg(c)['name']
        for i in range(len(self.__champs)):
            info, rank, cs = self.__ps[i]
            idx = self.__champidx[i]
            name = info['displayName'] + '\t' + rank
            if i == self.__sep:
                yield '\0 ┼' + '\0' * 11
            if not self.__champs[i] or idx is not None and idx > 9:
                yield f'{name}{T}│ {T.join(cname(c["championId"]) for c in cs[:8])}{T}...{T}{cname(self.__champs[i])}{T}'
                pts = cs[idx]['championPoints'] // 1000 if idx else 0
                yield f'{self.__wl[i]}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in cs[:8])}{T}...{T}{pts}K{T}'
            else:
                yield f'{name}{T}│ {T.join(cname(c["championId"]) for c in cs[:10])}{T}'
                yield f'{self.__wl[i]}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in cs[:10])}{T}'

    def clear(self):
        if n := out_sz() - self.__seek:
            out_rm(n)

    def update(self, cids: list[int]):
        '''
        Updates the presented table to match given champ selections
        '''
        while not self.__q.empty():
            i, wl = self.__q.get()
            self.__wl[i] = wl
            self.__champs = []
        if self.__champs != cids:
            self.__champs = cids
            self.__champidx = list(x.get(y)
                                   for x, y in zip(self.__cid2mi, cids))
            self.__show_fn()

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

        def pts(i, x: str):  # line 2: mastery points
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

        def champ(x: str):  # line 1: champ names
            if not self.__champs[j]:
                return g(x)
            key = self.__cl.champions[self.__champs[j]]['name']
            a = x.index(key)
            b = a + len(key)
            return f'{g(x[:a])}{t(x[a:b])}{g(x[b:])}'

        if i % 2:  # odd line idx
            if i == len(self.__champs) * 2 - 1:
                self.clear()
            nwl = x.index(' ')
            wl = ''.join((t if y == '1' else g)('•') for y in x[:nwl])
            return f'{wl}{pts(j, x[nwl:])}'

        m = _prank.search(x)
        def color(y): return _crank[y[0]](y)
        rank = f'{color(m[1]) if m[1] else ""}{cgray(m[2]) if m[2] else ""}{color(m[3]) if m[3] else ""}'
        a, b = m.span()
        return f'{t(x[:a])} {rank}{champ(x[b:])}'
