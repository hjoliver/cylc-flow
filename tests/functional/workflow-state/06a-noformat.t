#!/usr/bin/env bash
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

# Test "cylc workflow-state" cycle point format conversion, when the target workflow
# sets no explicit cycle point format, and the CLI does (the reverse of 06.t).
. "$(dirname "$0")/test_header"

set_test_number 5

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = True
    # (Use default cycle point format)
[scheduling]
    initial cycle point = 20100101T0000Z
[[graph]]
    R1 = foo
[runtime]
    [[foo]]
        script = true
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach "${WORKFLOW_NAME}"

TEST_NAME=${TEST_NAME_BASE}-cli-poll
run_ok "${TEST_NAME}" cylc workflow-state "${WORKFLOW_NAME}" -p 2010-01-01T00:00Z \
        --task=foo --status=succeeded
contains_ok "${TEST_NAME}.stdout" <<__OUT__
polling for 'succeeded': satisfied
__OUT__

TEST_NAME=${TEST_NAME_BASE}-cli-dump
run_ok "${TEST_NAME}" cylc workflow-state "${WORKFLOW_NAME}" -p 2010-01-01T00:00Z
contains_ok "${TEST_NAME}.stdout" <<__OUT__
foo, 20100101T0000Z, succeeded, [1]
__OUT__

purge

