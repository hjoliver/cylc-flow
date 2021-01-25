# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

"""Cylc task queue."""

from copy import deepcopy
from collections import deque
from typing import List, Set, Dict, Deque

from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import TASK_STATUS_PREPARING


class Limiter:
    def __init__(self, name: str, limit: int, members: Set[str]) -> None:
        """Initialize limiter for active tasks."""
        self.name = name  # limiter name
        self.limit = limit  # max active tasks
        self.members = members  # member task names

    def is_free(self, itask: TaskProxy, active: Dict[str, int]) -> bool:
        """Return True if itask can be released from the queue, else False.

        The "active" arg is a Counter object, for active tasks by name.
        """
        if itask.tdef.name not in self.members:
            return True
        n_active: int = 0
        for mem in self.members:
            n_active += active[mem]
        return n_active < self.limit

    def adopt(self, limiter_name: str, orphans: List[str]) -> None:
        if limiter_name != self.name:
            return
        self.members.update(orphans)


class TaskQueue:
    """Cylc task queue."""
    Q_DEFAULT = 'default'

    def __init__(
            self,
            qconfig: dict,
            all_task_names: List[str],
            descendants: dict
            ) -> None:
        """Configure the task queue.

        Expand family names in the queue config. Ignore unused or undefined
        tasks (they have no impact on limiting).

        """
        self.task_deque: Deque = deque()
        self.limiters: List[Limiter] = []

        queues = deepcopy(qconfig)
        for qname, queue in queues.items():
            qmembers = set()
            if qname == self.Q_DEFAULT:
                # Add all tasks to the default queue.
                qmembers = set(all_task_names)
            else:
                for mem in queue['members']:
                    if mem in descendants:
                        # Family name.
                        for fmem in descendants[mem]:
                            # This includes sub-families.
                            qmembers.add(fmem)
                    else:
                        # Task name.
                        qmembers.add(mem)
            queues[qname]['members'] = qmembers

        for name, config in queues.items():
            if name == "default" and not config['limit']:
                continue
            self.limiters.append(
                Limiter(name, config['limit'], config['members']))

    def add(self, itask: TaskProxy) -> None:
        """Queue tasks."""
        itask.state.reset(is_queued=True)
        itask.reset_manual_trigger()
        self.task_deque.appendleft(itask)

    def get_free_map(self, itask: TaskProxy, active: Dict[str, int]):
        map: dict = {}
        for limiter in self.limiters:
            map[limiter.name] = limiter.is_free(itask, active)
        return map

    def release(self, active: Dict[str, int]) -> List[TaskProxy]:
        """Release queued tasks."""
        released: List[TaskProxy] = []
        rejects: List[TaskProxy] = []
        while True:
            try:
                candidate = self.task_deque.pop()
            except IndexError:
                # Empty: all tasks released or limited.
                break
            free_map = self.get_free_map(candidate, active)
            if not free_map.get("default", True):
                # Global limit exists and reached.
                rejects.append(candidate)
                break
            if all(free_map.values()):
                # Not limited by any groups.
                candidate.state.reset(TASK_STATUS_PREPARING)
                candidate.state.reset(is_queued=False)
                released.append(candidate)
                active.update({candidate.tdef.name: 1})
            else:
                rejects.append(candidate)

        # Re-queue rejected tasks in the original order.
        for itask in reversed(rejects):
            self.task_deque.append(itask)
        return released

    def remove(self, itask):
        try:
            self.task_deque.remove(itask)
        except ValueError:
            pass

    def adopt_orphans(self, orphans: List[str]) -> None:
        for limiter in self.limiters:
            limiter.adopt(self.Q_DEFAULT, orphans)
