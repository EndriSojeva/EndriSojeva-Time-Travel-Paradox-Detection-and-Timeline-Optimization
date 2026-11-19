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

`TimelineConstraint` defines the future rule interface. A `ConstraintViolation`
can carry a causal or logical classification, responsible event IDs and directed
relation evidence. The consistent and contradictory example files illustrate
inputs for Issue #3. Their logical conclusions depend on the selected rules.

Run the focused tests with `python -m pytest tests/test_graph.py tests/test_constraints.py`
or the full suite with `python -m pytest` from the configured environment.

## Planned detection, repair and experiments
DFS will supply cycle witnesses; Tarjan will isolate strongly connected components.
A cycle is structural evidence, not proof of a paradox: self-consistent loops may
exist. Logical contradictions require explicit existence, precedence or mutually
exclusive state rules. Acyclic graphs may also violate such rules. Backward edges
are not automatically invalid in a time-travel model.

Define validity relative to declared rules and return violations with responsible
event IDs. Use the operations defined above when evaluating candidate edits.
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
