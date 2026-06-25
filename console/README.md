# AutoML Bench Console

Multipage Streamlit app over the benchmark (spec 003). Shows **only sections backed by real
data** — Evaluation, Datasets, Methods. Mock-only sections (Training jobs, Compute pricing,
Deploy) and the placeholder budget were removed; add them back when each has a real backend.

## Run

```bash
source .venv/bin/activate
streamlit run console/app.py          # DB-first if DATABASE_URL set, else SQLite/CSV fallback
```

## Layout

```
console/
├── app.py            # st.navigation entrypoint (3 live sections)
├── theme.py          # shared CSS identity (teal/amber) + table/pill/card helpers + repo-root path
├── state.py          # live results loader via storage.repo (DB-first, CSV fallback)
└── pages/
    ├── evaluation.py  # ranking · Pareto · by-characteristic (reuses analysis/* via repo)
    ├── datasets.py    # Upload CSV / Add-from-OpenML → object store + DB; catalog from DB
    └── methods.py     # framework catalog from the methods table + US7 integration entry
```

All three read real data through `storage/repo.py` (Postgres or SQLite/CSV fallback). Backend
setup: see the repo `README.md` → *Backend (Postgres + MinIO)*. Tests: `pytest tests/test_console.py`.
