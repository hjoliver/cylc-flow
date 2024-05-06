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
import os
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
from cylc.flow.command_polling import Poller
from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    TASK_OUTPUT_STARTED
)
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_RUNNING
)
from cylc.flow.terminal import cli_function
from cylc.flow.pathutil import get_cylc_run_dir

from metomi.isodatetime.parsers import TimePointParser

if TYPE_CHECKING:
    from optparse import Values


TODO: "finished" (output?)


class WorkflowPoller(Poller):
    """A polling object that checks workflow state."""

    def connect(self):
        """Connect to the workflow db, polling if necessary in case the
        workflow has not been started up yet."""

        # Returns True if connected, otherwise (one-off failed to
        # connect, or max number of polls exhausted) False
        connected = False

        if cylc.flow.flags.verbosity > 0:
            sys.stderr.write(
                "connecting to workflow db for " +
                self.args['run_dir'] + "/" + self.args['workflow_id'])

        # Attempt db connection even if no polls for condition are
        # requested, as failure to connect is useful information.
        max_polls = self.max_polls or 1
        # max_polls*interval is equivalent to a timeout, and we
        # include time taken to connect to the run db in this...
        while not connected:
            self.n_polls += 1
            try:
                self.checker = CylcWorkflowDBChecker(
                    self.args['run_dir'], self.args['workflow_id'])
                connected = True
                # ... but ensure at least one poll after connection:
                self.n_polls -= 1
            except (OSError, sqlite3.Error):
                if self.n_polls >= max_polls:
                    raise
                if cylc.flow.flags.verbosity > 0:
                    sys.stderr.write('.')
                sleep(self.interval)

        if cylc.flow.flags.verbosity > 0:
            sys.stderr.write('\n')

        if connected and self.args['cycle']:
            fmt = self.checker.point_fmt
            if fmt:
                # convert cycle point to DB format
                self.args['cycle'] = str(
                    TimePointParser().parse(
                        self.args['cycle'], fmt
                    )
                )
        return connected, self.args['cycle']

    async def check(self):
        """Return True if desired workflow state achieved, else False"""

        return self.checker.task_state_met(
            self.args['task'],
            self.args['cycle'],
            status=self.args['status'],
            trigger=self.args['trigger'],
            message=self.args['message'],
            flow_num=self.args['flow_num']
        )


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[ID_MULTI_ARG_DOC]
    )

    parser.add_option(
        "-t", "--task", help="Task name to query.",
        metavar="NAME", action="store", dest="task", default=None)

    parser.add_option(
        "-p", "--point", "-c", "--cycle", metavar="POINT",
        help="Task cycle point (deprecated: use task ID).",
        action="store", dest="cycle", default=None)

    parser.add_option(
        "-T", "--task-point",
        help="Take cycle point from job environment (deprecated: just"
             " use $CYLC_TASK_CYCLE_POINT explicitly in job scripting).",
        action="store_true", dest="use_task_point", default=False)

    parser.add_option(
        "-d", "--run-dir",
        help="cylc-run directory location, for workflows owned by others."
             " The database location will be DIR/WORKFLOW_ID/log/db.",
        metavar="DIR", action="store", dest="alt_run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Offset from target cycle point. Can be used"
        " along with --task-point when polling one workflow from another."
        " For example, --offset=PT30M for a 30 minute offset.",
        action="store", dest="offset", metavar="OFFSET", default=None)

    parser.add_option(
        "--old-format",
        help="Print results in legacy comma-separated format.",
        action="store_true", dest="old_format", default=False)

    parser.add_option(
        "-S", "--status", metavar="STATUS",
        help="Task status (deprecated: use task ID)",
        action="store", dest="status", default=None)

    parser.add_option(
        "-O", "--output", metavar="OUTPUT",
        help="Task output (by trigger name, not task message)"
             " (deprecated: use task ID).",
             action="store", dest="trigger", default=None)

    parser.add_option(
        "-m", "--message", metavar="MESSAGE",
        help="Task output message (deprecated: use task trigger).",
        action="store", dest="message", default=None)

    parser.add_option(
        "--flow",
        help="Specify a flow number (default 1).",
        action="store", type="int", dest="flow_num", default=1)

    parser.add_option(
        "--print-outputs",
        help="For non-specific queries print outputs rather than statuses."
             "The default is statuses.",
        action="store_true", dest="print_outputs", default=False)

    WorkflowPoller.add_to_cmd_options(parser)

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', ids: str) -> None:

    if options.use_task_point and options.cycle:
        raise InputError("Use --task-point or --point, not both.")

    if options.use_task_point:
        if "CYLC_TASK_CYCLE_POINT" not in os.environ:
            raise InputError("CYLC_TASK_CYCLE_POINT is not defined.")
        options.cycle = os.environ["CYLC_TASK_CYCLE_POINT"]

    if options.offset and not options.cycle:
        raise InputError("A cycle point is required for --offset.")

    if options.task or options.cycle or options.trigger:
        print(
            "WARNING: --task, --cycle, --status, and --output"
            " are deprecated; use task ID.", file=sys.stderr
        )

    # Attempt to apply specified offset to the targeted cycle
    if options.offset:
        options.cycle = str(add_offset(options.cycle, options.offset))

    workflow_id, tokens, _ = parse_id(
        ids,
        constraint='mixed',
        max_workflows=1,
        max_tasks=1,
        alt_run_dir=options.alt_run_dir
    )

    cycle = options.cycle
    task = options.task
    status = options.status
    trigger = options.trigger

    if tokens is not None:
        # Check for deprecated options along with task ID.
        if tokens["cycle"] is not None:
            if options.cycle:
                raise InputError(
                    "Use --cycle or WORKFLOW//cycle, not both.")
            cycle = tokens["cycle"]

        if tokens["task"] is not None:
            if options.task:
                raise InputError(
                    "Use --task or WORKFLOW//CYCLE/task, not both.")
            task = tokens["task"]

        if tokens["task_sel"] is not None:
            if options.status or options.trigger:
                raise InputError(
                    "Use --status/--outputor"
                    "WORKFLOW//CYCLE/TASK:selector, not both.")
            if tokens["task_sel"] == TASK_STATUS_RUNNING:
                trigger = TASK_OUTPUT_STARTED
            elif tokens["task_sel"] in TASK_OUTPUTS:
                # Standard outputs.
                trigger = tokens["task_sel"]
            elif tokens["task_sel"] in TASK_STATUSES_ORDERED:
                # Task statuses with no corresponding output (waiting).
                status = tokens["task_sel"]
            else:
                # Must be a custom output
                # (--message is required for task message - deprecated)
                trigger = tokens["task_sel"]

    pollargs = {
        'workflow_id': workflow_id,
        'run_dir': get_cylc_run_dir(alt_run_dir=options.alt_run_dir),
        'task': task,
        'cycle': cycle,
        'status': status,
        'trigger': trigger,
        'message': options.message,
        'flow_num': options.flow_num,
    }

    spoller = WorkflowPoller(
        "requested state",
        options.interval,
        options.max_polls,
        args=pollargs,
    )

    connected, formatted_pt = spoller.connect()

    if not connected:
        raise CylcError(f"Cannot connect to the {workflow_id} DB")

    if status and task and cycle:
        spoller.condition = f'status "{status}"'
        if not asyncio.run(spoller.poll()):
            sys.exit(1)

    elif trigger and task and cycle:
        # poll for a task output
        spoller.condition = f'output "{trigger}"'
        if not asyncio.run(spoller.poll()):
            sys.exit(1)

    elif options.message and task and cycle:
        # poll for a task message
        spoller.condition = f'message "{options.message}"'
        if not asyncio.run(spoller.poll()):
            sys.exit(1)

    else:
        # just display query results
        spoller.checker.display_maps(
            spoller.checker.workflow_state_query(
                task=task,
                cycle=formatted_pt,
                status=status,
                trigger=trigger,
                message=options.message,
                flow_num=options.flow_num,
                print_outputs=options.print_outputs,
            ),
            old_format=options.old_format
        )
