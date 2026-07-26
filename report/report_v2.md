### Giới thiệu các framework

#### AutoGluon
AutoGluon áp dụng chiến lược **stacked ensembling đa tầng**: huấn luyện nhiều mô hình cơ sở (LightGBM, CatBoost, XGBoost, Random Forest, Neural Net) rồi dùng meta-learner để kết hợp đầu ra. Cách tiếp cận này hướng tới độ chính xác và độ ổn định cao, đặc biệt trên dữ liệu có không gian đặc trưng lớn và hỗn hợp, nơi ensemble nhiều tầng có lợi thế. Đổi lại, việc duy trì toàn bộ stack trong RAM khiến mức tiêu thụ bộ nhớ tăng theo quy mô dữ liệu. AutoGluon có cơ chế fallback tự động khi một mô hình thành phần thất bại, giúp pipeline hoàn thành ngay cả khi một số mô hình gặp lỗi.

#### FLAML
FLAML dùng thuật toán tối ưu siêu tham số **CFO (Cost-Frugal Optimization)** kết hợp lịch trình ưu tiên các mô hình nhẹ (LightGBM, XGBoost) trước khi thử các lựa chọn đắt hơn. Triết lý thiết kế của FLAML là đạt cấu hình tốt với chi phí tính toán thấp nhất có thể, nên framework này hướng tới mức tiêu thụ bộ nhớ nhỏ và thời gian huấn luyện thấp, đặc biệt phù hợp với dữ liệu lớn nhưng đặc trưng đơn giản. Cách tìm kiếm tiết kiệm này đánh đổi bằng khả năng bao phủ hạn chế hơn trên các bài toán cần mô hình phức tạp.

#### H2O AutoML
H2O chạy trên **JVM server riêng biệt**: toàn bộ quá trình huấn luyện diễn ra trong tiến trình Java, Python chỉ giao tiếp qua REST API. Vì vậy, mức RAM đo từ phía Python không phản ánh tiêu thụ thực tế, do phần lớn bộ nhớ huấn luyện nằm trong JVM. H2O kết hợp các mô hình GLM + GBM + Stacking được tối ưu kỹ, mạnh ở nhóm hồi quy và phân loại nhị phân cân bằng. Chiến lược huấn luyện tuần tự từng mô hình khiến H2O thường dùng gần hết time budget và có thể gặp khó khi dữ liệu quá lớn hoặc nhiều chiều, khi thời gian load và huấn luyện vượt quá ngân sách cho phép.

#### MLJAR
MLJAR xây dựng **pipeline ML tùy chỉnh** cho từng bộ dữ liệu: feature engineering tự động (tạo đặc trưng tương tác, encoding đặc biệt), chọn thuật toán qua Optuna, và tạo ensemble từ các pipeline tốt nhất. Cách tiếp cận này hướng tới dữ liệu có không gian đặc trưng cao và các bài toán hồi quy phi tuyến. Thời gian chạy của MLJAR biến động theo độ rộng của không gian tìm kiếm: có thể kết thúc sớm khi tìm được pipeline tốt, nhưng cũng chậm khi phải duyệt nhiều lựa chọn.

---

## Datasets

Thực nghiệm được tiến hành trên 12 bộ dữ liệu thu thập từ Kaggle, bao gồm ba dạng bài toán: phân loại nhị phân (5 bộ), phân loại đa lớp (3 bộ) và hồi quy (4 bộ). Các bộ dữ liệu được lựa chọn dựa trên tiêu chí đa dạng về quy mô, số lượng đặc trưng, tỉ lệ mất cân bằng nhãn và mức độ khó, nhằm đánh giá toàn diện khả năng của các framework AutoML trong nhiều tình huống thực tế. Độ đo được chọn là AUC cho phân loại nhị phân, Accuracy cho phân loại đa lớp và RMSE cho hồi quy.

| # | Dataset | Task | Metric | Rows | Features |
|---|---------|------|--------|------|----------|
| 1 | adult_income | Binary classification | AUC | 32,561 | 13 |
| 2 | breast_cancer | Binary classification | AUC | 569 | 30 |
| 3 | give_me_credit | Binary classification | AUC | 150,000 | 10 |
| 4 | santander_satisfaction | Binary classification | AUC | 76,020 | 369 |
| 5 | telco_churn | Binary classification | AUC | 7,043 | 19 |
| 6 | forest_cover | Multiclass classification | Accuracy | 581,012 | 54 |
| 7 | obesity | Multiclass classification | Accuracy | 2,111 | 16 |
| 8 | wine | Multiclass classification | Accuracy | 178 | 13 |
| 9 | abalone | Regression | RMSE | 4,177 | 8 |
| 10 | california_housing | Regression | RMSE | 20,640 | 8 |
| 11 | house_prices | Regression | RMSE | 1,460 | 79 |
| 12 | wine_quality | Regression | RMSE | 1,599 | 11 |


## Experiment

## Kết quả

### Bảng tổng hợp điểm số

| Dataset | Framework | Metric | Score (mean ± std) | Thời gian (s) | Bộ nhớ (MB) |
|---------|-----------|--------|-------------------|--------------|-------------|
| abalone | autogluon | rmse | 2.1130 ± 0.1437 | 97.3 | 229.6 |
| abalone | flaml | rmse | 2.1473 ± 0.1337 | 326.9 | 107.2 |
| abalone | h2o | rmse | **2.1125 ± 0.1308** | 307.6 | 23.0 |
| abalone | mljar | rmse | 2.1324 ± 0.1512 | 335.3 | 234.2 |
| adult_income | autogluon | auc | 0.9299 ± 0.0016 | 262.0 | 357.0 |
| adult_income | flaml | auc | 0.9295 ± 0.0015 | 331.4 | 114.4 |
| adult_income | h2o | auc | 0.9283 ± 0.0019 | 310.5 | 31.1 |
| adult_income | mljar | auc | **0.9301 ± 0.0018** | 369.3 | 285.9 |
| breast_cancer | autogluon | auc | 0.9945 ± 0.0045 | 78.9 | 205.5 |
| breast_cancer | flaml | auc | 0.9941 ± 0.0042 | 327.2 | 103.6 |
| breast_cancer | h2o | auc | **0.9947 ± 0.0059** | 308.7 | 24.6 |
| breast_cancer | mljar | auc | 0.9933 ± 0.0066 | 353.5 | 214.2 |
| california_housing | autogluon | rmse | 0.4408 ± 0.0104 | 325.0 | 528.8 |
| california_housing | flaml | rmse | 0.4528 ± 0.0106 | 329.0 | 120.7 |
| california_housing | h2o | rmse | 0.4383 ± 0.0101 | 309.6 | 28.9 |
| california_housing | mljar | rmse | **0.4324 ± 0.0114** | 334.2 | 212.5 |
| forest_cover | autogluon | log_loss | 0.4593 ± 0.0127 | 113.2 | 1284.8 |
| forest_cover | flaml | log_loss | **0.4501 ± 0.1409** | 103.3 | 1481.3 |
| give_me_credit | autogluon | auc | 0.8654 ± 0.0053 | 320.0 | 839.9 |
| give_me_credit | flaml | auc | **0.8659 ± 0.0038** | 280.9 | 153.1 |
| give_me_credit | h2o | auc | 0.8592 ± 0.0034 | 327.4 | 88.8 |
| give_me_credit | mljar | auc | 0.8654 ± 0.0044 | 72.6 | 223.6 |
| house_prices | autogluon | rmse | **28708.49 ± 7647.33** | 87.4 | 220.3 |
| house_prices | flaml | rmse | 29053.14 ± 9052.32 | 113.2 | 104.1 |
| house_prices | h2o | rmse | 29362.74 ± 11357.00 | 308.7 | 23.8 |
| house_prices | mljar | rmse | 30737.50 ± 9153.25 | 83.4 | 158.9 |
| obesity | autogluon | log_loss | 0.0851 ± 0.0201 | 75.1 | 245.3 |
| obesity | h2o | log_loss | **0.0737 ± 0.0246** | 311.6 | 22.9 |
| obesity | mljar | log_loss | 0.0861 ± 0.0222 | 90.7 | 168.9 |
| santander_satisfaction | autogluon | auc | 0.8373 ± 0.0071 | 343.9 | 1132.3 |
| santander_satisfaction | flaml | auc | 0.8323 ± 0.0097 | 89.8 | 1200.1 |
| santander_satisfaction | mljar | auc | **0.8383 ± 0.0054** | 90.1 | 703.7 |
| telco_churn | autogluon | auc | 0.8439 ± 0.0138 | 68.0 | 213.8 |
| telco_churn | flaml | auc | 0.8475 ± 0.0136 | 87.1 | 103.2 |
| telco_churn | h2o | auc | **0.8486 ± 0.0130** | 335.9 | 25.3 |
| telco_churn | mljar | auc | 0.8475 ± 0.0129 | 95.9 | 174.2 |
| wine | autogluon | accuracy | 0.9660 ± 0.0314 | 43.5 | 203.9 |
| wine | flaml | accuracy | **0.9722 ± 0.0000** | 108.5 | 101.4 |
| wine | h2o | accuracy | 0.9721 ± 0.0340 | 321.1 | 22.9 |
| wine | mljar | accuracy | 0.9717 ± 0.0350 | 93.0 | 170.9 |
| wine_quality | autogluon | rmse | 0.5852 ± 0.0369 | 41.3 | 212.7 |
| wine_quality | flaml | rmse | 0.5906 ± 0.0342 | 84.4 | 103.6 |
| wine_quality | h2o | rmse | **0.5706 ± 0.0242** | 320.9 | 22.9 |
| wine_quality | mljar | rmse | 0.5866 ± 0.0345 | 88.2 | 158.3 |

### Nhận xét

Nhìn chung, kết quả cho thấy sự cạnh tranh sát sao giữa các framework trên hầu hết các bộ dữ liệu, đặc biệt ở nhóm phân loại nhị phân (AUC dao động trong khoảng rất hẹp, ví dụ adult_income chênh lệch chỉ 0.002 giữa framework tốt nhất và tệ nhất). Điều này phản ánh tính bão hòa của các bài toán phân loại nhị phân tiêu chuẩn khi thời gian huấn luyện đủ lớn.

**Phân loại nhị phân (AUC):** Không có framework nào thống trị rõ ràng. MLJAR đạt AUC cao nhất trên adult_income (0.9301) và santander_satisfaction (0.8383); H2O dẫn đầu trên breast_cancer (0.9947) và telco_churn (0.8486); FLAML tốt nhất trên give_me_credit (0.8659). AutoGluon cho kết quả ổn định và cạnh tranh trên toàn bộ nhóm này.

**Phân loại đa lớp:** H2O vượt trội trên obesity với log_loss thấp nhất (0.0737), trong khi FLAML đạt log_loss tốt hơn AutoGluon trên forest_cover (0.4501 so với 0.4593). Đáng chú ý, H2O và MLJAR không hoàn thành được các fold trên một số bộ dữ liệu lớn (forest_cover với 581,012 mẫu), cho thấy giới hạn về khả năng xử lý dữ liệu quy mô lớn trong thời gian ngắn.

**Hồi quy (RMSE):** MLJAR cho kết quả tốt nhất trên california_housing (0.4324); H2O dẫn đầu trên abalone (2.1125) và wine_quality (0.5706); AutoGluon tốt nhất trên house_prices (28,708). FLAML có xu hướng cho RMSE cao hơn (kém hơn) trên nhóm hồi quy so với các framework khác.

**Tài nguyên:** H2O tiêu thụ bộ nhớ thấp nhất (trung bình ~40–90 MB nhờ xử lý trên JVM server riêng), trong khi AutoGluon và MLJAR có mức tiêu thụ RAM cao hơn đáng kể, đặc biệt trên các bộ dữ liệu lớn như give_me_credit (~840 MB) và santander_satisfaction (~1,132 MB). Về thời gian huấn luyện, AutoGluon thường hoàn thành nhanh hơn trên các bộ dữ liệu nhỏ nhờ cơ chế early stopping hiệu quả, trong khi FLAML và H2O thường sử dụng gần hết time budget được cấp.

---

## Nhận xét mỗi ảnh (Tham khảo cho report)

---

## dataset_pie.png

### Caption
Biểu đồ tròn thể hiện phân bố 12 bộ dữ liệu thực nghiệm theo dạng bài toán: Phân loại nhị phân (45%, 5 bộ), Phân loại đa lớp (27%, 3 bộ) và Hồi quy (27%, 4 bộ).

### Nhận xét
Thực nghiệm được thiết kế với sự thiên lệch nhẹ về phân loại nhị phân (chiếm gần một nửa), phản ánh sự phổ biến của dạng bài toán này trong các benchmark AutoML thực tế. Hai dạng còn lại được phân bổ đều nhau, đảm bảo đánh giá toàn diện trên cả ba tác vụ chính.

---

## dataset_summary.png

### Caption
Hai biểu đồ cột ngang thể hiện quy mô và độ phức tạp đặc trưng của từng bộ dữ liệu: (trái) số lượng mẫu (rows), (phải) số lượng đặc trưng phân chia theo loại numeric và categorical.

### Nhận xét
Các bộ dữ liệu có sự chênh lệch rất lớn về quy mô — từ wine (178 mẫu) đến forest_cover (581,012 mẫu, gấp hơn 3,000 lần). Về đặc trưng, santander_satisfaction nổi bật với 369 đặc trưng (toàn bộ numeric), trong khi hầu hết các bộ khác có dưới 30 đặc trưng. Sự đa dạng này kiểm tra khả năng thích nghi của các framework trên nhiều tình huống thực tế khác nhau.

---

## dataset_target_dist.png

### Caption
Lưới 11 biểu đồ phân phối nhãn mục tiêu của từng bộ dữ liệu. Các bộ phân loại hiển thị histogram đếm số mẫu mỗi lớp; các bộ hồi quy hiển thị histogram của giá trị liên tục.

### Nhận xét
Nhiều bộ dữ liệu phân loại nhị phân có mất cân bằng nhãn đáng kể: santander_satisfaction (~94% nhãn âm), give_me_credit (~93% không vỡ nợ, missing 2%), adult_income (~75% thu nhập thấp). Điều này đặt ra thách thức cho AutoML phải xử lý class imbalance tự động. Ngược lại, obesity và wine có phân phối tương đối cân bằng. Các bộ hồi quy như abalone và wine_quality có phân phối gần chuẩn, trong khi california_housing có đuôi dài bên phải.

---

## experiment_scaled_perf.png

### Caption
Boxplot điểm số đã chuẩn hóa [0–1] (1 = framework tốt nhất trên bộ dữ liệu đó) của mỗi framework. Trái: tổng hợp trên toàn bộ 12 dataset. Phải: phân nhóm theo tác vụ (Binary, Multiclass, Regression).

### Nhận xét
Nhìn chung, cả 4 framework có trung vị tương đương nhau (~0.6), nhưng phân phối khác nhau rõ rệt khi tách theo tác vụ. Ở **Binary**, AutoGluon có trung vị cao nhất và ổn định, trong khi H2O có đuôi dưới thấp (thất bại trên một số dataset). Ở **Multiclass**, H2O vượt trội rõ ràng với IQR hoàn toàn nằm trong khoảng [0.6, 0.95+], các framework còn lại có box rộng hơn và nhiều outlier gần 0. Ở **Regression**, H2O và MLJAR dẫn đầu, FLAML có trung vị thấp nhất và đuôi xuống gần 0, cho thấy FLAML gặp khó khăn trên các bài toán hồi quy phức tạp.

---

## experiment_score_boxplots_by_task.png

### Caption
Boxplot phân phối điểm số thô (raw score) trên 5 fold CV của từng cặp (dataset × framework), nhóm theo tác vụ. Mỗi cụm trên trục x là một dataset, 4 box màu tương ứng 4 framework.

### Nhận xét
**Binary:** Các bộ dữ liệu nhỏ (breast_cancer) có IQR rất hẹp, cho thấy kết quả ổn định qua các fold. Dataset lớn như santander_satisfaction và telco_churn có độ biến động cao hơn. Các framework cạnh tranh sát sao, chênh lệch AUC thường dưới 0.01. **Multiclass:** forest_cover bộc lộ vấn đề nghiêm trọng — FLAML chỉ hoàn thành 4/5 fold với IQR rất rộng (~0.1 đến ~0.7), cho thấy kết quả không ổn định trên dataset 581k mẫu. Wine cho kết quả gần hoàn hảo (~0.97) với mọi framework. **Regression:** house_prices có biến động lớn nhất (IQR rộng, nhiều outlier ở mức 40,000–50,000 RMSE), phản ánh độ khó cao của dataset này. Các dataset nhỏ (abalone, wine_quality) cho kết quả ổn định hơn nhiều.

---

## experiment_score_vs_time.png

### Caption
Scatter plot điểm số trung bình theo thời gian huấn luyện trung bình (log scale), phân thành 3 panel theo tác vụ. Màu sắc = framework, ký hiệu điểm = dataset.

### Nhận xét
**Binary:** AutoGluon hoàn thành rất nhanh (50–100s) trên hầu hết dataset nhờ early stopping, trong khi FLAML, H2O, MLJAR thường sử dụng gần hết 300s budget. Điểm số của AutoGluon trên breast_cancer (~0.995) đạt được chỉ sau 78s — hiệu quả nhất về tỉ lệ điểm/thời gian. **Multiclass:** H2O và MLJAR vắng mặt trên forest_cover (thất bại), chỉ thấy AutoGluon (~0.96) và FLAML với điểm số biến động cao. Wine đạt gần 1.0 với mọi framework chỉ sau 43–108s. **Regression:** Các framework phân cụm gần nhau về điểm số nhưng rải rác về thời gian — H2O luôn dùng đủ 300s, AutoGluon hoàn thành sớm hơn mà vẫn cạnh tranh được.

---

## experiment_perf_by_budget.png

### Caption
So sánh hiệu năng chuẩn hóa giữa hai mức time budget (60s và 300s). Trái: biểu đồ cột nhóm trung bình ± std theo framework. Phải: đường kẻ thể hiện trajectory của từng framework khi tăng budget, với vùng tin cậy ±1 std.

### Nhận xét
Tất cả framework đều cải thiện điểm số khi tăng budget từ 60s lên 300s, nhưng mức cải thiện khác nhau rõ rệt. **MLJAR** có mức tăng lớn nhất (0.59 → 0.79), cho thấy framework này chưa kịp hội tụ ở 60s và tận dụng tốt thời gian thêm để mở rộng không gian tìm kiếm. **FLAML** cũng cải thiện đáng kể nhờ CFO tiếp tục tinh chỉnh cấu hình. **AutoGluon** và **H2O** cải thiện ít hơn — AutoGluon vì đã đạt điểm tốt ở 60s trên nhiều dataset nhỏ, H2O vì chiến lược huấn luyện tuần tự ít phụ thuộc vào budget ngắn. Vùng tin cậy rộng phản ánh hiệu năng biến động cao theo dataset.

---

## experiment_inference_speed.png

### Caption
Boxplot thời gian inference (giây, thang log) của mỗi framework trên tất cả các fold thực nghiệm.

### Nhận xét
**FLAML** có inference nhanh nhất (trung vị ~0.25s) nhờ mô hình gọn nhẹ (LightGBM/XGBoost đơn lẻ). **H2O** có phân phối hẹp nhất (trung vị ~0.65s, IQR nhỏ), phản ánh sự nhất quán của mô hình stacking GLM+GBM. **MLJAR** có trung vị ~1.0s do pipeline tùy chỉnh phức tạp hơn. **AutoGluon** có outlier cao nhất (lên đến 10s+) do stack nhiều tầng mô hình, mặc dù trung vị (~0.8s) vẫn chấp nhận được. Nhìn chung, tất cả framework đều có thời gian inference dưới 2s ở mức trung vị — phù hợp cho hầu hết ứng dụng thực tế.

---

## experiment_memory_usage.png

### Caption
Mức sử dụng bộ nhớ đỉnh (MB) đo từ phía Python. Trái: heatmap theo từng cặp (dataset × framework). Phải: trung bình toàn bộ dataset theo framework.

### Nhận xét
**AutoGluon** tiêu thụ nhiều RAM nhất (trung bình 473 MB), đặc biệt trên give_me_credit (~840 MB) và santander_satisfaction (~1,132 MB) — phản ánh chi phí của stacked ensembling đa tầng giữ nhiều mô hình trong bộ nhớ đồng thời. **FLAML** đứng thứ hai (336 MB) nhưng cũng đạt 1,481 MB trên forest_cover — cao bất thường, có thể do dataset 581k mẫu đẩy LightGBM vượt giới hạn thông thường. **H2O** có số liệu bộ nhớ thấp nhất (trung bình chỉ 31 MB từ phía Python) vì toàn bộ quá trình huấn luyện diễn ra trong JVM — con số này **không phản ánh thực tế** mức RAM tiêu thụ của H2O server. **MLJAR** ở mức vừa phải (246 MB), với mức cao nhất trên santander_satisfaction (704 MB) do không gian đặc trưng 369 chiều.

---

## experiment_failures.png

### Caption
Phân tích lỗi theo 3 góc nhìn: (A) tỉ lệ lỗi theo framework và loại lỗi (stacked bar), (B) bubble chart tỉ lệ lỗi theo kích thước dataset (n_rows × n_features), (C) tỉ lệ lỗi theo time budget.

### Nhận xét
**Panel A:** FLAML và H2O có tỉ lệ lỗi cao nhất (~16%), AutoGluon gần như không thất bại. H2O gặp cả hai loại lỗi oom và timeout, trong khi FLAML và MLJAR chủ yếu là timeout. **Panel B:** Lỗi tập trung ở góc trên phải của biểu đồ — dataset lớn với nhiều đặc trưng (forest_cover: ~581k mẫu, 54 đặc trưng) là điểm nóng thất bại, với H2O và FLAML có bubble lớn nhất tại đây. Các dataset nhỏ (dưới 10k mẫu) hầu như không có lỗi. **Panel C:** FLAML cải thiện mạnh khi tăng budget (26% → 4%), cho thấy phần lớn lỗi ở 60s là do timeout — thêm thời gian giải quyết được vấn đề. Ngược lại, MLJAR tăng lỗi từ 0% lên 20% khi budget = 300s, một nghịch lý có thể do pipeline phức tạp hơn được kích hoạt với budget dài làm tăng xác suất gặp lỗi bộ nhớ.

---

## experiment_bradley_terry.png

### Caption
Bradley-Terry Tree: so sánh sức mạnh tương đối (λ) của các framework theo mô hình xếp hạng dựa trên thắng/thua cặp đôi. Panel trái = mô hình toàn cục, 3 panel còn lại = mô hình riêng cho từng tác vụ (lá của cây).

### Nhận xét
Kết quả Bradley-Terry tiết lộ sự đảo chiều xếp hạng rõ rệt khi phân tách theo tác vụ — đây là lý do chính để sử dụng cây thay vì mô hình toàn cục đơn giản. **Toàn cục:** H2O (λ=0.282) > MLJAR (0.278) > AutoGluon (0.257) > FLAML (0.183) — FLAML bị kéo xuống bởi hiệu năng yếu ở hồi quy. **Binary:** Thứ hạng đảo hoàn toàn — MLJAR (0.330) dẫn đầu, FLAML vươn lên thứ hai (0.259), trong khi H2O tụt xuống cuối (0.164). **Multiclass:** H2O thống trị tuyệt đối (λ=0.446, cách biệt gần gấp đôi so với FLAML và AutoGluon cùng 0.197), MLJAR yếu nhất (0.161). **Regression:** H2O tiếp tục dẫn đầu (0.389), FLAML cuối bảng (0.105) — xác nhận FLAML không phù hợp với bài toán hồi quy trong cài đặt này. Mô hình BT Tree cho thấy không có framework nào vượt trội toàn diện: lựa chọn tối ưu phụ thuộc vào tác vụ.
