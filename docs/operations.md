# Operations

How to bring the backend up, load data, run the console, and recover.

## Environment variables

Loaded from `.env` automatically by `storage/db.py` (python-dotenv; `docker-compose` sets its own).
Copy [`.env.example`](../.env.example) → `.env`. **Leave everything unset to use the SQLite +
local-`.objectstore/` fallback (no containers).**

| Var | Purpose | Default / fallback |
|---|---|---|
| `DATABASE_URL` | Postgres DSN | unset → SQLite `console.db` |
| `S3_ENDPOINT` | MinIO/S3 endpoint | unset → local `.objectstore/` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | object-store creds | `amlb` / `amlb12345` |
| `CONTAINER_CLI` | container CLI | auto-detect `docker`/`nerdctl`/`podman` |
| `AMLB_RUN_TIMEOUT` | cap a benchmark `docker run` (s) | `1800` |

## Bring up the backend (Docker)

```bash
docker-compose up -d            # postgres + minio (+ console image)
python -m storage.seed          # catalog: methods / constraints / compute_instances
python -m storage.migrate results/results.csv   # optional: load historical results into `runs`
streamlit run console/app.py    # → http://localhost:8501
```

Ports:

| Service | Port | Notes |
|---|---|---|
| Console (Streamlit) | **8501** | the app |
| PostgreSQL | 5432 | `amlb`/`amlb`, db `amlb` |
| MinIO S3 API | 9000 | key `amlb` / secret `amlb12345` |
| MinIO console (UI) | 9001 | login `amlb` / `amlb12345` |

## Zero-setup mode (no Docker)

Skip `docker-compose`; just `streamlit run console/app.py`. The app uses SQLite + `.objectstore/`.
Browsing, dataset upload, and OpenML ingest all work; only benchmark **runs** need Docker.

## Schema changes

`db.init_db()` runs `create_all` (creates missing tables) but **does not ALTER** existing ones.
After a model change either recreate the dev DB (`docker-compose down -v && docker-compose up -d`,
then re-seed/migrate) or apply a manual `ALTER TABLE`.

## Recovery (Docker VM crashed)

A heavy run can exhaust the Docker VM and take Postgres/MinIO down with it. Recover:

```bash
rdctl start                                   # restart Rancher Desktop VM (Apple Silicon)
# wait for `docker info` to succeed, then:
docker compose up -d postgres minio           # data persists in named volumes
```

Orphaned `running` jobs (worker died) are auto-marked failed on the next Training page load
(`runner.reap_stale_jobs()` — anything past `AMLB_RUN_TIMEOUT` + grace). Disk is managed from the
**Methods → 💾 Docker storage** panel. See [docker.md](docker.md).

## Tests

```bash
pytest -q        # storage / ingest / integration / runner / console render tests
```
