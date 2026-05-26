# NHS Patient Activity — ETL Pipeline

A clean, well-documented ETL pipeline for NHS ward activity data, built to demonstrate good software engineering practices.

## Open in GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/YOUR_USERNAME/nhs-etl-pipeline)

> Click the button above to launch a fully configured environment. The notebook opens automatically.

---

## What this project demonstrates

| Practice | Implementation |
|---|---|
| **Separation of concerns** | Three independent layers: `extract` · `transform` · `load` |
| **Idempotent loads** | `INSERT OR REPLACE` on a natural key — safe to re-run any number of times |
| **Data quality validation** | NHS number checks, NULL rate thresholds, open spell detection |
| **Unit testing** | 20+ tests covering all core logic in `tests/` |
| **CI/CD** | GitHub Actions: lint → test → execute notebook on every push |
| **Documented decisions** | Every design choice explained inline in the notebook |

---

## Project structure

```
nhs-etl-pipeline/
├── .devcontainer/
│   └── devcontainer.json        # Codespaces configuration
├── .github/
│   └── workflows/
│       └── ci.yml               # CI/CD: lint → test → notebook execution
├── data/
│   └── mock_activity.csv        # Mock NHS ward activity data
├── notebooks/
│   └── etl_pipeline.ipynb       # Main ETL walkthrough — start here
├── src/
│   ├── extract.py               # Extract layer — reads source data
│   ├── transform.py             # Transform layer — all business logic
│   └── load.py                  # Load layer — idempotent upsert to SQLite
├── tests/
│   ├── test_transform.py        # Unit tests for transform logic
│   └── test_load.py             # Unit tests for idempotency
├── requirements.txt
└── README.md
```

---

## Running locally

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nhs-etl-pipeline.git
cd nhs-etl-pipeline

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov jupyter

# Run the tests
pytest tests/ -v --cov=src --cov-report=term-missing

# Open the notebook
jupyter notebook notebooks/etl_pipeline.ipynb
```

---

## CI/CD pipeline

Every push triggers three sequential jobs:

1. **Lint** — `flake8` checks code style across `src/` and `tests/`
2. **Test** — `pytest` runs all unit tests with 80% minimum coverage gate
3. **Notebook** — the notebook is executed end-to-end via `nbconvert` and the output is uploaded as a CI artefact

A pull request cannot be merged to `main` unless all three jobs pass.

---

## Design decisions

Full design rationale is documented inline in the notebook. Key decisions:

- **All columns read as `str` at extract time** — type casting happens in transform, not in the reader
- **ValidationReport returned from transform** — the caller decides how to handle issues; transform has no side effects
- **Configurable NULL threshold** — can be tightened per environment (UAT vs production)
- **`INSERT OR REPLACE` over plain `INSERT`** — idempotency is enforced at the schema level via `PRIMARY KEY`, not just application logic
- **SQLite for portability** — no server required; in a production NHS context this would be SQL Server with `MERGE`
