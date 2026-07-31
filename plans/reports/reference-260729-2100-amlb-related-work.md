---
title: "AMLB: an AutoML Benchmark — Related Work & Contributions"
---

# AMLB: an AutoML Benchmark

> Gijsbers, Bueno, Coors, LeDell, Poirier, Thomas, Bischl, Vanschoren — arXiv:2207.12560v2 (2023), *Journal of Machine Learning Research*.

Bảng tổng hợp **Related Work** và **đóng góp chính (main contributions)** của paper.

---

## 1. Đóng góp chính (Main Contributions)

| # | Đóng góp | Chi tiết |
|---|----------|----------|
| 1 | **Benchmark AutoML mở & mở rộng được** | Tuân theo *best practices*, tránh các lỗi phổ biến (selection bias, cấu hình sai, ngân sách tính toán không tương đương) → thúc đẩy chuẩn hóa việc so sánh AutoML. |
| 2 | **Công cụ mã nguồn mở AMLB** | Tự động hóa đánh giá *end-to-end*: từ cài đặt framework → cấp phát tài nguyên → phân tích chuyên sâu. Tích hợp dễ dàng với nhiều framework AutoML. |
| 3 | **Đánh giá quy mô lớn 9 framework** | So sánh 9 framework AutoML nổi tiếng (một số có nhiều cấu hình) trên **71 tác vụ phân loại + 33 tác vụ hồi quy**. |
| 4 | **Phân tích đa chiều (multi-faceted)** | Không chỉ độ chính xác mô hình mà còn: đánh đổi với *inference time*, và **phân tích lỗi (failure analysis)** của framework. |
| 5 | **Bradley-Terry trees** | Kỹ thuật phát hiện các *nhóm tác vụ con* nơi thứ hạng tương đối giữa các framework thay đổi. |
| 6 | **Công cụ trực quan hóa tương tác + website** | Cho phép khám phá sâu kết quả & tái lập phân tích. Dùng dữ liệu công khai, có website cập nhật kết quả liên tục, dễ mở rộng thêm framework/tác vụ. |

**Phạm vi (scope):** Chỉ tập trung dữ liệu **dạng bảng (tabular)** & framework **mã nguồn mở**. Dữ liệu phi cấu trúc (NAS) nằm ngoài phạm vi.

---

## 2. Related Work

### 2.0 Bộ dữ liệu benchmark ML tổng quát

| Công trình | Loại | Hạn chế mà AMLB nêu ra |
|-----------|------|------------------------|
| Van Gestel et al. (2004), Olson et al. (2017), Wu et al. (2018), Bischl et al. (2021), Fischer et al. (2023) | Bộ benchmark ML chung | Thường **không chứa dữ liệu "khó" thực tế** (nhiều missing values...); **không có runtime budget** — vốn thiết yếu cho AutoML. |

### 2.1 Đánh giá các Framework AutoML

| Công trình | Phạm vi / Thiết lập | Đóng góp | Hạn chế mà AMLB chỉ ra |
|-----------|---------------------|----------|------------------------|
| **Balaji & Allen (2018)** | 4 framework mã nguồn mở; classification + regression; dữ liệu OpenML | Một trong những benchmark AutoML đầu tiên | Lỗi kỹ thuật: H2O tối ưu sai metric & không container hóa; auto_ml tắt HPO → kết quả không so sánh được. |
| **Ferreira et al. (2021)** | H2O vs GAMA vs TPOT; dự đoán protein abundance | So sánh trực tiếp các framework | Ngân sách thời gian **rất khác nhau** (6h / 1h / theo cấu hình) và không được lý giải. |
| **Truong et al. (2019)** | 6 framework; ~300 dataset; holdout 80/20; budget 15 phút | Phân tích theo *nhóm con* (ít/nhiều đặc trưng), thử nhiều budget & đo "robustness" | Thí nghiệm phụ chỉ trên **1 dataset/nhóm** → khó tổng quát; lỗi framework làm kết quả khó diễn giải. |
| **Zöller & Huber (2021)** | Survey CASH + AutoML; 137 tác vụ; 6 CASH + 5 AutoML; so với Kaggle | So sánh với data scientist (Kaggle) | Không kiểm soát cấu hình → khó kết luận về từng thành phần; kết quả Kaggle cũ, khó diễn giải. |
| **Wever et al. (2021)** | Benchmark cho **multi-label classification**; search space & optimizer cấu hình được | Cho phép ablation study | Yêu cầu **tái cài đặt (re-implement)** framework trong công cụ → khó theo kịp lĩnh vực phát triển nhanh. |
| **Guyon et al. (2019)** | Chuỗi **cuộc thi** AutoML (tabular, i.i.d.) | Đánh giá trên dữ liệu mới ẩn danh | Đa số phương pháp **thất bại** trên ít nhất vài dataset do vấn đề thực tế (hết bộ nhớ...). |

### 2.2 Benchmark cho các thành phần con (HPO / BBO / NAS)

| Nhóm | Benchmark tiêu biểu | Mục đích |
|------|---------------------|----------|
| **Black-box optimization** | COCO (Hansen 2021), Nevergrad, kurobako (Ohta & Yamazaki 2022), LassoBench (Šehić 2021), Bayesmark (Turner 2022) | Đánh giá optimizer gradient-free / BO trên hàm tổng hợp & tác vụ thực tế / chiều cao. |
| **HPO benchmarks** | HPOlib (Eggensperger 2013), HPOBench (2021), HPO-B (Arango 2021), PROFET (Klein 2019) | Benchmark tái lập cho tuning siêu tham số, multi-fidelity, transfer-HPO, meta-model tổng hợp. |
| **NAS benchmarks** | NAS-Bench-101 (Ying 2019), NAS-Bench-1shot1 (Zela 2020), NAS-Bench-301 (Siems 2020) | Dữ liệu dạng bảng ánh xạ kiến trúc → hiệu năng, giúp NAS dễ tiếp cận hơn. |

---

## 3. Khoảng trống (Gap) mà AMLB lấp

Không benchmark nào trước đó trở thành **chuẩn** cho cộng đồng AutoML: hoặc thiếu runtime budget, hoặc cấu hình sai/không tương đương, hoặc yêu cầu tái cài đặt framework, hoặc phân tích không đủ tổng quát. AMLB giải quyết bằng một công cụ mở, tích hợp trực tiếp với framework (không cần re-implement), tự động hóa toàn trình và phân tích đa chiều trên bộ tác vụ lớn, chuẩn hóa.
