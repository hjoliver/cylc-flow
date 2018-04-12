#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
#-------------------------------------------------------------------------------
# Test killing of jobs on a remote host.
CYLC_TEST_IS_GENERIC=false
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
export CYLC_TEST_HOST=$( \
    cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z $CYLC_TEST_HOST ]]; then
    skip_all '"[test battery]remote host": not defined'
fi
N_TESTS=3
set_test_number $N_TESTS
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug --no-detach $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-ps
run_fail $TEST_NAME \
    ${SSH} -n "${CYLC_TEST_HOST}" \
    "bash -c 'ps \$(cat cylc-run/$SUITE_NAME/work/*/t*/file)'"
#-------------------------------------------------------------------------------
purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite $SUITE_NAME
exit
