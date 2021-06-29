
import pytest
from copy import copy
from cylc.flow.flow_label_mgr import FlowLabelMgr


LABEL_CHARS = {'a', 'b'}


@pytest.fixture
def get_mgr(monkeypatch):
    """Create a FlowLabelMgr with limited label chars available."""
    mgr = FlowLabelMgr()
    monkeypatch.setattr(mgr, 'chars_avail', copy(LABEL_CHARS))
    return mgr


def test_get_new_label(get_mgr):
    mgr = get_mgr
    lbl = mgr.get_new_label()
    assert len(lbl) == 1
    assert len(mgr.chars_in_use) == 1
    assert len(mgr.chars_avail) == len(LABEL_CHARS) - 1


def test_labels_exhausted(get_mgr):
    mgr = get_mgr
    mgr.get_new_label()
    mgr.get_new_label()
    with pytest.raises(KeyError):
        mgr.get_new_label()

