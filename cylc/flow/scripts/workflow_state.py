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

Poll a workflow database for task status or completed outputs until matching
results are found or the maxumum number of polls is reached (see --max-polls
and --interval).

If the database does not exist at first, polls are consumed waiting for it.

In cycle/task:selector the selector is interpreted as a status, except:
  - transient statuses "submitted" and "running" are converted to the
    associated outputs "submitted" and "started", to avoid missing them.
  - status "running" is converted to output "started" to avoid missing it
  - "finished" is supported as an alias for "succeeded or failed"
  - if selector is not a known status it is assumed to be a custom output

Both cycle and task can include "*" to match any sequence of zero or more
characters. Quote the ID to protect it from shell expansion.

In task scripting, to poll the same cycle point in another workflow just use
$CYLC_TASK_CYCLE_POINT in the ID (but see also the workflow_state xtrigger).

NOTES:
  - Tasks are only recorded in the DB once they enter the active window (n=0).
  - Flow numbers are only printed if not the original flow (i.e., if > 1).

WARNINGS:
 - Typos in the workflow or task ID will result in fruitless polling.
 - Avoid polling for "waiting" - it is transient and may be missed.
 - If your system clock is running local time and the target database
   cycle points are UTC, your command line cycle point will be converted
   to UTC before the database is queried.

Examples:

  # Print the status of all tasks in WORKFLOW:
  $ cylc workflow-state WORKFLOW

  # Print the status of all tasks in cycle point 2033:
  $ cylc workflow-state WORKFLOW//2033

  # Print the status of all tasks named foo:
  $ cylc workflow-state WORKFLOW//*/foo

  # Print all succeeded tasks:
  $ cylc workflow-state "WORKFLOW//*/*:succeeded"

  # Print all tasks foo that completed output file1:
  $ cylc workflow-state "WORKFLOW//*/foo:file1"

  # Print if task 2033/foo completed output file1:
  $ cylc workflow-state WORKFLOW//2033/foo:file1
"""

import asyncio
import sqlite3
import sys
from typing import TYPE_CHECKING

from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.id import Tokens
from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import (
    ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow import LOG
from cylc.flow.command_polling import Poller
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import infer_latest_run_from_id

if TYPE_CHECKING:
    from optparse import Values


# TODO: flow=all, none?  Useful for CLI if not xrigger, pt format.

WILDCARD = "*"

# polling defaults
MAX_POLLS = 12
INTERVAL = 5


class WorkflowPoller(Poller):
    """A polling object that queries task states or outputs from a DB."""

    def __init__(
        self, id_, offset, flow_num, alt_cylc_run_dir,
        *args, **kwargs
    ):
        self.id_ = id_
        self.offset = offset
        self.flow_num = flow_num
        self.alt_cylc_run_dir = alt_cylc_run_dir

        self.db_checker = None

        tokens = Tokens(self.id_)

        self.workflow_id_raw = tokens.workflow_id
        self.task_sel = tokens["task_sel"]
        self.cycle = tokens["cycle"]
        self.task = tokens["task"]

        self.status = None
        self.outuput = None
        self.workflow_id = None

        if (
            self.cycle is not None and
            "*" in self.cycle and
            self.offset is not None
        ):
            raise InputError(
                f"Cycle point wildcard ({WILDCARD})"
                " is not compatible with --offset")

        super().__init__(*args, **kwargs)

    def _db_connect(self) -> bool:
        """Find workflow and connect to Db, else return False."""

        if self.workflow_id is None:
            # Workflow not found (maybe not installed or running yet).
            # Can't infer runN until the run dir exists.
            try:
                self.workflow_id = infer_latest_run_from_id(
                    self.workflow_id_raw,
                    self.alt_cylc_run_dir
                )
            except InputError:
                return False

        if self.db_checker is None:
            # DB not connected yet.
            try:
                self.db_checker = CylcWorkflowDBChecker(
                    get_cylc_run_dir(self.alt_cylc_run_dir),
                    self.workflow_id
                )
            except (OSError, sqlite3.Error):
                return False

        # Connected. At first connection:
        # 1. check for status or output? (requires DB compat mode)
        self.status, self.output = self.db_checker.status_or_output(
            self.task_sel,
            default_succeeded=False
        )
        # 2. compute target cycle point (requires DB point format)
        self.cycle = self.db_checker.tweak_cycle_point(self.cycle, self.offset)

        return True

    async def check(self):
        """Return True if desired workflow state achieved, else False.

        Called once per poll by super().

        """
        if self.db_checker is None and not self._db_connect():
            LOG.debug("DB not connected")
            return False

        res = self.db_checker.workflow_state_query(
            self.task, self.cycle, self.status, self.output, self.flow_num,
            self.args["print_outputs"]
        )
        if res:
            # End the polling dot stream and print inferred runN workflow ID.
            sys.stderr.write(f" from {self.workflow_id}:\n")
            self.db_checker.display_maps(
                res, old_format=self.args["old_format"]
            )
        return bool(res)


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[ID_MULTI_ARG_DOC]
    )

    parser.add_option(
        "-d", "--alt-run-dir",
        help="Alternate cylc-run directory, e.g. for others' workflows.",
        metavar="DIR", action="store", dest="alt_cylc_run_dir", default=None)

    parser.add_option(
        "-s", "--offset",
        help="Offset from ID cycle point as an ISO8601 duration, for datetime"
        " cycling (e.g. PT30M for 30 minutes) or an integer interval, for"
        " integer cycling (e.g. P2). Can be used in task job scripts to poll"
        " offset cycle points without doing the cycle arithmetic yourself,"
        " but see also the workflow_state xtrigger).",
        action="store", dest="offset", metavar="DURATION", default=None)

    parser.add_option(
        "--flow",
        help="Flow number, for target tasks.",
        action="store", type="int", dest="flow_num", default=None)

    parser.add_option(
        "--outputs",
        help="For non status-specific queries print completed outputs instead"
             "  of current task statuses.",
        action="store_true", dest="print_outputs", default=False)

    parser.add_option(
        "--old-format",
        help="Print results in legacy comma-separated format.",
        action="store_true", dest="old_format", default=False)

    WorkflowPoller.add_to_cmd_options(
        parser,
        d_interval=INTERVAL,
        d_max_polls=MAX_POLLS
    )

    return parser


@cli_function(get_option_parser, remove_opts=["--db"])
def main(parser: COP, options: 'Values', *ids: str) -> None:

    if len(ids) != 1:
        raise InputError("Please give a single ID")
    id_ = ids[0]

    if options.max_polls == 0:
        raise InputError("max-polls must be at least 1.")

    poller = WorkflowPoller(
        id_,
        options.offset,
        options.flow_num,
        options.alt_cylc_run_dir,
        f'"{id_}"',
        options.interval,
        options.max_polls,
        args={
            "old_format": options.old_format,
            "print_outputs": options.print_outputs
        }
    )

    if not asyncio.run(poller.poll()):
        sys.exit(1)
