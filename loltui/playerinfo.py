import queue
import re
import threading
from itertools import accumulate, chain
from typing import Iterable, Union

from loltui.data import *

#
# Player info presenter
#

_crank = {  # rank colorizers
    'I': colorizer(8),
    'B': colorizer(95),
    'S': colorizer(102),
    'G': colorizer(179),
    'P': colorizer(7),
    'D': colorizer(14),
    'M': colorizer(12),
    'C': colorizer(50)}
class PlayerInfo():
    __prank = re.compile(r'\t(\w\d)?(→)?(\w\d)?')

    def __wl_calc(self):
        for i, wl in enumerate(self.__cl.wins_losses(x[0]) for x in self.__ps):
            if wl:
                self.__q.put((i, wl))

    def __init__(self, client: Client, geom: tuple[int, int],
                 summoner_ids: Iterable[str], show_fn):
        self.__cl = client
        self.__sep = geom[0]
        self.__ps = [client.id2player(x) for x in summoner_ids]
        self.__wl = [[] for _ in self.__ps]
        self.__seek = out_sz()
        self.__champs = []
        self.__show_fn = show_fn
        self.__q = queue.Queue()
        threading.Thread(target=self.__wl_calc, daemon=True).start()

    def __get(self, i: int) -> Union[tuple[str, str], tuple[str, str, str]]:
        T = '\0 '  # 0-terminator, used for aligning info
        (info, rank, champs), idx = self.__ps[i], self.__champidx[i]
        name = info['displayName'] + '\t' + rank
        if not 0 <= idx <= 9:
            champs = champs[:8]
            champs.append({
                'championId': -1,
                'championPoints': -1})
            champs.append({
                'championId': self.__champs[i],
                'championPoints': 0 if idx == -1 else self.__ps[i][2][idx]['championPoints']})
        top = f'{name}{T}│ {T.join(d["name"] if (d := self.__cl.champions.get(c["championId"])) else "..." for c in champs[:10])}{T}'
        bot = f'{"".join("01"[y] for y in self.__wl[i])}{T}│ {T.join(str(c["championPoints"]//1000)+"K" for c in champs[:10])}{T}'
        return (T + '┼' + '\0' * 11, top,
                bot) if i == self.__sep else (top, bot)

    def get(self) -> Iterable[str]:
        '''
        Returns all lines of the table. Use self.post() for post-processing.
        '''
        return chain.from_iterable(map(self.__get, range(len(self.__champs))))

    def clear(self):
        out_rm(-self.__seek)

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
            self.__champidx = [next((i for i, c in enumerate(
                y[2]) if x == c['championId']), -1) for x, y in zip(cids, self.__ps)]
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
            if (m1k := x.find('-1K')) != -1:
                return f'{g(x[:m1k])}   {x[m1k+3:]}'
            b = x.index('K') + 1
            for _ in range(self.__champidx[j]):
                b = x.index('K', b) + 1
            a = x.rindex(' ', 0, b)
            return f'{g(x[:a])}{x[a:b]}{g(x[b:])}'

        def champ(x: str):  # line 1: champ names
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

        m = self.__prank.search(x)
        def color(y): return _crank[y[0]](y)
        rank = f'{color(m[1]) if m[1] else ""}{cgray(m[2]) if m[2] else ""}{color(m[3]) if m[3] else ""}'
        a, b = m.span()
        return f'{t(x[:a])} {rank}{champ(x[b:])}'
