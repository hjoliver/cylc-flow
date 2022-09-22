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

"""
No-cycle logic for isolated start-up and shutdown graphs.
"""

NOCYCLE_STARTUP = "startup"
NOCYCLE_SHUTDOWN = "shutdown"

NOCYCLE_GRAPHS = (
    NOCYCLE_STARTUP,
    NOCYCLE_SHUTDOWN
)


class NocyclePoint:
    """A string-valued no-cycle point."""

    def __init__(self, value: str) -> None:
        if value not in NOCYCLE_GRAPHS:
            raise ValueError(f"Illegal Nocycle value {value}")
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return other.value == self.value

    def __le__(self, other):
        return str(other) == str(self.value)

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __str__(self):
        return self.value


class NocycleSequence:
    """A no-cycle sequence is just a point."""

    def __init__(self, dep_section, p_context_start=None, p_context_stop=None):
        """blah"""
        self.point = NocyclePoint(dep_section)

    def is_valid(self, point):
        """Is point on-sequence and in-bounds?"""
        return True

    def get_first_point(self, point):
        """blah"""
        return None

    def get_next_point_on_sequence(self, point):
        """blah"""
        return self.point

    def __hash__(self):
        return hash(str(self.point))

    def __eq__(self, other):
        return other.point == self.point

    def __str__(self):
        return str(self.point)


NOCYCLE_STARTUP_SEQUENCE = NocycleSequence(NOCYCLE_STARTUP)
NOCYCLE_SHUTDOWN_SEQUENCE = NocycleSequence(NOCYCLE_SHUTDOWN)
