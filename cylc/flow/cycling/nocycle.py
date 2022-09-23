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
Cycling logic for isolated non-cycling startup and shutdown graphs.
"""

# TODO: scheduler check DB to be sure alpha and omega sections have run or not.

# cycle point values
NOCYCLE_PT_ALPHA = "alpha"
NOCYCLE_PT_OMEGA = "omega"

NOCYCLE_POINTS = (
    NOCYCLE_PT_ALPHA,
    NOCYCLE_PT_OMEGA
)


class NocyclePoint:
    """A string-valued point."""

    def __init__(self, value: str) -> None:
        if value not in [NOCYCLE_PT_ALPHA, NOCYCLE_PT_OMEGA]:
            raise ValueError(f"Illegal Nocycle value {value}")
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return str(other) == self.value

    def __le__(self, other):
        """less than or equal only if equal."""
        return str(other) == self.value

    def __lt__(self, other):
        """never less than."""
        return False

    def __gt__(self, other):
        """never greater than."""
        return False

    def __str__(self):
        return self.value


class NocycleSequence:
    """A single point sequence."""

    def __init__(self, dep_section, p_context_start=None, p_context_stop=None):
        """Workflow cycling context is ignored."""
        self.point = NocyclePoint(dep_section)

    def __hash__(self):
        return hash(str(self.point))

    def is_valid(self, point):
        """Is point on-sequence and in-bounds?"""
        return str(point) == self.point

    def get_first_point(self, point):
        """First point is the only point"""
        return self.point

    def get_next_point(self, point):
        """There is no next point"""
        return None

    def get_next_point_on_sequence(self, point):
        """There is no next point"""
        return None

    def __eq__(self, other):
        try:
            return other.point == self.point
        except AttributeError:
            # (other is not a nocycle sequence)
            return False

    def __str__(self):
        return str(self.point)


NOCYCLE_SEQ_ALPHA = NocycleSequence(NOCYCLE_PT_ALPHA)
NOCYCLE_SEQ_OMEGA = NocycleSequence(NOCYCLE_PT_OMEGA)
