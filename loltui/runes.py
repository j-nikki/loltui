import re
from typing import Optional

import requests

from loltui.output import *

_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

_prunetbl = re.compile(
    r'^\s*<table class="perksTableContainerTable">([\s\S]*?)^\s*</table>',
    flags=re.MULTILINE)
_prune = re.compile(r'<div( style="")?.+\n.+?alt="([^"]+)"(.+opacity: ?1)?')

def get_runes(champ: str) -> Optional[list[str]]:
    try:
        resp = requests.get(
            f'https://www.leagueofgraphs.com/champions/runes/{champ.lower()}',
            headers=_headers)
        tbl = _prunetbl.search(resp.content.decode('U8'))[1]
        return [m[2] for m in _prune.finditer(tbl) if m[1] or m[3]]
    except Exception as e:
        pass
