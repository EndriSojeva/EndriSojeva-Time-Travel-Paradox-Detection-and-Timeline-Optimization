# Methodology

Author: Endri Sojeva. Deadline: December 1, 2026.

## Timeline model

`Event` is an immutable record keyed by a unique nonblank ID. `time` is a finite
numeric year or timestamp on a common scale. The optional location, affected
entities, state assertions, importance, edit cost and status carry context.
A `StateChange` asserts an affected entity's attribute and value after an event.
Status is `planned`, `occurred` or `prevented`. It is stored as evidence for future
rules. It does not change causal links on its own. Importance and edit costs are
finite and nonnegative. Importance is descriptive and does not determine edit cost.

`build_graph` stores events as nodes and dependencies as directed edges. An edge
points from cause to effect. `causal` edges may be simultaneous or forward in time.
`time_travel` edges require an earlier target. When legacy input omits the kind,
the builder infers it from the endpoint times. Existing edge kinds are preserved
on rescheduling, and a time change that violates a kind is rejected. Each ordered
pair can have one edge. Parallel dependencies, calendars and propagation of state
assertions are outside this model.

## Operations and costs

All operations in `timetravel.operations` take a graph from `build_graph`. A valid
operation returns `OperationResult(graph, record)` with a deep copy and its cost.
A rejected operation raises `ValueError` and leaves the input unchanged. Graphs
returned by the API can be used for independent branches. Each edit appends an
immutable record to `graph.graph['timeline_history']`, including before and after
values where applicable and the relations removed by a cascade. This is an audit
trail for the branch. Direct changes to NetworkX dictionaries bypass the model.

| Operation and inputs | Validation and effect | Charged cost |
| --- | --- | --- |
| `add_event(event)` | Requires an unused ID. Adds the node. | New event cost |
| `modify_event(event)` | Requires its ID to exist. Replaces modeled fields and revalidates incident edges. | Previous event cost |
| `reschedule_event(id, time)` | Requires an existing ID, a finite time and valid incident edges. Changes the time only. | Previous event cost |
| `remove_event(id)` | Requires an existing ID. Removes the node and its edges, cancelling associated named trips. | Previous event cost, inclusive of the cascade |
| `add_relation(relation)` | Requires existing endpoints, a valid kind for their times and an unused directed pair. | New relation cost |
| `modify_relation(relation, previous_endpoints=...)` | Requires an existing edge. Updates its cost, kind or endpoints. Omitted kind preserves the old kind. A named trip must retain a backward edge. | Previous relation cost |
| `remove_relation(source, target)` | Requires an existing edge. Removes it and cancels any associated named trip. | Previous relation cost |
| `travel_to_past(action_id, source, target, cost=1)` | Requires an unused action ID, existing departure and arrival, an earlier arrival and an unused pair. Adds a named backward edge. | Supplied cost, also stored on the new edge |
| `cancel_travel(action_id, cost=1)` | Requires an active named trip. Removes its edge and records cancellation. | Supplied cost |
| `prevent_travel(action_id, cost=1)` | Requires an unused action ID. Reserves it as prevented without creating an edge. | Supplied cost |

Action IDs are scoped to a branch and cannot be reused after cancellation or
prevention. Travel links existing events. Cancellation removes the travel link
without reversing other edits or deleting its endpoints. Prevention reserves a
named action. It does not forbid all possible links between the same endpoints.
Unnamed backward edges can be removed with `remove_relation`.

```python
from timetravel.graph import build_graph
from timetravel.models import Event
from timetravel.operations import cancel_travel, travel_to_past

original = build_graph([Event("arrival", "Arrival", 1840),
                        Event("departure", "Departure", 1920)], [])
trip = travel_to_past(original, "trip-1", "departure", "arrival", cost=2)
alternative = cancel_travel(trip.graph, "trip-1")
assert trip.graph.has_edge("departure", "arrival")
assert not alternative.graph.has_edge("departure", "arrival")
```

`TimelineConstraint` defines the rule interface. A `ConstraintViolation`
can carry a causal or logical classification, responsible event IDs and directed
relation evidence. The example files illustrate results under the declared rules.

Run the focused tests with `python -m pytest tests/test_graph.py tests/test_constraints.py`
or the full suite with `python -m pytest` from the configured environment.

## Detection and consistency
Iterative DFS tracks the active path and returns its closed suffix when an edge
leads to an active vertex. Iterative Tarjan tracks discovery indices, low-link
values and a stack of unassigned vertices to identify SCCs. A component is cyclic
if it contains multiple vertices or a self-loop. The report returns one DFS
witness per cyclic component, including directed edges. Traversal follows graph
insertion order, so repeated analysis of the same ordered input gives the same
output. Reordering equivalent input may change witnesses or presentation order.

A timeline is consistent when its evaluated rules return no violations. A cycle
or backward edge is structural evidence. Apply these rules independently:

- **Exclusive state.** Occurred events may assert only one distinct value for
  each `(time, entity, attribute)` key. Different times and events that have yet
  to occur do not produce competing assertions for that key.
- **Causal prerequisite.** Every declared incoming edge of an occurred event
  requires an occurred source. A planned or prevented source is reported with
  its effect and the responsible edge.
- **Active travel.** A named active trip requires two occurred endpoints and
  its recorded edge. Prevented and cancelled trips do not assert an active trip.
- **Explicit prerequisites and required events.** A JSON `prerequisites` item
  declares `event_id` and `required_event_id`. If the dependent occurred, its
  prerequisite must exist and have occurred, even when an edit removed the edge
  or prerequisite node. `required_events` is a list of IDs whose occurrence is
  mandatory without a dependent. A recorded status of `planned` is insufficient
  for these rules. These are scenario declarations, not inferred physics.

For the fictional grandfather paradox, the traveler interferes before the family
is founded. The scenario encodes the negative outcome as `e0` (ancestor survival)
being prevented. `e1` (birth) still claims occurrence and depends on `e0` by edge.
`e2` (departure) also explicitly requires `e0`. The report identifies the loop,
the failed causal dependency and the failed existence prerequisite. The loop
with revision A at both dates is consistent. The two incompatible beacon
assertions at the same year produce a contradiction in an acyclic graph.

```python
from pathlib import Path
from timetravel.detection import detect_paradoxes
from timetravel.scenarios import load_scenario

scenario = load_scenario(Path("data/examples/grandfather_paradox.json"))
report = detect_paradoxes(scenario.graph, scenario.constraints)
assert len(report.cycles) == 1 and not report.consistent
```

The report keeps SCCs and witnesses separate from rule violations and provides
event IDs, rule IDs, explanations and relevant edges for candidate repair.
Passing `[]` as the rules requests structural analysis only. The model does
not propagate world state between timestamps or infer unrecorded occurrences.
Default rules are read-only. Extension rules are expected to follow that contract.
Tests compare SCCs with NetworkX on 18 seeded graphs and check a 2,500-node chain
and cycle without recursion. Notebook 02 produces a table and graphs for the
four structural and logical outcomes. These are correctness demonstrations.

## Planned repair and experiments

Use the operations and consistency rules above when evaluating candidate edits.
Repair candidates must be revalidated against all rules. Define admissible edits,
protected events, nonnegative costs and alternative timelines. Compare a greedy
baseline with exact branch-and-bound on small instances. Claim minimum cost only
when the exact search completes with a valid bound and exhaustive coverage.

Experiments will vary graph size, density, cycle structure, constraint count and
operation mix. Use fixed seeds, repeated measurements, environment versions,
wall-clock timings, peak Python allocations (with native-memory limitations),
expanded/pruned search nodes and cost gaps against an exact baseline.
Keep raw results and distinguish timeouts from completed solutions. No measurements
have been collected in Phase 1.
