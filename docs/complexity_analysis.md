# Complexity analysis

Let V be event count and E be causal edge count. Graph storage and construction
use O(V + E) space and expected time, assuming constant-time identifier hashing.

DFS visits each vertex and inspects each outgoing edge at most once. The active
path index gives the witness start in constant expected time. Constructing a
witness takes O(V) in the worst case. Iterative Tarjan visits each vertex and
edge once and pushes and pops each vertex once. Each algorithm runs in O(V + E)
time and uses O(V) auxiliary space beyond the input graph. The SCC partition and
cycle witnesses also require O(V) output space. Finding one witness per cyclic
SCC preserves the bound because components are disjoint and DFS only expands
vertices in the current component. Edges leaving a component are inspected at
most once in this pass. Enumerating all simple cycles may require exponential output.

Let S be the number of stated entity effects, A the number of recorded trips,
and R the number of explicit prerequisites and required IDs. Validation and the
built-in rules take expected O(V + E + S + A + R) time, assuming constant-time
hashing and bounded text field sizes. Variable-length event metadata and report
text add time proportional to their size. The assertion index requires O(S)
space, status and structural working data require O(V), and violations can add
O(E + S + A + R) output space. Custom rules can have different bounds.

Greedy repair complexity depends on candidate generation and repeated validation.
Branch-and-bound has exponential worst-case search; pruning does not guarantee
polynomial runtime. Exact bounds will be documented after the edit model and
implementation are fixed. The general repair problem is not yet formally defined.
