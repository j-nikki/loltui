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
