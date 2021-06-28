# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Logic for creation, matching, merging, and pruning of flow labels."""

import re
from contextlib import suppress
from string import ascii_letters
from typing import Set, List, TYPE_CHECKING

from cylc.flow import LOG

if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy


class FlowLabelMgr:
    """
    If a new flow is triggered we label it with a single ASCII character.

    One flow can catch up to another, one task at a time: if foo.10 of flow "z"
    can't be spawned because foo.10 of flow "Q" already exists in the task pool
    we re-label foo.10 with 'zQ'. Downstream events can then be considered to
    belong to flows "z", "Q", or "zQ". If "zQ" eventually takes over the whole
    graph we can return redundant characters for use in new flows again (e.g.
    if the flow labels of every task in the pool includes the characters "z"
    and "Q" we can remove "Q" from them all and return it for re-use.

    This implementation provides up to 52 simultaneous original flows (with
    many merging too) with merged flow labels that are just simple strings
    (so, easy to target on the command line, etc.)

    This class does not actually keep track of labels, just the of elements
    (characters) available to create them, and the logic to compare them, etc.

    """
    def __init__(self) -> None:
        """Store available and used label characters."""
        self.chars_avail: Set[str] = set(ascii_letters)
        self.chars_in_use: Set[str] = set()

    def get_new_label(self) -> str:
        """Return a new label, or None if we've run out.

        Raises KeyError if the pool of labels is exhausted.
        """
        label = self.chars_avail.pop()
        self.chars_in_use.add(label)
        return label

    def prune_labels(self, tasks: List["TaskProxy"]) -> None:
        """Prune redundant characters and make them available for new flows."""
        if len(list(self.chars_in_use)) == 1:
            # Don't bother if there's only one flow.
            return
        redundant_chars = set.intersection(
            *[
                set(label) for label in [
                    itask.flow_label for itask in tasks
                ]
            ]
        )
        with suppress(KeyError):
            redundant_chars.pop()  # discard one
        if not redundant_chars:
            return

        LOG.debug(f"Pruning redundant flow label chars: {redundant_chars}")
        # Unmerge label.
        REC = re.compile(f"[{redundant_chars}]")
        for itask in tasks:
            itask.flow_label = REC.sub('', itask.flow_label)

        # Return labels (set) to the pool of available labels.
        for label in redundant_chars:
            with suppress(KeyError):
                self.chars_in_use.remove(label)
            self.chars_avail.add(label)

    @staticmethod
    def merge_labels(label1: str, label2: str) -> str:
        """Return merged label."""
        if label1 == label2:
            return label1
        return ''.join(set(label1).union(set(label2)))

    @staticmethod
    def match_labels(label1: str, label2: str) -> bool:
        """Return True if two labels represent the same flow."""
        return bool(set(label1).intersection(set(label2)))
