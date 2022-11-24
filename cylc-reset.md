
# `cylc reset [options] [TASK(S)]`

Command for manual manipulation of task prerequisites and outputs.

This replaces:
- `cylc set-outputs`
- (and the proposed `cylc set-prerequisites`)
- and removes the need for `cylc remove`

Background:
- "prerequisite" means dependence on other tasks, not on xtriggers etc.
- a task spawns when its first prerequisite gets satisfied (or if it has no
  prerequisites at all)
- spawned tasks with any unsatisfied prerequisites are hidden from users;
  this is merely a way to keep track of prerequisites

Note:
- we need the ability to set task outputs
  - to spawn all downstream tasks with the corresponding prerequisites satisfied
- we need the ability to set task prerequisites
  - to spawn individual tasks - their parents may have other children too
  - not the same as trigger - they may have other unsatisfied prerequisites
- if the action results in all expected outputs being completed, the task is
  considered complete and will be removed automatically

### [options]:

`--flow=N`: attribute action to a flow (default: all current flows)
- if the action targets an existing task proxy, merge flows

`--pre=<PRE>`: set a single prerequisite as satisfied
- effect: spawn or update target task, with `<PRE>` satisfied

`--pre=all`: set all prequisites satisfied
- effect: same as `cylc trigger`

`--out=<OUT>`: set <OUT>, and any prior expected outputs, as completed
- effect: spawn or update downstream tasks, with prerequisite on `<OUT>` (and
  priors) satisfied
- priors: e.g. `succeeded` and `failed` imply `submitted` and `started`; 

`--out=all`: set all *expected* outputs to complete
- effect: same as `--output` for each expected output
- for optional outputs, which may be mutually exclusive, use `--output`

`--state=<STATE>`: alias for `--output=<OUTPUT>` for equivalent output (and
prior expected outputs)
