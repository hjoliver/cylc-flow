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

from typing import Dict, Optional, Tuple, Any

from metomi.isodatetime.parsers import TimePointParser

from cylc.flow import LOG
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.workflow_files import infer_latest_run_from_id
from cylc.flow.id import tokenise
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.task_outputs import TASK_OUTPUT_STARTED
from cylc.flow.task_state import (
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUSES_ORDERED
)


def workflow_state(
    remote_id: str,
    offset: Optional[str] = None,
    flow_num: Optional[int] = 1,
    alt_cylc_run_dir: Optional[str] = None,
) -> Tuple[bool, Dict[str, Optional[str]]]:
    """Connect to a workflow DB and query a tasks status or output.

    * Reports satisfied only if the remote workflow state has been achieved.
    * Returns all workflow state args to pass on to triggering tasks.

    Arguments:
        remote_id:
            ID of the workflow[//task] to check.
        offset:
            Interval offset from local to remote cycle point, as an ISO8601
            duration, e.g. PT1H (1 hour).
        flow_num:
            Flow number of remote task.
        alt_cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

            .. note::

               This only needs to be supplied if the workflow is running in a
               different location to what is specified in the global
               configuration (usually ``~/cylc-run``).

    Returns:
        tuple: (satisfied, results)

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            Dictionary of the args / kwargs provided to this xtrigger.

    """
    tokens = tokenise(remote_id)
    workflow_id = infer_latest_run_from_id(
        tokens["workflow"], alt_cylc_run_dir)

    # Failure to connect could mean the target workflow has not started yet,
    # but it could also mean a bad workflow ID, say, so don't hide the error.
    checker = CylcWorkflowDBChecker(
        get_cylc_run_dir(alt_cylc_run_dir),
        workflow_id
    )

    status, output = check_task_selector(
        tokens["task_sel"],
        checker.back_compat_mode
    )

    if offset is not None:
        cycle = str(add_offset(tokens["cycle"], offset))
    else:
        cycle = tokens["cycle"]

    # Point validity can only be checked at run time.
    # Bad function arg templating can cause a syntax error.
    if checker.point_fmt is None:
        # Integer cycling: raises ValueError if bad.
        int(cycle)
    else:
        # Datetime cycling: raises ISO8601SyntaxError if bad
        cycle = str(
            TimePointParser().parse(
                cycle, dump_format=checker.point_fmt
            )
        )

    satisfied: bool = checker.task_state_met(
        tokens["task"],
        cycle,
        trigger=output,
        status=status,
        flow_num=flow_num
    )

    return (
        satisfied,
        {
            'workflow_id': workflow_id,
            'task': tokens["task"],
            'point': str(cycle),
            'offset': str(offset),
            'status': str(status),
            'output': output,
            'flow_num': str(flow_num),
            'cylc_run_dir': alt_cylc_run_dir
        }
    )


def check_task_selector(task_sel, back_compat=False):
    """Determine whether to poll for a status or an output.

    For standard task statuses, poll for the corresponding output instead
    to avoid missing transient statuses between polls.

    """
    status = None
    output = None

    if task_sel is None:
        # Default to succeeded
        status = TASK_STATUS_SUCCEEDED

    elif task_sel == TASK_STATUS_RUNNING:
        # transient running status: use corresponding output "started".
        if back_compat:
            # Cylc 7 only stored custom outputs.
            status = TASK_STATUS_RUNNING
        else:
            output = TASK_OUTPUT_STARTED

    elif task_sel in TASK_STATUSES_ORDERED:
        status = task_sel

    else:
        # Custom output
        output = task_sel

    return (status, output)


def validate(args: Dict[str, Any], Err=WorkflowConfigError):
    """Validate workflow_state xtrigger function args.

    * remote_id: full workflow//cycle/task[:selector]
    * flow_num: must be an integer
    * status: must be a valid status

    """
    tokens = tokenise(args["remote_id"])
    if any(
        tokens[token] is None
        for token in ("workflow", "cycle", "task")
    ):
        raise WorkflowConfigError(
            "Full ID needed: workflow//cycle/task[:selector].")

    try:
        int(args["flow_num"])
    except ValueError:
        raise WorkflowConfigError("flow_num must be an integer.")

    sig = f"workflow_state({args['remote_id']})"
    status, output = check_task_selector(tokens["task_sel"])
    if status is not None:
        LOG.debug(f'xtrigger {sig}:\npoll for status "{status}"')
    else:
        LOG.debug(f'xtrigger {sig}:\npoll for output "{output}"')
