from loltui.output import *
from loltui.output import _buf

class TestOutput:

    def test_sz(self):
        assert out_sz() == 0
        out('.')
        assert out_sz() == 1
        out('.')
        out('.')
        assert out_sz() == 3
        out_rm(2)
        assert out_sz() == 1
        out_rm()
        assert out_sz() == 0

    def test_colorizer(self):
        assert colorizer(42)('asd') == f'\033[38;5;42masd\033[m'
        assert colorizer(42, 42)(
            'asd') == f'\033[38;5;42m\033[48;5;42masd\033[m'

    def test_box_empty(self):
        assert out_sz() == 0
        box()
        assert _buf == [cgray('╭──╮'), cgray('╰──╯')]
        out_rm(2)
        assert out_sz() == 0

    def test_box_title(self):
        assert out_sz() == 0
        box(title='åäö')
        assert _buf == [cgray('╭╼åäö╾╮'), cgray('╰─────╯')]
        out_rm(2)
        assert out_sz() == 0

    def test_box_align(self):
        assert out_sz() == 0
        box('     a\0', '\0b\0', '\0\0c')
        assert out_sz() == 5
        a_idx = _buf[-4].index('a')
        b_idx = _buf[-3].index('b')
        c_idx = _buf[-2].index('c')
        assert b_idx == a_idx + 1
        assert c_idx == b_idx + 1
        out_rm(5)
        assert out_sz() == 0
        box('\0a\0b\0c', '\0\0b\0c', '\0\0\0c')
        assert out_sz() == 5
        a_idx = _buf[-4].index('a')
        b_idx = _buf[-3].index('b')
        c_idx = _buf[-2].index('c')
        start = len(f'{cgray("│")} ')
        assert a_idx == start
        assert b_idx == start + 1
        assert c_idx == start + 2
        out_rm(5)
        assert out_sz() == 0


    def test_box_post(self):
        assert out_sz() == 0
        box(*'abc', post=lambda i, x: f'{i}{x}')
        assert out_sz() == 5
        assert _buf[1:4] == [f'{cgray("│")} 0a {cgray("│")}',
                             f'{cgray("│")} 1b {cgray("│")}',
                             f'{cgray("│")} 2c {cgray("│")}']
        out_rm(5)
        assert out_sz() == 0
