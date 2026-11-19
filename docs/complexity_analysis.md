# Complexity analysis plan

Let V be event count and E be causal edge count. Graph storage and construction
use O(V + E) space and expected time, assuming constant-time identifier hashing.

Planned DFS and Tarjan implementations target O(V + E) time and O(V) auxiliary
space; these are algorithmic targets, not measurements of implemented code.
Enumerating all cycles can require exponential output and is not equivalent
to detecting one cycle. Constraint cost depends on the selected rule semantics.

Greedy repair complexity depends on candidate generation and repeated validation.
Branch-and-bound has exponential worst-case search; pruning does not guarantee
polynomial runtime. Exact bounds will be documented after the edit model and
implementation are fixed. The general repair problem is not yet formally defined.
