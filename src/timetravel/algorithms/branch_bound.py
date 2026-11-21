"""Best-first branch and bound over the finite repair catalog."""

from heapq import heappop, heappush

from ..repair import SearchContext, SearchState
from .greedy import greedy


def branch_and_bound(context: SearchContext, original: SearchState, use_greedy_bound: bool) -> tuple[SearchState, ...]:
    solutions: dict[tuple, SearchState] = {}
    capacity = context.limits.max_alternatives
    subtree_sizes = [0]
    if context.track_prefix_pruning:
        for remaining in range(1, len(context.catalog) + 1):
            subtree_sizes.append(remaining * (1 + subtree_sizes[-1]))

    def cut(state: SearchState, reason: str) -> None:
        metrics = context.metrics
        metrics.pruned += 1
        if reason == "bound":
            metrics.bound_pruned += 1
        else:
            metrics.dominance_pruned += 1
        if metrics.raw_prefix_descendants_pruned is not None and not state.report.consistent:
            metrics.raw_prefix_descendants_pruned += subtree_sizes[state.remaining.bit_count()]

    def offer(candidate: SearchState) -> None:
        previous = solutions.get(candidate.key)
        if previous is None or candidate.rank < previous.rank:
            solutions[candidate.key] = candidate
        if len(solutions) > capacity:
            worst = max(solutions, key=lambda key: solutions[key].rank)
            del solutions[worst]

    def beyond_bound(state: SearchState) -> bool:
        # Nonnegative edit fees make the cumulative cost a lower bound.
        return len(solutions) == capacity and state.cost > max(item.cost for item in solutions.values())

    def memo_key(state: SearchState) -> tuple:
        # Unknown extension rules may inspect audit history or graph insertion order.
        return state.key, state.remaining, () if state_only else state.path

    state_only = context.state_only
    preview = min(context.limits.max_candidates // 4, len(context.catalog) * 2)
    if use_greedy_bound and preview and original.remaining:
        incumbent = greedy(context, original, attempt_cap=preview)
        if incumbent is not None:
            offer(incumbent)

    frontier = [(original.rank, original)]
    best_rank = {memo_key(original): original.rank}
    while frontier and context.limit_reason is None:
        if not context.time_available():
            break
        rank, state = heappop(frontier)
        if beyond_bound(state):
            cut(state, "bound")
            for _, pending in frontier:
                cut(pending, "bound")
            break  # Heap order means every pending state has an equal or greater lower bound.
        if rank != best_rank[memo_key(state)]:
            cut(state, "dominance")
            continue
        if not state.remaining:
            continue
        context.metrics.expanded += 1
        context.metrics.exact_expanded += 1
        for index in state.choices():
            if not context.can_attempt():
                break
            candidate = context.transition(state, index)
            if candidate is None:
                continue
            if beyond_bound(candidate):
                cut(candidate, "bound")
            elif candidate.report.consistent:
                offer(candidate)
            elif candidate.remaining:
                key = memo_key(candidate)
                if key in best_rank and best_rank[key] <= candidate.rank:
                    cut(candidate, "dominance")
                    continue
                best_rank[key] = candidate.rank
                heappush(frontier, (candidate.rank, candidate))
    context.time_available()
    return tuple(sorted(solutions.values(), key=lambda item: item.rank))
