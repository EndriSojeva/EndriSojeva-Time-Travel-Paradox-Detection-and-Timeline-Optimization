# Project checklist

The headings below are intended as individual GitHub Issues. Check each item
as it is completed and close the issue after verifying all items.

## Phase 1 — Initialize and publish the project

- [x] Check Python, Git, VS Code and extension availability on Windows.
- [x] Create the local virtual environment and install project dependencies.
- [x] Add the package, sample data, notebooks, documentation and Streamlit shell.
- [x] Verify the initial tests, notebook cells and Streamlit startup.
- [ ] Confirm the public repository contains the initial commit on `main`.

## Phase 2 — Model timelines and time travel operations

- [ ] Define event state, causal relation types and allowed edit operations.
- [ ] Specify the semantics of backward travel, insertion, deletion and modification.
- [ ] Add fixtures for valid history, consistent loops and contradictory histories.
- [ ] Test graph invariants and invalid operations.

## Phase 2 — Detect cycles and logical paradoxes

- [ ] Implement DFS and return reproducible cycle witnesses.
- [ ] Implement Tarjan and identify strongly connected components.
- [ ] Implement explicit logical constraints and report responsible events.
- [ ] Test consistent cycles and contradictions in acyclic graphs.
- [ ] Expose a timeline validation result that distinguishes structural and logical findings.

## Phase 2 — Find minimum-cost repairs and alternative timelines

- [ ] Define admissible edits, protected events and their costs.
- [ ] Implement a greedy repair baseline.
- [ ] Implement branch-and-bound and record expanded and pruned states.
- [ ] Revalidate candidate repairs and return alternative timelines.
- [ ] Check exact optimum on small cases and distinguish timeouts from proven optima.

## Phase 2 — Run reproducible experiments and verify Kaggle

- [ ] Generate seeded scenarios across sizes, densities and constraint mixes.
- [ ] Measure runtime, peak allocations, pruning and repair quality over repeated trials.
- [ ] Run notebooks, capture raw results and make comparison figures.
- [ ] Verify installation and execution on Kaggle at a chosen commit.
- [ ] Document complexity, measurement limits and experimental findings.

## Phase 2 — Complete the Streamlit demo and academic handoff

- [ ] Connect the graph builder, detection and repair pages to the package.
- [ ] Show alternative timelines and explain cycle and contradiction results.
- [ ] Present verified comparison and performance results.
- [ ] Run the full test suite and verify the demo from a fresh setup.
- [ ] Prepare the academic presentation and final submission.
