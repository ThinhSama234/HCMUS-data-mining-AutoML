# Báo cáo đồ án MTH055 — Khai thác Dữ liệu lớn (Nhóm 19)

Khung báo cáo LaTeX theo **chuẩn luận văn thạc sĩ**, đã được điền sẵn nội dung
theo đề tài của nhóm: **Đánh giá và so sánh công bằng các framework AutoML**
(FLAML, H2O AutoML, AutoGluon) theo giao thức **AMLB**, kèm hệ thống *AutoML Bench
Console*. Nhiều phần đã viết sẵn bằng văn phong khoa học; các chỗ `[...]` là số
liệu/thông tin cần điền (đặc biệt là kết quả lần chạy đầy đủ trên 20 bộ dữ liệu).

## Cấu trúc thư mục
```
report-template/
├── main.tex                          # Preamble (12pt) + lắp ráp báo cáo
├── frontmatter/                      # Bìa, cam đoan, cảm ơn, tóm tắt, danh mục viết tắt
├── content/
│   ├── chuong1_gioi-thieu.tex        # Mở đầu (có bảng Input/Output/Ràng buộc)
│   ├── chuong2_co-so-ly-thuyet.tex   # Kiến thức nền + khảo sát ≥5 công trình
│   ├── chuong3_phuong-phap.tex       # Giao thức AMLB + kiến trúc + thuật toán + ví dụ tính
│   ├── chuong4_thuc-nghiem.tex       # Dữ liệu, kết quả sơ bộ, ablation, phân tích lỗi
│   ├── chuong5_ket-luan.tex          # Kết luận + hướng phát triển
│   └── phu-luc.tex                   # Hướng dẫn tái lập + ghi chú sử dụng AI
├── main/references.bib               # Tài liệu tham khảo (IEEE)
└── image/                            # Ảnh chụp hệ thống (thật, từ docs/images)
```

## Ánh xạ tới yêu cầu đề bài (MTH055)
| Yêu cầu đề bài | Vị trí trong báo cáo |
|---|---|
| Phát biểu bài toán (Input/Output/Ràng buộc) | Chương 1, Bảng 1.1 |
| Khảo sát ≥5 công trình, phân loại, khoảng trống | Chương 2, mục 2.6–2.7 |
| Trình bày lại/cải tiến + thuật toán + độ phức tạp | Chương 3 (Hướng 1: tái thực nghiệm AMLB) |
| ≥2 bộ dữ liệu, ≥2 baseline, độ đo, bảng+biểu đồ, ablation | Chương 4 |
| Kết luận + ≥2–3 hướng phát triển cụ thể | Chương 5 |
| Mục lục, danh mục thuật ngữ/hình/bảng, phụ lục | frontmatter/ + phu-luc |
| Ghi chú sử dụng công cụ AI | Phụ lục B |
| Định dạng: LaTeX, 12pt, lề T/B 2.5cm, trái 3cm, phải 2.5cm, TLTK IEEE | main.tex |

> **Còn cần điền:** thành viên nhóm + MSHV (bìa), tên GVHD, số liệu lần chạy đầy
> đủ 20 bộ dữ liệu (các bảng có ô `[ ]`), thống kê bộ dữ liệu Kaggle, ghi chú AI.
> Yêu cầu tối thiểu 50 trang — mỗi chương đã có ghi chú mốc ≥10 trang.

## Biên dịch
- **Overleaf (khuyến nghị):** tải cả thư mục, đặt `main.tex` làm file chính,
  Compiler = **pdfLaTeX** → Recompile.
- **Máy cá nhân:** `pdflatex main` → `bibtex main` → `pdflatex main` → `pdflatex main`.
- Nếu bắt buộc font Times New Roman: dùng **XeLaTeX** + `\usepackage{fontspec}`,
  `\setmainfont{Times New Roman}` (xem ghi chú trong `main.tex`).

## Lưu ý về tính trung thực
Các số liệu ở Chương 4 (breast_cancer / california_housing / wine, ngân sách 30s)
là **kết quả sơ bộ có thật**, trích từ `reports/run_20260702_211007_f0f0d1.json`
và `report/report.md` của dự án. Kết quả trên đủ 20 bộ dữ liệu (môi trường
Docker/Linux) đang hoàn tất — giữ nguyên nhãn "sơ bộ" cho tới khi có số cuối cùng.
