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

With M single-use catalog entries, Greedy makes at most M(M + 1)/2 candidate
attempts and retains a current state, candidates under comparison and visited
keys. Branch-and-Bound may visit up to the number of ordered prefixes,
Σ[d=0..M] M!/(M-d)!, before pruning, memoization or resource limits. Its frontier
and memo can also grow exponentially or worse with the problem size. Each
attempt additionally pays for graph copying, validation and state indexing.
The best-first frontier incurs a logarithmic heap cost per insertion and removal
in terms of frontier size. Ranking up to K retained solutions may scan K entries.
Pruning does not guarantee polynomial complexity. In the recorded experiment,
increasing forward-edge probability at a fixed 2,000 vertices increased the
observed traversal time. Changes in DFS runtime also depend on how early a
witness is found. The independent oracle is capped at six edits, and exact raw
prefix accounting at eight. The five-conflict configuration reached its candidate
limit. These finite measurements do not establish asymptotic behavior.
