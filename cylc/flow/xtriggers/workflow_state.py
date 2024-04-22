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

import sqlite3
from typing import Dict, Optional, Tuple, Any

from metomi.isodatetime.parsers import TimePointParser
from metomi.isodatetime.exceptions import ISO8601SyntaxError

from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.workflow_files import infer_latest_run_from_id
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.task_state import TASK_STATUSES_ALL


def workflow_state(
    workflow: str,
    task: str,
    point: str,
    offset: Optional[str] = None,
    status: Optional[str] = None,
    message: Optional[str] = None,
    output: Optional[str] = None,
    flow_num: Optional[int] = None,
    cylc_run_dir: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Optional[str]]]]:
    """Connect to a workflow DB and query the requested task state.

    * Reports satisfied only if the remote workflow state has been achieved.
    * Returns all workflow state args to pass on to triggering tasks.

    Arguments:
        workflow:
            The workflow to interrogate.
        task:
            The name of the task to query.
        point:
            The cycle point.
        offset:
            The offset between the cycle this xtrigger is used in and the one
            it is querying for as an ISO8601 time duration.
            e.g. PT1H (one hour).
        status:
            The task status required for this xtrigger to be satisfied.
        message:
            (Deprecated) back-compat alias for ``output``
        output:
            The task output required for this xtrigger to be satisfied.
            .. note::

               This cannot be specified in conjunction with ``status``.
        cylc_run_dir:
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
            Dictionary containing the args / kwargs which were provided
            to this xtrigger.

    """
    workflow = infer_latest_run_from_id(workflow, cylc_run_dir)
    cylc_run_dir = get_cylc_run_dir(cylc_run_dir)

    if offset is not None:
        point = str(add_offset(point, offset))

    try:
        checker = CylcWorkflowDBChecker(cylc_run_dir, workflow)
    except (OSError, sqlite3.Error):
        # Failed to connect to DB; target workflow may not be started.
        return (False, None)

    # TODO - HANDLE ERRORS IN THE XTRIGGER FUNC?
    # currently:
    # - we don't distinguish False from exception
    # - therefore we don't log repeated exceptions outside of debug mode.
    
    # Point validity can only be checked at run time.
    if checker.point_fmt is None:
        # Integer cycling
        try:
            int(point)
        except ValueError:
            raise WorkflowConfigError(
                f"Invalid integer 'point' value {point}")
    else:
        try:
            point = str(
                TimePointParser().parse(
                    point, dump_format=checker.point_fmt
                )
            )
        except ISO8601SyntaxError:
            raise WorkflowConfigError(
                f"Invalid ISO8601 'point' value {point}")

    # Back-compat:
    output = output or message

    if not output and not status:
        status = "succeeded"

    satisfied = checker.task_state_met(
        task, point, output=output, status=status
    )

    results = {
        'workflow': workflow,
        'task': task,
        'point': point,
        'offset': offset,
        'status': status,
        'message': output,  # back-compat
        'output': output,
        'flow_num': flow_num,
        'cylc_run_dir': cylc_run_dir
    }
    return satisfied, results


def validate(args: Dict[str, Any]):
    """Validate and manipulate args parsed from the workflow config.

    The rules for args are:
    * output/message: Use one or the other
    * output/status: Use one or the other
    * flow_num: Must be an integer
    * status: Must be a valid status

    """
    message = args['message']
    output = args['output']
    status = args['status']
    flow_num = args['flow_num']

    if message is not None and output is not None:
        raise WorkflowConfigError(
            "'message' is a deprecated alias for 'output' - don't use both"
        )

    output = output or message

    #if output is None and status is None:
    #    raise WorkflowConfigError(
    #        "You must specify one of 'output' or 'status'"
    #    )

    if output is not None and status is not None:
        raise WorkflowConfigError(
            "You must specify one of 'output' or 'status', not both"
        )

    if status is not None and status not in TASK_STATUSES_ALL:
        raise WorkflowConfigError(
            f"Invalid tasks status '{status}'"
        )

    if flow_num is not None and not isinstance(flow_num, int):
        raise WorkflowConfigError(
            "'flow_num' must be an integer"
        )
