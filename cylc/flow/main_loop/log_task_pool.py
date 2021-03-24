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
"""Log the task pool content of a running scheduler over time.

.. note::

   This plugin is for Cylc developers debugging the scheduler task pool.
   Run with an interval of zero to log every main loop iteration.

.. warning::
   
   You should probably avoid running this with huge workflows.

"""

from cylc.flow.main_loop import periodic
from cylc.flow import LOG

@periodic
async def log_task_pool(scheduler, state):
    """Log current task pool content"""
    msg = "Task pool content:"
    for itask in scheduler.pool.get_tasks():
        held = queued = ""
        if itask.state.is_held:
            held = " (held)"
        if itask.state.is_queued:
            queued = " (queued)"
        msg += f"\n - {itask.identity}{held}{queued}"  
    LOG.critical(msg) 
