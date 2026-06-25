# Docker & framework images

Each AutoML framework is a **prebuilt `automlbenchmark/<name>` Docker image** that embeds the AMLB
harness + that framework's environment. The console uses Docker two ways:

- **Integrate** = `docker pull` the image (works on any architecture).
- **Run** = `docker run` the image on a benchmark (this is where architecture matters).

Implementation: [`storage/integration.py`](../storage/integration.py) (pull/manage),
[`storage/runner.py`](../storage/runner.py) (run), pattern mirrors `scripts/run_mvp_docker.sh`.

## Run invocation

```
docker run --rm --name amlb_job_<id> --platform linux/amd64 \
  -v <amlb_userdir>:/custom -v results/job_<id>:/output \
  automlbenchmark/<framework>:<tag> \
  <framework> _job_<id> <constraint> -o /output -u /custom -s auto
```

- `-s auto` (not `-s skip`): verifies the image's pre-built per-framework venv, else a real
  framework would error `"... is not installed"`.
- `-u /custom`: mounts `amlb_userdir/` so AMLB sees our benchmark/constraint definitions.
- The benchmark `_job_<id>.yaml` is generated per run from the datasets you picked.

## Apple Silicon (arm64): emulation matters

The images are **amd64-only**. On an Apple-silicon Mac they run under emulation:

| Backend | Behavior |
|---|---|
| **qemu** (default) | heavy AutoML images **segfault** (`qemu: uncaught target signal 11`) |
| **Rosetta** | emulates x86 reliably — flaml/light frameworks run |

**Enable Rosetta** (Rancher Desktop, VM type `vz`):
```bash
rdctl set --virtual-machine.use-rosetta=true   # restarts the VM; re-`docker compose up -d` after
```
Even with Rosetta, **very heavy images don't all run here**: AutoGluon pulls multi-GB CUDA/torch
wheels at setup (no GPU on a Mac) and times out. Verified-runnable locally: `flaml`,
`constantpredictor`. Run AutoGluon/autosklearn/H2O on an x86_64 Linux/CI host.

## Compatibility metric

The console predicts compatibility from **objective inputs** (portable to any machine) plus this
machine's history:

- **Host profile** — OS, arch, emulation backend (native/Rosetta/qemu), Docker VM memory & CPUs (`runner.host_profile()`).
- **Image weight** — `light` / `medium` / `heavy` (`runner.WEIGHT`).
- **Verdict** — host × weight → `ok` / `warn` / `fail`; a `done`/`failed` job on this machine overrides as ground truth (`runner.compat()`).

Shown as a badge on the Methods cards and the Training picker. A framework that **failed here** is
blocked on Training unless you tick "run anyway". See [frameworks.md](frameworks.md).

## Safety: never hang, never silently fill disk

- **Run timeout** — `AMLB_RUN_TIMEOUT` (default 1800s) caps each `docker run`; on timeout the named
  container is `docker kill`ed and the job is marked `failed` with a reason.
- **Auto-reap** — a `running` job whose worker died is auto-failed on the next Training load.
- **Disk management** — **Methods → 💾 Docker storage**: see `docker system df` and **🧹 Reclaim
  space** (prunes build cache + stopped containers + dangling layers; keeps tagged framework
  images). Per framework, **🗑 Remove image** frees its space (status → `available`).
