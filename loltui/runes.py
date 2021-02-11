import re
from typing import Optional

import requests

from loltui.client import *
from loltui.output import *

_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

_prunetbl = re.compile(
    r'^\s*<table class="perksTableContainerTable">([\s\S]*?)^\s*</table>',
    flags=re.MULTILINE)
_prune = re.compile(r'<div( style="")?.+\n.+?\/([0-9]+)\.png"(.+opacity: ?1)?')

_2style = [{perk: style['id'] for slot in style['slots']
            for perk in slot['perks']} for style in client.get_json('lol-perks/v1/styles')]
_commonperks = [x for x in _2style[0] if x in _2style[1]]
_2style = {k: v for d in _2style for k, v in d.items() if k not in _commonperks}

_2name = {perk['id']: perk['name']
          for perk in client.get_json('lol-perks/v1/perks')}

_cperk = {
    8000: colorizer(
        0, 214), 8100: colorizer(
            0, 160), 8200: colorizer(
                0, 135), 8400: colorizer(
                    0, 70), 8300: colorizer(
                        0, 75)}
_cdef = colorizer(0, 248)

def get_runes(champ: str) -> Optional[list[int]]:
    try:
        resp = requests.get(
            f'https://www.leagueofgraphs.com/champions/runes/{champ.lower()}',
            headers=_headers)
        tbl = _prunetbl.search(resp.content.decode('U8'))[1]
        return [int(m[2]) for m in _prune.finditer(tbl) if m[1] or m[3]]
    except BaseException:
        pass

def apply_runes(name: str, runes: list[int]) -> str:
    data = {
        'current': True,
        'name': f'loltui: {name}',
        'primaryStyleId': _2style[runes[0]],
        'selectedPerkIds': runes,
        'subStyleId': _2style[runes[4]]}
    if page := next((x for x in client.get_json('lol-perks/v1/pages')
                     if x['name'].startswith('loltui: ')), None):
        requests
        resp = client.put(
            f'lol-perks/v1/pages/{page["id"]}',
            data=json.dumps(data))
    else:
        resp = client.post('lol-perks/v1/pages', data=data)
    if resp.status_code // 100 != 2:
        msg = resp.json().get("message", f"code {resp.status_code}")
        return f'Failed to set runes: {cyell(msg)}'
    return " ".join(
        f"{_cperk.get(_2style.get(x), _cdef)(_2name[x])}" for x in runes)
