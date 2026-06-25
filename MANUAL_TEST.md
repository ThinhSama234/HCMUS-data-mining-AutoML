# Manual UI Test — AutoML Console

Hướng dẫn test tay giao diện console (spec 003). Vừa làm vừa tick `[ ]` → `[x]`.

> **Live** = nối DB/object-store thật · **Mock** = UI shell (chưa nối backend).

---

## 0. Chuẩn bị

- Stack chạy: `docker compose ps` → `postgres (healthy)`, `minio`, đều Up.
- Console: **http://localhost:8501** (nếu chưa chạy: `streamlit run console/app.py`).
- File mẫu để upload (dialog trỏ tới thư mục này):

  ```
  /Users/lap17650/workspace/automl-thesis/sample_data/
  ```

| File | Loại | Target | Dùng để |
|------|------|--------|---------|
| `loan_binary.csv` | binary | `approved` | upload OK |
| `flower_multiclass.csv` | multiclass | `species` | upload OK |
| `house_regression.csv` | regression | `price` | upload OK |
| `bad_single_column.csv` | — | (không có) | test **bị từ chối** |

- OpenML task id: **`59`** (iris, multiclass) — đã verify chạy được.

---

## ① Evaluation  *(Live)*

- [ ] Mở section **Evaluation** ở sidebar.
- [ ] Caption hiện `data source: **db**`.
- [ ] Thấy 3 view: **Ranking** (bar), **Accuracy vs inference time** (Pareto), **By data characteristic**.
- [ ] Đổi filter **Framework / Task type / Dataset** → các view cập nhật theo.
- [ ] Bấm **Export headline figures** → báo "Wrote: results/figures/…".

**Kỳ vọng:** flaml ~1.33 > RandomForest ~1.67 > constantpredictor 3.0.

---

## ② Datasets  *(Live — phần US8 chính)*

### Upload CSV
- [ ] Chọn `loan_binary.csv` → **Ingest upload** → ✅ "Ingested … dataset_id N".
- [ ] Bảng dưới thêm dòng: `source=upload`, `task_type=binary`, `n_instances=60`, `n_features=3`.
- [ ] Lặp với `flower_multiclass.csv` → `task_type=multiclass`.
- [ ] Lặp với `house_regression.csv` → `task_type=regression`.

### Test từ chối (rejection)
- [ ] Upload `bad_single_column.csv` → ❌ báo đỏ "needs at least one feature plus a target".
- [ ] **Không** có dòng mới nào được tạo.

### Add from OpenML
- [ ] Nhập `59` → **Add from OpenML** → ✅ "iris … dataset_id N" (multiclass).
- [ ] Nhập `59` lần nữa → trả về **cùng dataset_id** (idempotent, không nhân đôi).

> Lưu ý: tên dataset là **UNIQUE** — upload trùng tên file hoặc OpenML trùng tên → báo lỗi unique (đúng thiết kế).

---

## ③ Methods  *(Live)*

- [ ] 6 method hiện từ DB: flaml, H2OAutoML, AutoGluon, RandomForest, TunedRandomForest, constantpredictor.
- [ ] Pill trạng thái đúng: flaml/RandomForest/constantpredictor = `integrated`, H2OAutoML = `setup_pending`, TunedRandomForest = `failed`.
- [ ] Có card nét đứt **"+ Integrate new framework"** (US7 skill).

---

## ④ Training  *(Mock)*

- [ ] Form chọn được: Datasets / Frameworks (chip), Budget (smoke/1h/4h), Folds, Mode.
- [ ] Nút **Launch run** + bảng **Jobs** hiển thị (tĩnh — chưa nối orchestration thật).

---

## ⑤ Compute & Pricing  *(Live instances + estimator)*

- [ ] 3 instance từ DB: CPU 8-core, GPU T4, GPU A100 (giá/hr).
- [ ] Chỉnh **Runs / Budget / Instance / Parallelism** → 3 ô (compute-hours, wall-clock, cost) cập nhật.

---

## ⑥ Deploy  *(Mock)*

- [ ] Bảng endpoints + form deploy hiển thị (UI shell, ngoài scope thesis).

---

## Đối chiếu backend (tin là thật, không phải mock)

```bash
# datasets vừa upload nằm trong Postgres:
docker compose exec -T postgres psql -U amlb -d amlb -c \
  "SELECT dataset_id,name,source,task_type,n_instances,storage_uri FROM datasets ORDER BY dataset_id;"
```
- [ ] Thấy các dòng `upload` / `openml` với `storage_uri = s3://datasets/...`.
- [ ] MinIO web http://localhost:9001 (amlb / amlb12345) → bucket **datasets/** có file.

---

## Dọn dẹp

```bash
lsof -ti tcp:8501 | xargs kill     # dừng console
docker compose down                # dừng stack (giữ data)
docker compose down -v             # xoá sạch (test lại từ đầu) → rồi: docker compose up -d && python -m storage.migrate
```
