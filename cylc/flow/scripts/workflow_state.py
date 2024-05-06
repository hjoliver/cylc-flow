#!/usr/bin/env python3

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

r"""cylc workflow-state [OPTIONS] ARGS

Print current task statuses or completed outputs from a workflow database.

NOTE: workflow databases hold all completed outputs, but only the latest task
statuses, so for transient states like "submitted" it is best to check for
the associated output, e.g. --output=submitted rather than --status=submitted.

For specific cycle/task instances, poll until the given status or output is
achieved (command success) or the max number of polls is reached (failure).

Override default polling parameters with --max-polls and --interval.

If the database does not exist at first, polls are consumed waiting for it.

For non-cycling workflows use --point=1 for task-specific (polling) queries.

For less specific queries immediate results are printed (no polling is done).

This command can be used to script polling tasks that trigger off of tasks in
other workflows, but the workflow_state xtrigger is recommended for that.

NOTE: Cylc 7 DBs only recorded custom (not standard) outputs.


        help="Take cycle point from job environment (deprecated: just"
             " use $CYLC_TASK_CYCLE_POINT explicitly in job scripting).",
IDs:
  if selector is matches a standard output, check for outputs not status.
  for --task-point just use CYLC_TASK_ID in the id.

Examples:

  # Print the current or latest status of all tasks:
  $ cylc workflow-state WORKFLOW_ID

  # Print the current or latest status of all tasks named "foo":
  $ cylc workflow-state --task=foo WORKFLOW_ID

  # Print the current or latest status of all tasks in point 2033:
  $ cylc workflow-state --point=2033 WORKFLOW_ID

  # Print all tasks with the current or latest status "succeeded":
  $ cylc workflow-state --status=succeeded WORKFLOW_ID

  # Print all tasks that generated the output "file1":
  $ cylc workflow-state --output="file1" WORKFLOW_ID

  # Print all tasks "foo" that generated the output "file1":
  $ cylc workflow-state --task=foo --output="file1" WORKFLOW_ID

  # POLL UNTIL task 2033/foo succeeds:
  $ cylc workflow-state --task=foo --point=2033 --status=succeeded WORKFLOW_ID

  # POLL UNTIL task 2033/foo generates output "hello":
  $ cylc workflow-state --task=foo --point=2033 --output="hello" WORKFLOW_ID
"""

import asyncio
import sqlite3
import sys
from time import sleep
from typing import TYPE_CHECKING

from cylc.flow.exceptions import CylcError, InputError
import cylc.flow.flags
from cylc.flow.option_parsers import (
    ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.id_cli import parse_id
from cylc.flow.command_polling import Poller
from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.terminal import cli_function
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.xtriggers.workflow_state import check_task_selector

from metomi.isodatetime.parsers import TimePointParser

if TYPE_CHECKING:
    from optparse import Values


# TODO: "finished" (output?)


class WorkflowPoller(Poller):
    """A polling object that checks workflow state."""

    def format_pt_for_db(self, db_checker):
        """Convert cycle point to target DB format."""

        self.checker = db_checker
        if self.args['cycle']:
            fmt = self.checker.point_fmt
            if fmt:
                # convert cycle point to DB format
                self.args['cycle'] = str(
                    TimePointParser().parse(
                        self.args['cycle'], fmt
                    )
                )
        return self.args['cycle']

    async def check(self):
        """Return True if desired workflow state achieved, else False"""

        return self.checker.task_state_met(
            self.args['task'],
            self.args['cycle'],
            status=self.args['status'],
            output=self.args['output'],
            flow_num=self.args['flow_num']
        )


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[ID_MULTI_ARG_DOC]
    )

    parser.add_option(
        "-d", "--alt-run-dir",
        help="Alternate cylc-run directory, e.g. for others' workflows.",
        metavar="DIR", action="store", dest="alt_run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Offset from given cycle point as an ISO8601 duration."
        " For example, --offset=PT30M for a 30 minute offset.",
        action="store", dest="offset", metavar="OFFSET", default=None)

    parser.add_option(
        "--flow",
        help="Specify a flow number (default 1).",
        action="store", type="int", dest="flow_num", default=1)

    parser.add_option(
        "--print-outputs",
        help="For non-specific queries, print completed outputs."
             " The default is to print current task statuses.",
        action="store_true", dest="print_outputs", default=False)

    parser.add_option(
        "--old-format",
        help="Print results in legacy comma-separated format.",
        action="store_true", dest="old_format", default=False)

    WorkflowPoller.add_to_cmd_options(parser)

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', ids: str) -> None:

    workflow_id, tokens, _ = parse_id(
        ids,
        constraint='mixed',
        max_workflows=1,
        max_tasks=1,
        alt_run_dir=options.alt_run_dir
    )

    # Attempt db connection even if no polls for condition are
    # requested, as failure to connect is useful information.
    max_polls = options.max_polls or 1

    # max_polls*interval is equivalent to a timeout, and we
    # include time taken to connect to the run db in this...
    connected = False
    n_attempts = 0

    cylc_run_dir = get_cylc_run_dir(options.alt_run_dir)

    sys.stderr.write(f"Connecting to {workflow_id} DB: ")
    while not connected:
        n_attempts += 1
        try:
            db_checker = CylcWorkflowDBChecker(
                cylc_run_dir, workflow_id)
        except (OSError, sqlite3.Error):
            if n_attempts >= max_polls:
                raise
            sys.stderr.write(".")
            sys.stderr.flush()
            sleep(options.interval)
        else:
            connected = True
            # ... but ensure at least one poll after connection:
            n_attempts -= 1

    if not connected:
        raise CylcError(f"Did not in {max_polls} polls")

    if tokens:
        cycle = tokens["cycle"]
        task = tokens["task"]
        status, output = check_task_selector(
            tokens["task_sel"], db_checker.back_compat_mode)
    else:
        cycle = None
        task = None

    # Attempt to apply specified offset to the targeted cycle
    if options.offset:
        cycle = str(add_offset(cycle, options.offset))

    spoller = WorkflowPoller(
        "requested state",
        options.interval,
        max_polls - n_attempts,  # subtract polls used to connect
        args={
            'workflow_id': workflow_id,
            'run_dir': cylc_run_dir,
            'task': task,
            'cycle': cycle,
            'status': status,
            'trigger': output,
            'flow_num': options.flow_num,
        }
    )

    formatted_pt = spoller.format_pt_for_db(db_checker)

    if status and tokens["task"] is not None and tokens["cycle"] is not None:
        spoller.condition = f'status "{status}"'
        if not asyncio.run(spoller.poll()):
            sys.exit(1)

    elif output and tokens["task"] is not None and tokens["cycle"] is not None:
        spoller.condition = f'output "{output}"'
        if not asyncio.run(spoller.poll()):
            sys.exit(1)

    else:
        # just display query results
        spoller.checker.display_maps(
            spoller.checker.workflow_state_query(
                task=tokens["task"],
                cycle=formatted_pt,
                status=status,
                output=output,
                flow_num=options.flow_num,
                print_outputs=options.print_outputs,
            ),
            old_format=options.old_format
        )
