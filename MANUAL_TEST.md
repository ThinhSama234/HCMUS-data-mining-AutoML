# Manual UI Test — AutoML Console

Hướng dẫn test tay giao diện console (spec 003 + runner US4 + Cost). Vừa làm vừa tick `[ ]` → `[x]`.

> Cập nhật theo app hiện tại: Training **chạy thật** (Docker), Cost là **estimator thật**,
> catalog có **~19 methods + 18 datasets**, Evaluation có leaderboard/rank-score/tooltip.

---

## 0. Chuẩn bị

- Stack: `docker compose ps` → `postgres (healthy)`, `minio` đều Up.
- Seed + (tuỳ chọn) nạp kết quả cũ: `python -m storage.seed` · `python -m storage.migrate results/results.csv`
- Console: **http://localhost:8501** (`streamlit run console/app.py`).
- File mẫu upload: `/Users/lap17650/workspace/automl-thesis/sample_data/`

| File | Loại | Target | Dùng |
|------|------|--------|------|
| `loan_binary.csv` | binary | `approved` | upload OK |
| `flower_multiclass.csv` | multiclass | `species` | upload OK |
| `house_regression.csv` | regression | `price` | upload OK |
| `bad_single_column.csv` | — | — | test **bị từ chối** |

- OpenML task id để Add-from-OpenML: **`59`** (iris).
- Sidebar 3 nhóm: **Analyze** (Evaluation) · **Build** (Datasets, Methods, Training) · **Operate** (Cost, Deploy).

> ⚠️ **Apple Silicon:** chỉ **flaml / constantpredictor** chạy được benchmark thật (verified).
> AutoGluon/autosklearn quá nặng → dùng để test *đường fail/chặn*, đừng đợi nó xong.

---

## ① Evaluation

- [ ] Caption `data source: **db**`.
- [ ] **KPI** (4 ô) có tooltip ⓘ khi hover: Best overall / Datasets / Runs / Coverage.
- [ ] **Overall leaderboard**: bảng cột 🥇🥈🥉 giảm dần (flaml #1), tooltip ⓘ giải thích.
- [ ] **Accuracy vs inference time** (Pareto): điểm amber = Pareto-optimal, tooltip ⓘ.
- [ ] **Ranking by data characteristic**: dropdown **Group datasets by** đổi được (Task type / Dataset size / #features / Class balance). Đoạn giải thích dài nằm trong tooltip ⓘ, **không** hiện inline.
  - [ ] Chọn **Task type** → bar ngang rank-score (bar dài = tốt), **không lỗi** "unknown characteristic".
- [ ] Đổi filter Framework/Task type/Dataset → mọi view cập nhật.
- [ ] **Export headline figures** → "Wrote: results/figures/…".

---

## ② Datasets

### Upload CSV
- [ ] `loan_binary.csv` → ✅ toast "Ingested … dataset_id N"; bảng có dòng `source=upload`, `binary`, `n_instances=60`.
- [ ] `flower_multiclass.csv` → `multiclass`; `house_regression.csv` → `regression`.
- [ ] Cột **status** = `ready`; cột **File** có icon ⬇ (presigned download).

### Test từ chối
- [ ] `bad_single_column.csv` → ❌ "needs at least one feature plus a target", **không** tạo dòng mới.

### Add from OpenML
- [ ] Nhập `59` → ✅ "iris … dataset_id N".
- [ ] Nhập `59` lần nữa → **cùng dataset_id** (idempotent).

> Tên dataset **UNIQUE** — trùng tên → báo lỗi unique (đúng thiết kế).

---

## ③ Methods

- [ ] Caption **Host:** … (arch · Rosetta/qemu · VM RAM/cores).
- [ ] ~19 cards; mỗi card có **status pill** + **compat badge** (vd flaml `Runs here` xanh, AutoGluon `Failed here` đỏ, autosklearn `Heavy · emulated` vàng).
- [ ] Nút **↻ Re-check** → toast "Re-checked …" (đồng bộ status với image thật).
- [ ] Expander **💾 Docker storage** → bảng `docker system df` + nút **🧹 Reclaim space**.
- [ ] Click 1 card → trang detail (`?m=…`): bảng field (Kind/Version/Resource class/Image size…), tooltip; nếu integrated + image có → nút **🗑 Remove image (free X GB)**; nếu đang có job chạy → nút **⏹ Stop job**.
- [ ] **Integrate**: chọn 1 framework `available` (vd `gama`) → **Integrate** → pill `integrating` → (chờ pull) → `integrated` (cần Docker + mạng).

---

## ④ Training  *(LIVE — chạy Docker thật)*

- [ ] Caption **Host:** hiện như Methods.
- [ ] **Framework**: chỉ liệt kê framework `integrated`. Chọn **flaml**.
- [ ] **Datasets to train on**: multiselect ~18 dataset, **chip chỉ hiện tên** (không cụt), dưới có dòng tóm tắt "N selected — X binary · Y multiclass · Z regression".
- [ ] **Constraint** = smoke; caption hiện budget/fold/cores.
- [ ] Bỏ bớt chỉ chừa **1 dataset nhỏ** (vd credit-g) cho nhanh → **🚀 Launch on 1 dataset(s)**.
- [ ] Bảng **Jobs**: job mới `running`, KPI Running/Done/Failed cập nhật, auto-refresh 3s.
- [ ] Chờ ~1–3 phút → job `done`, cột **Runs** ≥1; mở **Evaluation** thấy kết quả flaml mới.
- [ ] **Test đường chặn:** chọn **AutoGluon** → hiện cảnh báo đỏ "Failed here" + **checkbox "Run anyway"**, nút Launch **bị khoá** đến khi tích.
- [ ] (tuỳ) Launch rồi bấm **⏹ Stop** → job `cancelled`.

---

## ⑤ Cost  *(estimator thật)*

- [ ] Chọn **Constraint / Datasets / Frameworks** → 3 KPI: Total runs, Compute (worst case) h, Budget/run.
- [ ] Bảng **Estimated cost by instance**: CPU/T4/A100 với cost = giờ × rate.
- [ ] Hàng GPU có nhãn ⚠ "no speed-up modelled"; hộp giải thích ghi rõ rate là minh hoạ, upper-bound.

---

## ⑥ Deploy  *(Coming soon)*

- [ ] Hiện placeholder 🚧 "Coming soon" (badge **Preview**, chưa có backend) — đúng thiết kế.

---

## Đối chiếu backend (tin là thật)

```bash
# datasets vừa upload nằm trong Postgres:
docker compose exec -T postgres psql -U amlb -d amlb -c \
  "SELECT dataset_id,name,source,task_type,storage_uri FROM datasets ORDER BY dataset_id DESC LIMIT 10;"
# job + kết quả vừa chạy:
docker compose exec -T postgres psql -U amlb -d amlb -c \
  "SELECT training_run_id,status,finished_at FROM training_runs ORDER BY training_run_id DESC LIMIT 5;"
```
- [ ] Dòng `upload`/`openml` có `storage_uri = s3://datasets/...`.
- [ ] MinIO web **http://localhost:9001** (`amlb` / `amlb12345`) → bucket **datasets/** có file.
- [ ] `results/job_<id>/run.log` của job vừa chạy có log AMLB.

---

## Dọn dẹp

```bash
lsof -ti tcp:8501 | xargs kill -9        # dừng console
docker compose down                      # dừng stack (giữ data)
docker compose down -v                   # xoá sạch → rồi: docker compose up -d && python -m storage.seed
```
