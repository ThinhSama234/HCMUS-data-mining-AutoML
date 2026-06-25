"""Phase 0 storage — a SQLite cache of the AMLB results, so the console/analysis read from a
queryable store instead of a static CSV. `analysis/*` is unchanged: `repo.load()` returns the
same tidy DataFrame whether the source is the DB or the CSV. No FastAPI yet (that arrives with
real training jobs / a non-Streamlit client)."""
