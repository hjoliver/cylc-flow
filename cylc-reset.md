
# `cylc reset [options] [TASK(S)]`

Command for manual manipulation of task prerequisites and outputs.

- Replaces `cylc set-outputs`, and the proposed `cylc set-prerequisites`
- Makes `cylc remove` obsolete

## Background

A "prerequisite" is a dependence on other task outputs, not on xtriggers etc.

A task gets spawned when its first prerequisite gets satisfied (or immediately,
out to the runahead limit, if it has no prerequisites at all).

To "spawn" means to create a new task proxy in the scheduler task pool. Either
the main pool, if all of the prerequisites are satisfied; or the hidden pool if
they are only partially satisfied (hidden tasks are not considered "real" yet,
they're just a way to keep track of partially satisfied prerequisites).

## Effect of manually setting a prerequisite

This spawns the target task with the specified prerequisite satisfied. Or if
the task was already spawned, it just updates its prerequisites.

## Effect of manually setting an output

This spawns downstream child tasks that depend on the specified output, with
their corresponding prerequisites satisfied. Or if any of the child tasks were
already spawned, it just updates their prerequisites.

### Implied outputs

Implied outputs should also be set, e.g.:
- started implies submitted
- custom outputs imply started and submitted
- failed implies started and submitted (but not custom outputs)
- succeeded implies expected custom outputs, plus started and submitted

(See Questions below, for possibly unsetting implied outputs)

If all expected outputs are completed, the task will be removed as complete.


## Overlapping concepts?

Setting a prerequisite satisfied in a target task is not equivalent to `cylc
trigger` unless the task has only one (unsatisfied) prerequisite.

Setting a prerequisite satisfied in a target task is not equivalent to setting
the corresponding parent output completed unless the task is an only child.



## [options]:

`--flow=INT`: flow to which spawned tasks belong. By default, all current flow
numbers. If the target task is already spawned, merge flows.

`--pre=PRE`: set a single prerequisite PRE to satisfied.

`--pre=all`: set all prerequisites satisfied (equivalent to `cylc trigger`).

`--out=OUT`: set a single output `OUT` (and any implied outputs) to completed.

`--out=all`: set all *expected* outputs to complete. For optional outputs
(which may be mutually exclusive) use `--out`.

## Questions

### 1. should we have "state reset"?

We could sort of emulate the old reset state behaviour with `cylc reset
--state=STATE`, by translating STATE to the prerequisites and outputs, and
updating the task state in the DB too.

However, I'm keen to promote the idea we don't (e.g.) reset a failed task to
succeeded; instead we tell the scheduler to carrying on as if certain outputs
had been completed. Then, the DB will better record what really happened
(although perhaps we need to add additional flags to the DB to help interpret
e.g. an incomplete failed task that got its expected outputs "completed"
manually).

### 2. unsetting implied outputs?

- e.g. submitted implies submit-failed should be unset
- however, note that unsetting an output has no effect, and seems to contradict 1.? 
