"""Benchmark runner (US4) — launch a real AMLB run on an integrated framework via Docker.

Mirrors `integration.py`: `launch()` creates a `training_runs` row, marks it `running`, and spawns
a **detached** worker that `docker run`s the framework's AMLB image on the `mvp` benchmark, then
ingests the produced `results.csv` into `runs` (linked to the job) and finalizes the job to
`done`/`failed`. The console polls `list_jobs()` on rerun. Same single-user/local model as US3 —
a detached subprocess + DB status rows, no FastAPI. The run pattern mirrors run_mvp_docker.sh.

Worker CLI:  python -m storage.runner --run <training_run_id> <method> <benchmark> <constraint>
"""
from __future__ import annotations

import io
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import func, insert, select, update

from storage import db
from storage.integration import _container_cli, _docker_available
from storage.models import (constraints, datasets, methods, runs,
                            training_run_datasets, training_run_methods, training_runs)

USERDIR = os.path.join(db.REPO_ROOT, "amlb_userdir")
DEFAULT_BENCHMARK = "mvp"
DEFAULT_CONSTRAINT = "smoke"
RUN_TIMEOUT = int(os.environ.get("AMLB_RUN_TIMEOUT", "1800"))   # cap a hung docker run (seconds)

# The AMLB images are amd64-only. On Apple Silicon they run under emulation; with the qemu
# backend the heavier AutoML images segfault, while light baselines run fine. Rosetta (enabled
# in Rancher/Docker Desktop) emulates x86 far more reliably and usually fixes this.
EMULATED = platform.system() == "Darwin" and platform.machine() == "arm64"
# Confirmed to complete under emulation on this Mac. flaml works once Rosetta is enabled
# (plain qemu segfaults on it); constantpredictor works even under qemu.
VERIFIED_LOCAL = {"constantpredictor", "flaml"}

# Community AMLB images bundle WIDELY different AMLB vintages, but we send them all the same modern
# CLI. Two version differences break a run, so we probe each image's bundled AMLB once and adapt:
#   * constraint     — older images' runbenchmark.py has NO `constraint` positional (e.g. *:stable);
#                      passing one fails with "unrecognized arguments: <constraint>". Can't run here.
#   * file_datasets  — mid-vintage images (e.g. *-v2.1.3) read `task_def.openml_task_id` un-guarded
#                      in BenchmarkTask.__init__, so an uploaded/file dataset (which has no
#                      openml_task_id) raises AttributeError and aborts the WHOLE job. Newer AMLB
#                      uses dict access with a default and tolerates file datasets.
# Detection is a cheap grep of the image's source (the image is already pulled). Results cache per
# image ref. On any probe failure we stay permissive (all caps True) so a modern image is never
# falsely blocked.
_CAPS: dict[str, dict] = {}
_PROBE_SH = r"""
c=$(grep -c "add_argument('constraint'" /bench/runbenchmark.py 2>/dev/null)
f=$(grep -c "openml_task_id=task_def\.openml_task_id" /bench/amlb/benchmark.py 2>/dev/null)
echo "CON=${c:-0} FILEUNSAFE=${f:-0}"
"""


def _probe_caps(image):
    """AMLB capabilities of a (pulled) image: {"constraint", "file_datasets", "probed"}. Cached."""
    if not image:
        return {"constraint": True, "file_datasets": True, "probed": False}
    if image in _CAPS:
        return _CAPS[image]
    caps = {"constraint": True, "file_datasets": True, "probed": False}
    try:
        r = subprocess.run(
            [_container_cli(), "run", "--rm", "--platform", "linux/amd64",
             "--entrypoint", "bash", image, "-c", _PROBE_SH],
            capture_output=True, text=True, timeout=60,
        )
        m = re.search(r"CON=(\d+)\s+FILEUNSAFE=(\d+)", r.stdout or "")
        if m:
            caps = {"constraint": int(m.group(1)) > 0,
                    "file_datasets": int(m.group(2)) == 0, "probed": True}
            _CAPS[image] = caps          # only cache a real probe — retry next time if Docker was down
    except Exception:
        pass
    return caps


def framework_caps(name, eng=None):
    """AMLB capabilities of a framework's integrated image (see `_probe_caps` / `_CAPS` notes)."""
    eng = db.init_db(eng)
    with eng.connect() as c:
        image = c.execute(select(methods.c.docker_image).where(methods.c.name == name)).scalar()
    return _probe_caps(image)


def run_advice(name, eng=None):
    """On Apple Silicon, flag how likely a framework is to run under amd64 emulation. None elsewhere."""
    if not EMULATED:
        return None
    if name in VERIFIED_LOCAL:
        return {"level": "ok", "msg": f"{name} is verified to run locally under emulation."}
    eng = db.init_db(eng)
    with eng.connect() as c:
        kind = c.execute(select(methods.c.kind).where(methods.c.name == name)).scalar()
    if kind == "baseline":
        return {"level": "warn",
                "msg": f"{name} is a lightweight baseline — usually OK under emulation (not verified)."}
    return {"level": "risk",
            "msg": (f"{name} is a heavy AutoML image (amd64). Under qemu emulation it often "
                    "segfaults — enable **Rosetta** in Rancher/Docker Desktop, or run it on an "
                    "Intel/Linux host or CI for real results.")}


def list_runnable(eng=None):
    """Integrated frameworks (image present) — the only ones runnable one-click."""
    eng = db.init_db(eng)
    with eng.connect() as c:
        rows = c.execute(select(methods.c.name)
                         .where(methods.c.integration_status == "integrated")
                         .order_by(methods.c.name)).all()
    return [r[0] for r in rows]


def list_constraints(eng=None):
    eng = db.init_db(eng)
    with eng.connect() as c:
        rows = c.execute(select(constraints.c.name).order_by(constraints.c.name)).all()
    return [r[0] for r in rows]


def constraint_info(constraint=DEFAULT_CONSTRAINT, eng=None):
    """The constraint's limits (folds / time budget / cores) for the run-plan preview."""
    eng = db.init_db(eng)
    with eng.connect() as c:
        crow = c.execute(select(constraints.c.folds, constraints.c.max_runtime_seconds,
                                constraints.c.cores).where(constraints.c.name == constraint)).first()
    return {"folds": crow[0], "seconds": crow[1], "cores": crow[2]} if crow else None


def run_history(eng=None):
    """Per-framework job outcomes on THIS machine: {name: {status: count}}."""
    eng = db.init_db(eng)
    with eng.connect() as c:
        rows = c.execute(
            select(methods.c.name, training_runs.c.status, func.count()).select_from(
                training_run_methods
                .join(methods, training_run_methods.c.method_id == methods.c.method_id)
                .join(training_runs,
                      training_run_methods.c.training_run_id == training_runs.c.training_run_id))
            .group_by(methods.c.name, training_runs.c.status)).all()
    out = {}
    for name, status, n in rows:
        out.setdefault(name, {})[status] = n
    return out


# Framework resource class — an objective, machine-independent property (image size / RAM / JVM /
# deep-learning). Used with the host profile to predict compatibility on ANY machine.
WEIGHT = {
    "constantpredictor": "light", "RandomForest": "light", "TunedRandomForest": "light",
    "DecisionTree": "light", "ranger": "light",
    "flaml": "medium", "gama": "medium", "tpot": "medium", "autoxgboost": "medium",
    "hyperoptsklearn": "medium", "naiveautoml": "medium", "mlr3automl": "medium", "oboe": "medium",
    "AutoGluon": "heavy", "autosklearn": "heavy", "H2OAutoML": "heavy", "lightautoml": "heavy",
    "mljarsupervised": "heavy", "mlplan": "heavy", "autoweka": "heavy",
}

_HOST = None


def host_profile():
    """Objective facts about THIS host that drive amd64-image compatibility (cached).

    AMLB images are amd64. On an arm64 host they run under emulation — Rosetta (reliable) or
    qemu (segfaults on heavy images). Returns os/arch/emulation/backend + Docker VM mem & cpus.
    """
    global _HOST
    if _HOST is not None:
        return _HOST
    arch = platform.machine()
    native = arch in ("x86_64", "amd64")
    backend, vm_mem, vm_cpu = ("native" if native else "unknown"), None, None
    if not native:
        try:
            import json
            s = json.loads(subprocess.run(["rdctl", "list-settings"], capture_output=True,
                                           text=True, timeout=10).stdout)
            vm = s.get("virtualMachine", {})
            backend = "rosetta" if vm.get("useRosetta") else "qemu"
            vm_mem, vm_cpu = vm.get("memoryInGB"), vm.get("numberCPUs")
        except Exception:
            backend = "emulated"
    _HOST = {"os": platform.system(), "arch": arch, "native": native,
             "image_arch": "amd64", "backend": backend, "vm_memory_gb": vm_mem, "vm_cpus": vm_cpu}
    return _HOST


def weight_of(name, kind=None):
    return WEIGHT.get(name) or ("light" if kind == "baseline" else "medium")


def host_summary():
    """One-line, machine-independent description of the run environment for the UI."""
    hp = host_profile()
    if hp["native"]:
        return f"Host: {hp['os']} {hp['arch']} · amd64 images run natively (no emulation)."
    be = {"rosetta": "via Rosetta", "qemu": "via qemu — heavy images segfault",
          "emulated": "emulated"}.get(hp["backend"], hp["backend"])
    mem = f"{hp['vm_memory_gb']} GB" if hp["vm_memory_gb"] else "? GB"
    cpu = f"{hp['vm_cpus']} cores" if hp["vm_cpus"] else "? cores"
    return (f"Host: {hp['os']} {hp['arch']} · amd64 images {be} · Docker VM {mem} / {cpu}. "
            "Heavier frameworks need more VM RAM and may time out under emulation.")


def compat(name, kind=None, hist=None):
    """Predicted compatibility of `name` on THIS machine, level ∈ {ok, warn, fail, ''}.

    Portable: derived from host emulation × image weight (works on any machine, no history needed).
    The machine's own job history, when present, overrides as ground truth.
    Returns the objective inputs too (weight/backend) so the UI can explain *why*.
    """
    hp, w = host_profile(), weight_of(name, kind)
    h = (hist or {}).get(name, {})
    done, failed = h.get("done", 0), h.get("failed", 0)

    if hp["native"]:
        level, label, why = "ok", "Native", "Host is amd64 — images run natively."
    elif hp["backend"] == "qemu":
        level, label, why = (("ok", "OK (light)", "Light image runs even under qemu.") if w == "light"
                             else ("fail", "qemu — risky",
                                   "amd64 image under qemu emulation usually segfaults. Enable Rosetta."))
    else:  # rosetta / emulated / unknown
        level, label, why = {
            "light": ("ok", "Light", "Light image — fine under emulation."),
            "medium": ("warn", "Medium · emulated", "Runs under emulation but slower; usually OK."),
            "heavy": ("warn", "Heavy · emulated",
                      "Heavy amd64 image under emulation — may time out or exhaust the Docker VM's RAM."),
        }[w]

    note = ""
    if done:                                            # empirical truth wins
        level, label = "ok", "Runs here"
        note = f" Confirmed: completed here {done}×."
    elif failed:
        level, label = "fail", "Failed here"
        note = f" Confirmed: failed here {failed}× (timeout/crash)."

    return {"level": level, "label": label, "weight": w, "backend": hp["backend"],
            "msg": (why + note).strip()}


def list_trainable_datasets(eng=None):
    """Catalog datasets a run can use: OpenML tasks (by id) or uploads (file + target column).

    Returns dicts with a `runnable` flag so the UI can show why one can't be trained.
    """
    eng = db.init_db(eng)
    with eng.connect() as c:
        rows = c.execute(select(
            datasets.c.dataset_id, datasets.c.name, datasets.c.task_type, datasets.c.source,
            datasets.c.openml_task_id, datasets.c.storage_uri, datasets.c.target_column,
        ).order_by(datasets.c.name)).all()
    out = []
    for d in rows:
        did, name, ttype, source, task_id, uri, target = d
        runnable = bool(task_id) or bool(uri and target)
        out.append({"dataset_id": did, "name": name, "type": ttype, "source": source,
                    "task_id": task_id, "uri": uri, "target": target, "runnable": runnable})
    return out


def _job_dir(tr_id):
    return os.path.join(db.REPO_ROOT, "results", f"job_{tr_id}")


def launch(method, dataset_ids=None, constraint=DEFAULT_CONSTRAINT, eng=None):
    """Create a job over the chosen catalog datasets and spawn the detached runner.

    dataset_ids: list of `datasets.dataset_id` to train on. None/empty → all runnable datasets.
    Returns (training_run_id, status).
    """
    eng = db.init_db(eng)
    runnable = {d["dataset_id"]: d for d in list_trainable_datasets(eng) if d["runnable"]}
    if not dataset_ids:
        dataset_ids = list(runnable)
    with eng.connect() as c:
        m = c.execute(select(methods.c.method_id, methods.c.docker_image,
                             methods.c.integration_status)
                      .where(methods.c.name == method)).first()
        cid = c.execute(select(constraints.c.constraint_id)
                        .where(constraints.c.name == constraint)).scalar()
    if not m or not m[1] or m[2] != "integrated":
        return None, "failed"                           # only an integrated (pulled) image runs
    caps = _probe_caps(m[1])
    if not caps["constraint"]:
        return None, "no_constraint"                    # image's AMLB predates constraints — can't run
    if not caps["file_datasets"]:                       # old image can't run uploads (no openml_task_id)
        dataset_ids = [i for i in dataset_ids if runnable.get(i) and runnable[i]["task_id"]]
    if not dataset_ids:
        return None, "no_datasets"                      # nothing left this image can actually run
    docker_ok = _docker_available()
    with eng.begin() as c:
        tr_id = c.execute(insert(training_runs).values(
            constraint_id=cid, mode="docker",
            status="running" if docker_ok else "failed",
            started_at=datetime.now(timezone.utc),
        )).inserted_primary_key[0]
        c.execute(insert(training_run_methods).values(training_run_id=tr_id, method_id=m[0]))
        for did in dataset_ids:
            c.execute(insert(training_run_datasets).values(training_run_id=tr_id, dataset_id=did))
    if not docker_ok:
        _finish(eng, tr_id, "failed", "Docker engine not running")
        return tr_id, "failed"
    subprocess.Popen(
        [sys.executable, "-m", "storage.runner", "--run", str(tr_id), method, constraint],
        cwd=db.REPO_ROOT, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return tr_id, "running"


def _finish(eng, tr_id, status, error=None):
    with eng.begin() as c:
        c.execute(update(training_runs).where(training_runs.c.training_run_id == tr_id)
                  .values(status=status, last_error=error, finished_at=datetime.now(timezone.utc)))


def reap_stale_jobs(eng=None, grace=120):
    """Mark orphaned 'running' jobs as failed.

    A worker caps its docker run at RUN_TIMEOUT and finalizes the row itself. If a job is still
    'running' past RUN_TIMEOUT + grace, its worker died abnormally (VM crash, OOM, kill) without
    finishing — so it would otherwise hang on 'running' forever. Returns the reaped job ids.
    """
    eng = db.init_db(eng)
    now = datetime.now(timezone.utc)
    reaped = []
    with eng.begin() as c:
        rows = c.execute(select(training_runs.c.training_run_id, training_runs.c.started_at)
                         .where(training_runs.c.status == "running")).all()
        for tid, started in rows:
            if started and started.tzinfo is None:      # SQLite returns naive datetimes
                started = started.replace(tzinfo=timezone.utc)
            if started and (now - started).total_seconds() > RUN_TIMEOUT + grace:
                c.execute(update(training_runs)
                          .where(training_runs.c.training_run_id == tid)
                          .values(status="failed", finished_at=now,
                                  last_error="stale — worker exited without finishing (exceeded "
                                             "run timeout); marked failed automatically"))
                reaped.append(tid)
    return reaped


def _status(eng, tr_id):
    """Current status of a job (None if it vanished)."""
    with eng.connect() as c:
        return c.execute(select(training_runs.c.status)
                         .where(training_runs.c.training_run_id == tr_id)).scalar()


def cancel(tr_id, eng=None):
    """Stop a running job *now*: kill its container, then flip running → cancelled atomically.

    Covers both races: if the container is already running, `docker kill` stops the heavy work
    immediately; if the worker hasn't reached `docker run` yet (still staging datasets), it checks
    for a 'cancelled' status before starting and aborts. The conditional UPDATE (only when still
    'running') means a job that finished a split-second earlier keeps its real done/failed result.
    Returns True if this call is what cancelled it.
    """
    eng = db.init_db(eng)
    try:                                                  # best-effort; no-op if container/CLI absent
        subprocess.run([_container_cli(), "kill", f"amlb_job_{tr_id}"], capture_output=True)
    except Exception:
        pass
    with eng.begin() as c:
        res = c.execute(update(training_runs)
                        .where(training_runs.c.training_run_id == tr_id)
                        .where(training_runs.c.status == "running")
                        .values(status="cancelled", last_error="stopped by user",
                                finished_at=datetime.now(timezone.utc)))
    return res.rowcount > 0


def list_jobs(eng=None, limit=50):
    """Recent jobs as a tidy frame: framework, constraint, status, timestamps, run count.

    Uses dict lookups (not pandas merges) so pre-existing runs with a NULL training_run_id
    can't poison the join key dtype.
    """
    eng = db.init_db(eng)
    with eng.connect() as c:
        tr = pd.read_sql(select(
            training_runs.c.training_run_id, training_runs.c.status, training_runs.c.mode,
            training_runs.c.started_at, training_runs.c.finished_at, training_runs.c.constraint_id,
            training_runs.c.last_error.label("error"),
        ).order_by(training_runs.c.training_run_id.desc()).limit(limit), c)
        if tr.empty:
            return tr
        fw = dict(c.execute(select(
            training_run_methods.c.training_run_id, methods.c.name
        ).select_from(training_run_methods.join(
            methods, training_run_methods.c.method_id == methods.c.method_id))).all())
        con = dict(c.execute(select(constraints.c.constraint_id, constraints.c.name)).all())
        rc = dict(c.execute(select(runs.c.training_run_id, func.count())
                            .where(runs.c.training_run_id.isnot(None))
                            .group_by(runs.c.training_run_id)).all())
        dc = dict(c.execute(select(training_run_datasets.c.training_run_id, func.count())
                            .group_by(training_run_datasets.c.training_run_id)).all())
    tr["framework"] = tr["training_run_id"].map(fw)
    tr["constraint"] = tr["constraint_id"].map(con)
    tr["runs"] = tr["training_run_id"].map(rc).fillna(0).astype(int)
    tr["datasets"] = tr["training_run_id"].map(dc).fillna(0).astype(int)
    return tr


def _build_benchmark(eng, tr_id):
    """Generate an AMLB benchmark file for the job's linked datasets under amlb_userdir/benchmarks.

    OpenML datasets → `{name, openml_task_id}`. Uploads → download from the object store, split
    train/test (AMLB v2.1.3 file datasets need both), stage under `{user}/data/_job_<id>/` and emit
    a `dataset: {train, test, target}` entry. Returns (benchmark_name, n_entries).
    """
    with eng.connect() as c:
        rows = c.execute(select(
            datasets.c.name, datasets.c.openml_task_id, datasets.c.storage_uri,
            datasets.c.target_column, datasets.c.task_type,
        ).select_from(training_run_datasets.join(
            datasets, training_run_datasets.c.dataset_id == datasets.c.dataset_id))
         .where(training_run_datasets.c.training_run_id == tr_id)).all()
    lines, n = [], 0
    for name, task_id, uri, target, ttype in rows:
        # keep the catalog name as the AMLB task name (AMLB allows hyphens/caps) so results
        # map straight back to this dataset row; sanitize only for the on-disk file path.
        safe = "".join(ch if ch.isalnum() else "_" for ch in name)
        if task_id:
            lines += [f"- name: {name}", f"  openml_task_id: {int(task_id)}", ""]
            n += 1
        elif uri and target:
            ddir = os.path.join(USERDIR, "data", f"_job_{tr_id}", safe)
            os.makedirs(ddir, exist_ok=True)
            _stage_upload_split(uri, target, ttype, ddir)
            lines += [f"- name: {name}", "  dataset:",
                      f"    train: '{{user}}/data/_job_{tr_id}/{safe}/train.csv'",
                      f"    test: '{{user}}/data/_job_{tr_id}/{safe}/test.csv'",
                      f"    target: {target}", "  folds: 1", ""]
            n += 1
    bench = f"_job_{tr_id}"
    with open(os.path.join(USERDIR, "benchmarks", f"{bench}.yaml"), "w") as f:
        f.write("---\n\n" + "\n".join(lines))
    return bench, n


def _stage_upload_split(uri, target, task_type, ddir):
    """Download an uploaded dataset and write a stratified-when-possible train/test split."""
    from storage import objectstore
    from sklearn.model_selection import train_test_split
    raw = objectstore.get(uri)
    df = pd.read_parquet(io.BytesIO(raw)) if uri.endswith(".parquet") else pd.read_csv(io.BytesIO(raw))
    strat = df[target] if task_type in ("binary", "multiclass") else None
    try:
        tr, te = train_test_split(df, test_size=0.25, random_state=0, stratify=strat)
    except ValueError:                                   # too few per class to stratify
        tr, te = train_test_split(df, test_size=0.25, random_state=0)
    tr.to_csv(os.path.join(ddir, "train.csv"), index=False)
    te.to_csv(os.path.join(ddir, "test.csv"), index=False)


# ---------------------------------------------------------------- worker body
def _run_job(tr_id, method, constraint):
    eng = db.init_db()
    if not _docker_available():
        _finish(eng, tr_id, "failed", "Docker engine not running")
        return 1
    with eng.connect() as c:
        image = c.execute(select(methods.c.docker_image)
                          .where(methods.c.name == method)).scalar()
    if not image:
        _finish(eng, tr_id, "failed", f"no Docker image for {method}")
        return 1
    try:
        benchmark, n_ds = _build_benchmark(eng, tr_id)
    except Exception as e:
        _finish(eng, tr_id, "failed", f"could not prepare datasets: {type(e).__name__}: {e}")
        return 1
    if not n_ds:
        _finish(eng, tr_id, "failed", "no runnable datasets selected (need an OpenML task id or an uploaded file + target)")
        return 1
    if _status(eng, tr_id) == "cancelled":      # user hit Stop while we were staging datasets
        return 1                                # never start the container
    outdir = _job_dir(tr_id)
    os.makedirs(outdir, exist_ok=True)
    cname = f"amlb_job_{tr_id}"
    cli = _container_cli()
    out, err, rc = "", "", 1
    try:
        r = subprocess.run(
            # -s auto: verify the framework's pre-built venv (fast) instead of -s skip, which
            # asserts setup-done and fails for real frameworks like flaml ("not installed").
            [cli, "run", "--rm", "--name", cname, "--platform", "linux/amd64",
             "-v", f"{USERDIR}:/custom", "-v", f"{outdir}:/output", image,
             method, benchmark, constraint, "-o", "/output", "-u", "/custom", "-s", "auto"],
            capture_output=True, text=True, timeout=RUN_TIMEOUT,
        )
        out, err, rc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        # a hung/emulation-segfaulting container never returns — kill it so the job can't hang forever
        subprocess.run([cli, "kill", cname], capture_output=True)
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = f"timed out after {RUN_TIMEOUT}s — container killed (amd64 image may be segfaulting under emulation)"
    if _status(eng, tr_id) == "cancelled":      # container was killed by cancel() — keep 'cancelled', don't relabel
        return 1
    with open(os.path.join(outdir, "run.log"), "w") as f:
        f.write(out or "")
        f.write("\n--- STDERR ---\n")
        f.write(err or "")
    csv = os.path.join(outdir, "results.csv")
    n = _ingest_job(eng, tr_id, csv) if os.path.exists(csv) else 0
    ok = rc == 0 and n
    if ok:
        _finish(eng, tr_id, "done")
        return 0
    if "Segmentation fault" in (out + err) or "qemu" in (out + err):
        reason = "container segfaulted under amd64 emulation — enable Rosetta or run on an Intel/Linux host"
    elif rc != 0:
        reason = (err or out or "docker run failed").strip()[-400:]
    else:
        reason = "run produced no results.csv"
    _finish(eng, tr_id, "failed", reason)
    return 1


def _ingest_job(eng, tr_id, csv_path):
    """Insert this job's results.csv into `runs`, tagged with training_run_id. Returns rows."""
    from storage.migrate import (BASELINES, METRIC_COLS, _failure_category, _get_or_create,
                                  _int, _num)
    from storage.models import datasets
    from analysis.load_results import load_results
    df = load_results(csv_path)
    if df.empty:
        return 0
    has_constraint = "constraint" in df.columns
    with eng.begin() as conn:
        m_ids = {fw: _get_or_create(conn, methods, fw,
                                    kind="baseline" if fw in BASELINES else "automl")
                 for fw in df["framework"].dropna().unique()}
        d_ids = {}
        for task, sub in df.groupby("task"):
            ttype = sub["type"].iloc[0] if "type" in sub.columns else None
            d_ids[task] = _get_or_create(conn, datasets, task, source="benchmark", task_type=ttype)
        c_ids = {cn: _get_or_create(conn, constraints, cn)
                 for cn in (df["constraint"].dropna().unique() if has_constraint else [])}
        rows = []
        for _, r in df.iterrows():
            metrics = {k: float(r[k]) for k in METRIC_COLS
                       if k in df.columns and not pd.isna(r.get(k))}
            rows.append(dict(
                training_run_id=tr_id,
                dataset_id=d_ids.get(r["task"]),
                method_id=m_ids.get(r["framework"]),
                constraint_id=c_ids.get(r.get("constraint")) if has_constraint else None,
                fold=_int(r.get("fold")),
                metric=None if pd.isna(r.get("metric")) else str(r["metric"]),
                result=_num(r.get("result_num")), score=_num(r.get("score")),
                status="success" if bool(r["success"]) else _failure_category(r.get("info")),
                training_duration=_num(r.get("training_duration")),
                predict_duration=_num(r.get("predict_duration")),
                models_count=_int(r.get("models_count")), seed=_int(r.get("seed")),
                framework_version=None if pd.isna(r.get("version")) else str(r["version"]),
                metrics=metrics or None,
            ))
        if rows:
            conn.execute(insert(runs), rows)
    return len(df)


def main(argv):
    if len(argv) >= 5 and argv[1] == "--run":
        return _run_job(int(argv[2]), argv[3], argv[4])
    print("usage: python -m storage.runner --run <id> <method> <constraint>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
