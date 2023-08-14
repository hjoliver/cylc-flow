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

"""cylc reset [OPTIONS] ARGS

Manually (re)set task prerequisites and outputs.

Setting (satisfying) prerequisites contributes to a task's readiness to run.

Setting (completing) outputs contributes to a task's completion, and sets the
corresponding prerequisites of child tasks.

Default: if no outputs or prerequisites are specified, set all required outputs
(note: this won't set the `succeeded` output if success is optional).

Setting an output also sets any implied outputs:
 - started implies submitted
 - succeeded and failed imply started
 - custom outputs and expired do not imply any other outputs

Specify prerequisites in the form "point/task:message".

"""

from functools import partial
from optparse import Values
from json import dumps
from typing import Dict

from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi
from cylc.flow.option_parsers import (
    FULL_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function
from cylc.flow.flow_mgr import (
    add_flow_opts,
    validate_flow_opts
)
from cylc.flow.task_pool import REC_CLI_PREREQ
from cylc.flow.scripts.show import prereqs_and_outputs_query


MUTATION = '''
mutation (
  $wFlows: [WorkflowID]!,
  $tasks: [NamespaceIDGlob]!,
  $prerequisites: [String],
  $outputs: [String],
  $flow: [Flow!],
  $flowWait: Boolean,
  $flowDescr: String,
) {
  reset (
    workflows: $wFlows,
    tasks: $tasks,
    prerequisites: $prerequisites,
    outputs: $outputs,
    flow: $flow,
    flowWait: $flowWait,
    flowDescr: $flowDescr
  ) {
    result
  }
}
'''


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        multiworkflow=True,
        argdoc=[FULL_ID_MULTI_ARG_DOC],
    )

    parser.add_option(
        "-o", "--out", "--output", metavar="OUTPUT(s)",
        help=(
            "Set task outputs completed, along with any implied outputs."
            ' May be "all", to set all required outputs complete.'
            " OUTPUT is the label (as used in the graph) not the associated"
            " message. Multiple use allowed, may be comma separated."
        ),
        action="append", default=None, dest="outputs"
    )

    parser.add_option(
        "-p", "--pre", "--prerequisite", metavar="PREREQUISITE(s)",
        help=(
            "Set task prerequisites satisfied."
            ' May be "all", which is equivalent to "cylc trigger".'
            " Prerequisite format: 'point/task:message'."
            " Multiple use allowed, may be comma separated."
        ),
        action="append", default=None, dest="prerequisites"
    )

    add_flow_opts(parser)
    return parser


def get_prerequisite_opts(options):
    """Convert prerequisite inputs to a single list, and validate.

    This:
       --pre=a -pre=b,c
    is equivalent to this:
       --pre=a,b,c

    Validation: format <point>/<name>:<qualifier>
    """
    if options.prerequisites is None:
        return []

    result = []

    for p in options.prerequisites:
        result += p.split(',')

    for p in result:
        if not REC_CLI_PREREQ.match(p):
            raise InputError(f"Bad prerequisite: {p}")

    return result


async def run(options: 'Values', workflow_id: str, *tokens_list) -> None:
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    mutation_kwargs = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'tasks': [
                tokens.relative_id_with_selectors
                for tokens in tokens_list
            ],
            'outputs': options.outputs,
            'prerequisites': get_prerequisite_opts(options),
            'flow': options.flow,
            'flowWait': options.flow_wait,
            'flowDescr': options.flow_descr
        }
    }

    await pclient.async_request('graphql', mutation_kwargs)

    # Print `cylc show` info as feedback to user.
    # TODO: do this FIRST; the mutation may not (won't?) be done in time.
    opts = Values()
    json_filter: Dict = {}
    opts.json = False
    opts.list_prereqs = False

    result = await prereqs_and_outputs_query(
        workflow_id,
        tokens_list,
        pclient,
        opts,
        json_filter,
    )
    if opts.json:
        print(dumps(json_filter, indent=4))
    else:
        print(result)


@cli_function(get_option_parser)
def main(parser: COP, options: 'Values', *ids) -> None:
    validate_flow_opts(options)
    call_multi(
        partial(run, options),
        *ids,
    )
