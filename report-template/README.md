# Báo cáo đồ án MTH055 — Khai thác Dữ liệu lớn (Nhóm 19)

Báo cáo LaTeX theo **chuẩn luận văn thạc sĩ** cho đề tài **đánh giá và so sánh
công bằng các framework AutoML** (AutoGluon, FLAML, H2O AutoML, MLJAR) theo giao
thức AMLB. Nội dung đã được viết dựa trên kết quả thực nghiệm thật ở
`report/report_v2.md` và bộ biểu đồ ở `report/images/` (nhánh `phat`).

## Cấu trúc
```
report-template/
├── main.tex                          # Preamble 12pt + lắp ráp báo cáo
├── frontmatter/                      # Bìa, cam đoan, cảm ơn, tóm tắt, danh mục viết tắt
├── content/
│   ├── chuong1_gioi-thieu.tex        # Mở đầu: bối cảnh, Input/Output/Ràng buộc, đóng góp
│   ├── chuong2_co-so-ly-thuyet.tex   # CASH, chiến lược tìm kiếm, độ đo, Bradley–Terry, 7 công trình
│   ├── chuong3_phuong-phap.tex       # Giao thức công bằng, kiến trúc, thuật toán, độ phức tạp
│   ├── chuong4_thuc-nghiem.tex       # 12 dataset, kết quả, 11 biểu đồ, ablation, phân tích lỗi
│   ├── chuong5_ket-luan.tex          # Kết luận, giới hạn, 5 hướng phát triển
│   └── phu-luc.tex                   # Hướng dẫn tái lập + ghi chú sử dụng AI
├── main/references.bib               # 9 tài liệu tham khảo (IEEE)
└── image/                            # 11 biểu đồ thực nghiệm + 4 ảnh giao diện
```

## Biên dịch
- **Overleaf (khuyến nghị):** tải cả thư mục, `main.tex` là file chính, Compiler =
  **pdfLaTeX** → Recompile.
- **Máy cá nhân:** `pdflatex main` → `bibtex main` → `pdflatex main` → `pdflatex main`.

## Trạng thái so với yêu cầu đề bài
| Yêu cầu | Trạng thái |
|---|---|
| Phát biểu bài toán (Input/Output/Ràng buộc) | ✅ Chương 1, Bảng 1.2 |
| Khảo sát ≥5 công trình + khoảng trống | ✅ Chương 2 (7 công trình) |
| Thuật toán từng bước + độ phức tạp | ✅ Chương 3 |
| ≥2 bộ dữ liệu, độ đo phù hợp, bảng + biểu đồ | ✅ Chương 4 (12 bộ, 11 biểu đồ) |
| Ablation study | ✅ Mục 4.7 (ngân sách 60s vs 300s) |
| **So sánh ≥2 baseline** | ⚠️ **Mục 4.5 đã có khung + luận giải, CẦN ĐIỀN SỐ** |
| Kết luận + ≥2–3 hướng phát triển | ✅ Chương 5 (5 hướng) |
| Mục lục, danh mục hình/bảng/thuật ngữ, phụ lục | ✅ |
| Ghi chú sử dụng AI | ⚠️ Phụ lục B — cần điền |
| LaTeX, 12pt, lề 2.5/3/2.5cm, TLTK IEEE | ✅ main.tex |
| Tối thiểu 50 trang (không tính phụ lục + TLTK) | ⚠️ Cần xác nhận bằng pdfLaTeX (xem bên dưới) |

## Còn cần điền
1. **Bìa:** tên + MSHV 4 thành viên, tên GVHD.
2. **Mục 4.5 — baseline:** chạy `dummy` + `randomforest` (đã có trong
   `scripts/orchestrator.py`) rồi điền Bảng 4.6. Đây là yêu cầu bắt buộc của đề bài.
3. **Phụ lục B:** bảng ghi chú công cụ AI đã sử dụng.
4. **Bảng 4.2:** liên kết Kaggle nguồn của 12 bộ dữ liệu (thêm entry `@misc` vào
   `references.bib`).

## Lưu ý về số trang
Bản dựng thử bằng tectonic/XeTeX cho **61 trang** (nội dung Chương 1–5 = 46 trang).
Tuy nhiên engine này thay thế font và **làm rơi phần lớn dấu tiếng Việt**, nên
dòng chữ ngắn lại và số trang bị **đếm thiếu**. Bản pdfLaTeX thật (đúng font T5)
sẽ dài hơn đáng kể. **Hãy compile trên Overleaf và kiểm tra lại** phần Chương 1–5
có đạt mốc 50 trang hay chưa; nếu thiếu, phần dễ mở rộng nhất là Mục 4.5 (baseline)
sau khi có số liệu thật.

Phân bố hiện tại (đo bằng tectonic): Ch1 = 6, Ch2 = 10, Ch3 = 10, Ch4 = 16, Ch5 = 4.

## Tính trung thực của số liệu
Toàn bộ số liệu trong Chương 4 lấy từ `report/report_v2.md` (nhánh `phat`): 4
framework × 12 dataset × 5 fold, ngân sách 60s và 300s. Các ô `[ ]` là phần chưa
có dữ liệu — không suy đoán hay điền số giả.
