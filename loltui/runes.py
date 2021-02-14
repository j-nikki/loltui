import re
from itertools import chain, groupby
from operator import itemgetter
from typing import Union

import requests

from loltui.client import client
from loltui.output import *

_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

_prunetbl = re.compile(r'<div class="perk-page__row">([\s\S]+?)</td>')
_prune = re.compile(r'perk(Shard)?\/([0-9]+)\.png\?image=q_auto')

_2style = [[(perk, style['id']) for slot in style['slots'] for perk in slot['perks']]
           for style in client.get_json('lol-perks/v1/styles')]
_commonperks = set(map(itemgetter(0), _2style[0])).intersection(
    map(itemgetter(0), _2style[1]))
_2style = dict(
    chain.from_iterable(filter(lambda x: x[0] not in _commonperks, _2style)))
_2name = {perk['id']: perk['name']
          for perk in client.get_json('lol-perks/v1/perks')}

_cperk = {8000: 214, 8100: 9, 8200: 177, 8400: 154, 8300: 75, None: 251}

def get_runes(champ: str, role: str) -> Union[list[int], str]:
    try:
        resp = requests.get(
            f'https://www.op.gg/champion/{champ}/statistics/{role}/rune',
            headers=_headers)
    except Exception as e:
        return f'Error querying for runes: {cyell(e)}'
    try:
        tbl = _prunetbl.search(resp.content.decode('U8'))[1]
        res = [int(m[2]) for m in _prune.finditer(tbl)]
        if len(res) == 9:
            return res
    except Exception as e:
        return f'Error reading runes: {cyell(e)}'
    return f'Error reading runes: {cyell("unexpected layout")}'

def apply_runes(name: str, runes: Union[list[int], str]) -> list[str]:
    # Return error message
    if isinstance(runes, str):
        return [runes]

    # Build runepage
    s0 = _2style[runes[0]]
    data = {
        'current': True,
        'name': f'loltui: {name}',
        'primaryStyleId': s0,
        'selectedPerkIds': runes,
        'subStyleId': _2style[runes[4]]}

    # Submit to client
    if page := next((x for x in client.get_json('lol-perks/v1/pages')
                     if x['name'].startswith('loltui: ')), None):
        data = json.dumps(data | {'id': page['id']})
        resp = client.put(f'lol-perks/v1/pages/{page["id"]}', data=data)
    else:
        resp = client.post('lol-perks/v1/pages', data=json.dumps(data))
    if resp.status_code // 100 != 2:
        msg = resp.json().get("message", f"code {resp.status_code}")
        return [f'Failed to set runes: {cyell(msg)}']

    # Return string representation
    return [f'{f"{CSI}38;5;{C_GRAY}m, ".join(f"{CSI}38;5;{k}m{_2name[r]}" for r in rs)}{CSI}m' for k, rs in groupby(
        runes, lambda x: _cperk[_2style.get(x)])]
