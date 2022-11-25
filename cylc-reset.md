
# `cylc reset [options] [TASK(S)]`

Command for manual manipulation of task prerequisites, outputs, and completion.

Replaces `cylc set-outputs` (and the proposed `cylc set-prerequisites`) and
makes `cylc remove` obsolete.


## Background

A "prerequisite" is a dependence on other task outputs, not on xtriggers etc.

A task gets spawned when its first prerequisite is satisfied (or immediately
out to the runahead limit if it has no prerequisites).

To "spawn" means to create a new task proxy in the scheduler task pool. Either
the main pool (aka `n=0` window); or the hidden pool if there are other
unsatisfied prerequisites (this is just how we keep track of partially
satisfied prerequisites).

## Effect of manually setting a prerequisite satisfied

Spawn the target task with the specified prerequisite satisfied; or 
update its prerequisite if already spawned. 


## Effect of manually setting an output to completed

Spawn child tasks that depend on the output, with the corresponding
prerequisite satisfied; or update prerequisites if already spawned.


### Implied outputs

When an output gets completed, we should also complete any implied outputs.
- started implies submitted
- succeeded implies started, and all expected custom outputs
- failed implies started, but not custom outputs

If all expected outputs are complete, the task will be removed as complete.


## Conceptual overlap?

Setting a prerequisite satisfied is not equivalent to setting the corresponding
parent output completed, unless the task is an only child.

Setting a prerequisite satisfied is not equivalent to `cylc trigger`, unless
the task has only one (or only one unsatisfied) prerequisite.


## Command options

`--flow=INT`: flow(s) to attribute spawned tasks. Default: all active flows.
If a task already spawned, merge flows.

`--pre=PRE`: set a single prerequisite to satisfied.

`--pre=all`: set all prerequisites to satisfied. Equivalent to trigger.

`--out=OUT`: set a single output (and any implied outputs) to completed.

`--out=all`: set all *expected* outputs to completed. For optional outputs,
which may be mutually exclusive, use `--out=OUT`.

`--expire/--forget`: allow the scheduler to forget a task (including `n>0`)
without running it and without completing its outputs (or spawning children).


## Questions

Reset completed tasks to waiting?
  - The point of this in Cylc 7 was to set tasks up for running again. In Cylc
    8 every task in the graph is already "set up" for running in that sense.
  - **Not needed**

Reset a failed task to succeeded (or vice versa)?
  - The point of this in Cylc 7 was to allow the scheduler to carry on as if the
    task had succeeded (note downstream tasks might need insertion etc. too).
  - In Cylc 8 we can just tell the scheduler to carry on as if certain
    prerequisites were satisfied or certain outputs completed (which might in
    fact be the case if we fixed something external - but that still doesn't
    mean the failed task actually succeeded). This is more legit from a
    provenance perspective.
  - **Not needed**

Un-satisfying a prerequisite?
  - If the task has already run, there's no point in doing this.
  - If the task has not run yet, this would prevent it from running when ready,
    but that's what hold (or `--expire`) is for.
  - **Not needed**

Un-completing an output?
    - No point, downstream action will already have been triggered.
    - Flow-wait could be an exception (a completed manually-triggered task
      waits for the flow to catch up before spawning on its outputs) but
      expiring the task and trigger anything wanted downsteam expire the... 

## NOTES

- expired doesn't need to be a task state! It would make more sense for it to
  be a task attribute.

- expired needs to be flow-specific

- we probably need another flag in the DB to record manually-reset
  prerequisites and outputs without overwriting earlier data

