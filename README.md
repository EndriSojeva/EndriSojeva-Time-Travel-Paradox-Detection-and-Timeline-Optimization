# Time Travel Paradox Detection and Timeline Optimization

Academic Python project by Endri Sojeva. The project models events and causal
relations as a directed graph, with planned support for logical contradictions
and minimum-cost timeline repairs.

Phase 1 includes a graph model, four illustrative scenarios, five notebook
scaffolds and a Streamlit interface. A causal cycle alone does not establish a
logical paradox. See [methodology](docs/methodology.md) and the
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

Use the project's Python environment for notebooks under `notebooks/`. On
Kaggle, enable Internet and install the repository at a chosen commit with
`%pip install "git+<REAL_REPOSITORY_URL>@<COMMIT_SHA>"`, or attach the source as
a dataset and install from its directory. Restart the kernel if needed. Record
the commit, dependency versions and seeds for comparisons. Kaggle execution
and authentication have not been verified.

## Layout

`src/timetravel/` contains the package and planned algorithm modules.
`data/examples/` contains synthetic inputs. `tests/` covers the initial graph
behavior and interfaces. `experiments/` reserves entry points for scenario
generation and benchmarking. `results/figures/` is reserved for future outputs.

See the [project checklist](docs/github_tasks.md) for the planned work and acceptance checks.
