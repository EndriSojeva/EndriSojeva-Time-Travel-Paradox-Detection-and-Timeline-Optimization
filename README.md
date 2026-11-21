# Time Travel Paradox Detection and Timeline Optimization

Academic Python project by Endri Sojeva. The project models events and causal
relations as a directed graph, with cycle witnesses and rule-based consistency
validation and finite minimum-cost timeline repair.

The project includes a graph model, validated timeline edits, seven illustrative
scenarios, five notebooks and a Streamlit interface. A causal cycle alone does
not establish a logical paradox. Choose **Paradox Detection** in Streamlit to
inspect cycle witnesses and conflicts. Choose **Timeline Repair** to compare
Greedy with Branch-and-Bound, control search limits and inspect alternatives.
Global optimum claims are relative to the finite edit catalog. The comparison
and performance pages display the recorded reference run.
See [methodology](docs/methodology.md) and the
[complexity analysis plan](docs/complexity_analysis.md).

## Local setup on Windows

From the project root with Python 3.11 or later available in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local address shown by Streamlit. In VS Code, select the `.venv`
interpreter and install the recommended Python, Pylance and Jupyter extensions.

## Notebooks and Kaggle

Use the project's Python environment for notebooks under `notebooks/`. Notebook
01 demonstrates timeline operations. Notebook 02 explains DFS and Tarjan and
compares consistent and inconsistent scenarios. Notebook 03 demonstrates Greedy,
exact, infeasible and limited repair runs. Notebooks 04 and 05 generate comparison
and scaling tables and figures. All five Phase 1 notebooks ran successfully
on Kaggle with a private source dataset from commit `ad8fa96`. Kaggle copies
load a source snapshot associated with a GitHub commit. Changes pushed to GitHub
require a new snapshot and notebook run. Record the full commit, dependency
versions and seeds for comparisons.

## Reproduce the benchmarks

```powershell
.\.venv\Scripts\python.exe -m experiments.generate_scenarios --size 40 --conflicts 6 --trips 8 --seed 73 --output results/generated.json
.\.venv\Scripts\python.exe -m experiments.benchmark --profile full --repetitions 3 --output results/latest
```

Run from the repository root. Profiles `comparison` and `smoke` use smaller
workloads. The measured [reference run](results/reference/) supplies raw trials,
summary statistics, provenance and figures. Unpublished reruns stay ignored by
Git. See the [methodology](docs/methodology.md#experimental-evaluation) for
sampling, oracle checks, pruning formulas and memory limits.

## Layout

`src/timetravel/` contains the timeline model, operations and detection algorithms.
`data/examples/` contains synthetic inputs. `tests/` covers graph operations,
consistency rules, structural algorithms, optimization and the benchmark.
`experiments/` contains the scenario generator and benchmark runner.

See the [project checklist](docs/github_tasks.md) for the planned work and acceptance checks.
