"""Framework integration (US3, FR-005/019/020) — make an AMLB framework's Docker image present.

`integrate(name)` resolves the image, marks the method `integrating`, and spawns a **detached**
`docker pull` worker that finalizes the method row to `integrated` (image present) or `failed`
(with the error). The console polls `integration_status(name)` on rerun. No FastAPI — a detached
subprocess + the DB status row is enough for single-user/local. See contracts/integration.md.

Worker CLI:  python -m storage.integration --pull <name>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select, update

from storage import db
from storage.models import methods


def _container_cli():
    """The container CLI to use — `CONTAINER_CLI` env, else first of docker/nerdctl/podman on PATH.
    Lets the feature work with Docker Desktop, Rancher (moby *or* containerd/nerdctl), Colima, Podman."""
    cli = os.environ.get("CONTAINER_CLI")
    if cli:
        return cli
    for c in ("docker", "nerdctl", "podman"):
        if shutil.which(c):
            return c
    return "docker"


def _docker_available():
    try:
        subprocess.run([_container_cli(), "info"], capture_output=True, timeout=15, check=True)
        return True
    except Exception:
        return False


def image_present(image):
    """True if the image is actually pulled locally (the real meaning of 'integrated')."""
    if not image:
        return False
    try:
        r = subprocess.run([_container_cli(), "image", "inspect", image],
                           capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def image_size_bytes(image):
    """On-disk size of a pulled image in bytes, or None if not present/unknown."""
    if not image:
        return None
    try:
        r = subprocess.run([_container_cli(), "image", "inspect", "--format", "{{.Size}}", image],
                           capture_output=True, text=True, timeout=15)
        return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None
    except Exception:
        return None


def docker_disk():
    """Parsed `docker system df` → [{type, size, reclaimable}] for the storage panel."""
    try:
        r = subprocess.run([_container_cli(), "system", "df",
                            "--format", "{{.Type}}|{{.Size}}|{{.Reclaimable}}"],
                           capture_output=True, text=True, timeout=20)
        out = []
        for line in r.stdout.strip().splitlines():
            p = line.split("|")
            if len(p) == 3:
                out.append({"type": p[0], "size": p[1], "reclaimable": p[2]})
        return out
    except Exception:
        return []


def reclaim_space():
    """Safe prune — build cache + stopped containers + dangling image layers. Never removes a
    tagged framework image (those are freed explicitly via remove_image). Returns a text summary."""
    cli = _container_cli()
    parts = []
    for args, label in [(["builder", "prune", "-a", "-f"], "build cache"),
                        (["container", "prune", "-f"], "stopped containers"),
                        (["image", "prune", "-f"], "dangling images")]:
        try:
            r = subprocess.run([cli] + args, capture_output=True, text=True, timeout=180)
            got = [l for l in r.stdout.splitlines() if "reclaimed" in l.lower()]
            parts.append(f"{label}: {got[-1].split(':')[-1].strip() if got else '0B'}")
        except Exception:
            parts.append(f"{label}: error")
    return " · ".join(parts)


def remove_image(image):
    """Delete a pulled image to reclaim its disk (the method then reconciles to 'available')."""
    if not image:
        return False
    try:
        return subprocess.run([_container_cli(), "rmi", image],
                              capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


def reconcile(eng=None):
    """Make `integration_status` truthful: a method is `integrated` only if its image is actually
    present locally. Seed defaults claim 'integrated' without a real pull — this corrects them.
    Leaves `integrating` / `setup_pending` / `failed` untouched. Returns the names changed.
    """
    eng = db.init_db(eng)
    with eng.connect() as c:
        rows = c.execute(select(methods.c.name, methods.c.integration_status,
                                methods.c.docker_image)).all()
    if not _docker_available():
        return []
    changed = []
    for name, status, image in rows:
        present = image_present(image)
        if present and status == "available":
            _set(eng, name, integration_status="integrated")
            changed.append((name, "integrated"))
        elif not present and status == "integrated":
            _set(eng, name, integration_status="available", last_error="image not pulled")
            changed.append((name, "available"))
    return changed


def _newest_tag(name):
    """Newest published tag for automlbenchmark/<name> (no `latest`); None if not found."""
    url = (f"https://hub.docker.com/v2/repositories/automlbenchmark/{name.lower()}"
           f"/tags?page_size=1&ordering=last_updated")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            results = json.load(r).get("results", [])
        return results[0]["name"] if results else None
    except Exception:
        return None


def resolve_image(name, eng=None):
    """Full image ref `automlbenchmark/<name>:<tag>` from the seeded row, else Docker Hub."""
    eng = db.init_db(eng)
    with eng.connect() as c:
        row = c.execute(select(methods.c.image_tag, methods.c.docker_image)
                        .where(methods.c.name == name)).first()
    if row and row[1]:
        return row[1]                                  # full image already seeded
    tag = (row[0] if row and row[0] else None) or _newest_tag(name)
    return f"automlbenchmark/{name.lower()}:{tag}" if tag else None


def _set(eng, name, **vals):
    with eng.begin() as c:
        c.execute(update(methods).where(methods.c.name == name).values(**vals))


def integration_status(name, eng=None):
    eng = db.init_db(eng)
    with eng.connect() as c:
        row = c.execute(select(methods.c.integration_status, methods.c.docker_image,
                               methods.c.last_error, methods.c.last_integration_at)
                        .where(methods.c.name == name)).first()
    if not row:
        return {"status": "unknown"}
    return {"status": row[0], "image": row[1], "last_error": row[2], "updated_at": row[3]}


def integrate(name, eng=None):
    """Kick off integration (non-blocking). Returns the immediate status."""
    eng = db.init_db(eng)
    if not _docker_available():
        _set(eng, name, integration_status="failed", last_error="Docker engine not running")
        return "failed"
    _set(eng, name, integration_status="integrating", last_error=None)
    subprocess.Popen(                                  # detached worker; finalizes DB when pull ends
        [sys.executable, "-m", "storage.integration", "--pull", name],
        cwd=db.REPO_ROOT, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return "integrating"


def _run_pull(name):
    """Worker body: pull the image and finalize the method row."""
    eng = db.init_db()
    if not _docker_available():
        _set(eng, name, integration_status="failed", last_error="Docker engine not running")
        return 1
    image = resolve_image(name, eng)
    if not image:
        _set(eng, name, integration_status="failed", last_error=f"no published image for {name}")
        return 1
    r = subprocess.run([_container_cli(), "pull", "--platform", "linux/amd64", image],
                       capture_output=True, text=True)
    if r.returncode == 0:
        _set(eng, name, integration_status="integrated", docker_image=image,
             image_tag=image.split(":")[-1], last_error=None,
             last_integration_at=datetime.now(timezone.utc))
        return 0
    _set(eng, name, integration_status="failed", last_error=(r.stderr or "docker pull failed").strip()[-500:])
    return 1


def main(argv):
    if len(argv) >= 3 and argv[1] == "--pull":
        return _run_pull(argv[2])
    print("usage: python -m storage.integration --pull <name>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
