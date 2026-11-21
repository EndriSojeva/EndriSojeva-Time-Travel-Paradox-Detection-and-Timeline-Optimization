"""Greedy descent on the number of active consistency violations."""

from ..repair import SearchContext, SearchState


def greedy(context: SearchContext, original: SearchState, attempt_cap: int | None = None) -> SearchState | None:
    current = original
    visited = {original.key}
    state_only = context.state_only
    incumbent = None
    while current.remaining and not current.report.consistent:
        context.metrics.expanded += 1
        best = None
        best_rank = None
        for index in current.choices():
            if attempt_cap is not None and context.metrics.greedy_candidates >= attempt_cap:
                return incumbent
            if not context.can_attempt():
                return incumbent
            context.metrics.greedy_candidates += 1
            candidate = context.transition(current, index)
            if candidate is None:
                continue
            if state_only and candidate.key in visited:
                context.metrics.pruned += 1
                continue
            gain = len(current.report.violations) - len(candidate.report.violations)
            if gain <= 0:
                context.metrics.pruned += 1
                continue
            if candidate.report.consistent and (incumbent is None or candidate.rank < incumbent.rank):
                incumbent = candidate
            cost = candidate.cost - current.cost
            rank = (cost != 0, -gain / cost if cost else 0, -gain, cost, index)
            if best_rank is None or rank < best_rank:
                best, best_rank = candidate, rank
        if best is None:
            break
        current = best
        visited.add(current.key)
    context.time_available()
    return incumbent
