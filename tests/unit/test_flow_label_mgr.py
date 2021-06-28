
import pytest
from string import ascii_letters
from string import ascii_letters
from cylc.flow.flow_label_mgr import FlowLabelMgr


@pytest.fixture
def get_mgr():
    return FlowLabelMgr()


def test_get_new_label(get_mgr):
    mgr = get_mgr
    assert len(mgr.chars_in_use) == 0
    lbl = mgr.get_new_label()
    assert len(lbl) == 1
    assert len(mgr.chars_in_use) == 1
    assert len(mgr.chars_avail) == len(ascii_letters) - 1


def test_labels_exhausted(get_mgr, monkeypatch):
    mgr = get_mgr
    monkeypatch.setattr(mgr, 'chars_avail', set(['a', 'b']))
    print(mgr.get_new_label())
    print(mgr.get_new_label())
    #print(mgr.get_new_label())
