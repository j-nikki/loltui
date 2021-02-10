from loltui.output import *
from loltui.output import _buf

out_init()

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

    def test_box_empty(self):
        assert out_sz() == 0
        box(min_width=0)
        assert _buf[-1] == f'{cgray("╭──╮")}\n{cgray("╰──╯")}'
        box(min_width=1)
        assert _buf[-1] == f'{cgray("╭───╮")}\n{cgray("╰───╯")}'
        out_rm(2)
        assert out_sz() == 0

    def test_box_title(self):
        assert out_sz() == 0
        box(title='åäö', min_width=0)
        assert _buf[-1] == f'{cgray("╭╼åäö╾──╮")}\n{cgray("╰───────╯")}'
        out_rm(2)
        assert out_sz() == 0
