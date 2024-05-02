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
    output: Optional[str] = None,
    message: Optional[str] = None,
    flow_num: Optional[int] = 1,
    cylc_run_dir: Optional[str] = None
) -> Tuple[bool, Dict[str, Optional[str]]]:
    """Connect to a workflow DB and query a tasks status or output.

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
        output:
            The task output trigger required for this xtrigger to be satisfied.

            .. note::

               This cannot be specified in conjunction with ``status``.
        message:
            The task output message required for this xtrigger to be satisfied.
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

    # Failure to connect to DB will raise exceptions here.
    # It could mean the target workflow as not started yet,
    # but it could also mean a typo in the workflow ID, so
    # so don't hide the error.
    checker = CylcWorkflowDBChecker(cylc_run_dir, workflow)

    # Point validity can only be checked at run time.
    # Bad function arg templating can cause a syntax error.
    if checker.point_fmt is None:
        # Integer cycling: raises ValueError if bad.
        int(point)
    else:
        # Datetime cycling: raises ISO8601SyntaxError if bad
        point = str(
            TimePointParser().parse(
                point, dump_format=checker.point_fmt
            )
        )

    if not status and not (output or message):
        status = "succeeded"

    satisfied: bool = checker.task_state_met(
        task, point, trigger=output, status=status, flow_num=flow_num
    )

    results = {
        'workflow': workflow,
        'task': task,
        'point': str(point),
        'offset': offset,
        'status': status,
        'output': output,
        'flow_num': str(flow_num),
        'cylc_run_dir': cylc_run_dir
    }
    return satisfied, results


def validate(args: Dict[str, Any]):
    """Validate workflow_state function args from the workflow config.

    The rules for are:
    * output/status: one at most (defaults to succeeded status)
    * flow_num: Must be an integer
    * status: Must be a valid status

    """
    output = args['output']
    status = args['status']
    flow_num = args['flow_num']

    if output is not None and status is not None:
        raise WorkflowConfigError(
            "Give `status` or `output`, not both"
        )

    if status is not None and status not in TASK_STATUSES_ALL:
        raise WorkflowConfigError(
            f"Invalid tasks status '{status}'"
        )

    if flow_num is not None and not isinstance(flow_num, int):
        raise WorkflowConfigError(
            "flow_num must be an integer"
        )
