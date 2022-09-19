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

import errno
import os
import sqlite3
import sys
from typing import Optional
from textwrap import dedent

from cylc.flow.pathutil import expand_path
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.task_state import (
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED
)
from cylc.flow.util import deserialise


class CylcWorkflowDBChecker:
    """Object for querying a workflow database."""
    STATE_ALIASES = {
        'finish': [
            TASK_STATUS_FAILED,
            TASK_STATUS_SUCCEEDED
        ],
        'start': [
            TASK_STATUS_RUNNING,
            TASK_STATUS_SUCCEEDED,
            TASK_STATUS_FAILED
        ],
        'submit': [
            TASK_STATUS_SUBMITTED,
            TASK_STATUS_RUNNING,
            TASK_STATUS_SUCCEEDED,
            TASK_STATUS_FAILED
        ],
        'fail': [
            TASK_STATUS_FAILED
        ],
        'succeed': [
            TASK_STATUS_SUCCEEDED
        ],
    }

    def __init__(self, rund, workflow, db_path=None):
        # (Explicit dp_path arg is to make testing easier).
        if db_path is None:
            # Infer DB path from workflow name and run dir.
            db_path = expand_path(
                rund, workflow, "log", CylcWorkflowDAO.DB_FILE_BASE_NAME
            )
        if not os.path.exists(db_path):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), db_path)
        self.conn = sqlite3.connect(db_path, timeout=10.0)

        # Get workflow point format.
        try:
            self.point_fmt = self._get_pt_fmt()
            self.back_compat_mode = False
        except sqlite3.OperationalError as exc:
            # BACK COMPAT: Cylc 7 DB (see method below).
            try:
                self.point_fmt = self._get_pt_fmt_compat()
                self.back_compat_mode = True
            except sqlite3.OperationalError:
                raise exc  # original error

    @staticmethod
    def display_maps(res):
        if not res:
            sys.stderr.write("INFO: No results to display.\n")
        else:
            for row in res:
                sys.stdout.write((", ").join([str(s) for s in row]) + "\n")

    def _get_pt_fmt(self):
        """Query a workflow database for a 'cycle point format' entry"""
        for row in self.conn.execute(dedent(
            rf'''
                SELECT
                    value
                FROM
                    {CylcWorkflowDAO.TABLE_WORKFLOW_PARAMS}
                WHERE
                    key==?
            '''),  # nosec (table name is code constant)
            ['cycle_point_format']
        ):
            return row[0]

    def _get_pt_fmt_compat(self):
        """Query a Cylc 7 suite database for 'cycle point format'."""
        # BACK COMPAT: Cylc 7 DB
        # Workflows parameters table name change.
        # from:
        #    8.0.x
        # to:
        #    8.1.x
        # remove at:
        #    8.x
        for row in self.conn.execute(
            rf'''
                SELECT
                    value
                FROM
                    {CylcWorkflowDAO.TABLE_SUITE_PARAMS}
                WHERE
                    key==?
            ''',  # nosec (table name is code constant)
            ['cycle_point_format']
        ):
            return row[0]

    def state_lookup(self, state):
        """Allows for multiple states to be searched via a status alias."""
        if state in self.STATE_ALIASES:
            return self.STATE_ALIASES[state]
        else:
            return [state]

    def workflow_state_query(
        self,
        task: Optional[str] = None,
        cycle: Optional[str] = None,
        status: Optional[str] = None,
        output: Optional[str] = None,
        flow_num: Optional[int] = None
    ):
        """Query task status or outputs in workflow database.

        Returns a list of data for tasks with matching status or output:
        For a status query:
           [(name, cycle, status, serialised-flows), ...]
        For an output query:
           [(name, cycle, serialised-outputs, serialised-flows), ...]

        If all args are None, print the whole task_states table.

        NOTE: the task_states table holds the latest state only, so querying
        (e.g.) submitted will fail for a task that is running or finished.

        Query cycle=2023, status=succeeded:
           [[foo, 2023, succeeded], [bar, 2023, succeeded]]

        Query task=foo, message="file ready":
           [[foo, 2023, "file ready"], [foo, 2024, "file ready"]]

        Query task=foo, point=2023, message="file ready":
           [[foo, 2023, "file ready"]]

        """
        stmt_args = []
        stmt_wheres = []

        # TODO: back compat flow_nums DB
        if output:
            target_table = CylcWorkflowDAO.TABLE_TASK_OUTPUTS
            mask = "name, cycle, outputs, flow_nums"
        else:
            target_table = CylcWorkflowDAO.TABLE_TASK_STATES
            mask = "name, cycle, status, flow_nums"

        stmt = dedent(rf'''
            SELECT
                {mask}
            FROM
                {target_table}
        ''')  # nosec
        # * mask is hardcoded
        # * target_table is a code constant

        # Select from DB by name, cycle, status.
        # (But not by output or flow - they are serialised lists).
        if task:
            stmt_wheres.append("name==?")
            stmt_args.append(task)

        if cycle:
            stmt_wheres.append("cycle==?")
            stmt_args.append(cycle)

        if status:
            stmt_frags = []
            for state in self.state_lookup(status):
                stmt_args.append(state)
                stmt_frags.append("status==?")
            stmt_wheres.append("(" + (" OR ").join(stmt_frags) + ")")

        if stmt_wheres:
            stmt += "WHERE\n    " + (" AND ").join(stmt_wheres)

        if status:
            stmt += dedent("""
                ORDER BY
                    submit_num
            """)

        # idx_status = 2
        # idx_flow = 3

        # TODO option to list outputs instead of status
        # TODO if flows not specified, use the most recent for the task

        res = []
        for row in self.conn.execute(stmt, stmt_args):
            if row[2] is None:
                # status can be None in Cylc 7 DBs
                continue
            flow_nums = deserialise(row[3])
            if flow_num is not None and flow_num not in flow_nums:
                continue
            res.append(list(row))

        if output:
            # Replace res with a task-states like result,
            # [[foo, 2032, output], [foo, 2033, output]]
            if self.back_compat_mode:
                # Cylc 7 DB: list of {output: message}
                results = [
                    [item[0], item[1], output]
                    for item in res
                    if output in deserialise(item[2]).values()
                ]
            else:
                # Cylc 8 DB list of [output]
                results = []
                for name, cycle, outputs_str, flows_str in res:
                    flows = deserialise(flows_str)
                    outputs = deserialise(outputs_str)
                    if output not in outputs:
                        continue
                    results.append([name, cycle, output, flows])
        else:
            results = res
        return results

    def task_state_met(
        self,
        task: str,
        cycle: str,
        status: Optional[str] = None,
        output: Optional[str] = None,
        flow_num: int = None
    ):
        """Return True if cycle/task has achieved status or output.

        Call when polling for a status or output message.

        """
        return bool(
            self.workflow_state_query(task, cycle, status, output, flow_num)
        )
