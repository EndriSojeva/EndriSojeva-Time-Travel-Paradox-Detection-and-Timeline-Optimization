# Methodology

Author: Endri Sojeva. Deadline: December 1, 2026.

## Phase 1 scope
Events are nodes with an identifier, label and numeric time. Directed edges
encode causal dependencies and nonnegative modification costs. Duplicate
edges are rejected; parallel relation types require a future schema extension.
Example scenarios are illustrative inputs, not verified experimental findings.

## Phase 2 design
DFS will supply cycle witnesses; Tarjan will isolate strongly connected components.
A cycle is structural evidence, not proof of a paradox: self-consistent loops may
exist. Logical contradictions require explicit existence, precedence or mutually
exclusive state rules. Acyclic graphs may also violate such rules. Backward edges
are not automatically invalid in a time-travel model.

Define validity relative to declared rules and return violations with responsible
event IDs. Establish semantics for travel, insertion, deletion and modification
operations before implementing them; timestamps alone cannot encode these semantics.
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
