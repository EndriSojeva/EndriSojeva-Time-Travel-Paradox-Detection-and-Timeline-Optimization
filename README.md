# Time Travel Paradox Detection and Timeline Optimization

Academic Python project by Endri Sojeva. The project models events and causal
relations as a directed graph, with cycle witnesses and rule-based consistency
validation. Minimum-cost timeline repair is planned.

The project includes a graph model, validated timeline edits, six illustrative
scenarios, five notebooks and a Streamlit interface. A causal cycle alone does
not establish a logical paradox. Choose **Paradox Detection** in Streamlit to
inspect cycle witnesses and conflicts. Repair and benchmarks are planned.
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
compares consistent and inconsistent scenarios. Notebooks 03–05 are scaffolds
for the remaining work. All five Phase 1 notebooks ran successfully
on Kaggle with a private source dataset from commit `ad8fa96`. Kaggle copies
load a source snapshot associated with a GitHub commit. Changes pushed to GitHub
require a new snapshot and notebook run. Record the full commit, dependency
versions and seeds for comparisons.

## Layout

`src/timetravel/` contains the timeline model, operations and detection algorithms.
`data/examples/` contains synthetic inputs. `tests/` covers graph operations,
consistency rules and structural algorithms. `experiments/` reserves entry points for scenario
generation and benchmarking. `results/figures/` is reserved for future outputs.

See the [project checklist](docs/github_tasks.md) for the planned work and acceptance checks.
