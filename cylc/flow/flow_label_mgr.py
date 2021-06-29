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

"""Logic for creation, matching, merging, and pruning of flow labels.

   To avoid "conditional reflow" flows must have labels that unique in the
   lifetime of the workflow.
"""

from string import ascii_letters
from typing import Set


class FlowLabelMgr:
    """ASCII implementation: 52 unique flows, simple strings as merged labels.

    Ongoing workflows with many reflows may need an unbounded model, possibly
    at the cost of making merged labels more difficult to represent.

    A flow can be stopped, or peter out, or catch up to another flow one task
    at a time: if foo.10 of flow "z" can't be spawned because foo.10 of flow
    "Q" already exists in the task pool we re-label foo.10 "zQ". Downstream
    tasks can then be considered to belong to flows "z", "Q", or "zQ".

    Merged flows taking over the whole graph manifest as characters common to
    all flow labels in the task pool. These cannot be pruned to simplify merged
    labels without risking conditional reflow (pruned characters could not be
    recycled anyway: flow labels must be unique for the life of the workflow).

    # Example:
    upstream => bar
    foo | bar => baz

    - foo(z) ran and triggered baz(z), which finished.
    - bar(z) long-running
    - upstream(Q) triggered as reflow, catches up and merges to bar(zQ)
    - pool is now just bar(zQ) running
    - if we pruned 'z', the resulting bar(Q) would trigger baz(Q)
      whereas bar(zQ) would not trigger baz(zQ) because baz(z) ran already.

    This should not be a problem if the main use cases involve starting a new
    flow and stopping the original (e.g. to replace Cylc 7 warm start) or
    re-running sub-graphs that peter out or stop. Otherwise we could allow
    users to order a "reset" of merged labels.

    TODO: trigger a task without reflow any number of times (label None)
    TODO: restart must load chars_avail!


    foo(z) and baz(z) ran
    pool: bar(zQ) is running
    if we prune 'z', bar(Q) will trigger baz(Q)
    where bar(zQ) would not trigger baz(zQ)

    pool: qux(zQ), waz(Q)
    """
    def __init__(self) -> None:
        """Initialize set of available flow label characters."""
        self.chars_avail: Set[str] = set(ascii_letters)

    def get_new_label(self) -> str:
        """Return a new label. Raises KeyError if the pool is exhausted."""
        return self.chars_avail.pop()

    @staticmethod
    def merge_labels(label1: str, label2: str) -> str:
        """Return merged label. Note incoming labels may be merged too."""
        if label1 == label2:
            return label1
        return ''.join(set(label1).union(set(label2)))

    @staticmethod
    def match_labels(label1: str, label2: str) -> bool:
        """Return True if two labels belong to the same flow."""
        return bool(set(label1).intersection(set(label2)))

    # Pruning of common label characters. See comment in class docstring.
    # def prune_labels(self, tasks: List["TaskProxy"]) -> None:
    #     """Prune characters common to all, to simplify merged labels.
    #     This method can be called infrequently by main loop plugin.
    #     """
    #     unique_labels: Set[str] = {
    #         itask.flow_label
    #         for itask in tasks
    #         # Ignore manual trigger without reflow
    #         if itask.flow_label is not None
    #     }
    #     common_chars = set.intersection(
    #         *[set(label) for label in unique_labels]
    #     )
    #     with suppress(KeyError):
    #         common_chars.pop()  # keep one
    #     if not common_chars:
    #         return
    #     LOG.critical(f"Pruning flow label characters {common_chars}")
    #     REC = re.compile(f"[{''.join(common_chars)}]")
    #     for itask in tasks:
    #         itask.flow_label = REC.sub('', itask.flow_label)
