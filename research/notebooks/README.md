
# Notebooks thực nghiệm Pipeline 1 (PAN-PC-11)

Các notebook trong thư mục này **ghi lại các lần chạy thật**. Chúng dùng để xem lại; không có ý định chạy lại trên máy cá nhân vì cần GPU, Google Drive hoặc Kaggle và dữ liệu PAN-PC-11. Phần code chạy lại được trên máy nằm ở `research/offline_retrieval/` và `research/tests/`.

```
research/notebooks/
  main_pipeline/     # Phần 1 đến 7: pool Test và Train, fine-tune v1, chấm Test
  simulated_extra/   # Phần 8: tập bổ sung gồm parent simulated (Mục 5.6 của bài)
  README.md
```

## main_pipeline/ (Phần 1 đến 7)

| Phần         | Việc                                               | Notebook                                              | Chạy ở        |
| ------------- | --------------------------------------------------- | ----------------------------------------------------- | --------------- |
| 1. Dựng pool | Dựng pool Test (300 parent) và Train (500 parent) | `p1_colab_build_pools_and_finetune` (Bước 1–10)  | Colab           |
| 2. BM25       | BM25 trên 2 pool, 2 cách cắt đoạn              | `p1_kaggle_bm25`                                    | Kaggle (CPU)    |
| 3. Dense      | E5 trên 2 pool, 2 cách cắt đoạn                | `p1_kaggle_dense`                                   | Kaggle (GPU T4) |
| 4. Train      | Dữ liệu cặp, fine-tune reranker v1 và v2        | `p1_colab_build_pools_and_finetune` (Bước 11–15) | Colab (GPU)     |
| 5. Val        | Chọn cấu hình rerank trên val rồi khoá        | cùng notebook (Bước 14, 16)                        | Colab           |
| 6. Test       | Chấm Test một lần với cấu hình đã khoá     | cùng notebook (Bước 17)                            | Colab (GPU)     |
| 7. Kết quả  | Bảng điểm, bootstrap, kết luận                 | cùng notebook (Bước 18)                            | Colab           |

**Thứ tự chạy thực tế:** Colab (dựng pool, lưu lên Drive) → Kaggle (BM25, Dense) → Colab (dữ liệu cặp, fine-tune, Test, kết quả).

## simulated_extra/ (Phần 8)

Tập bổ sung gồm 179 parent `simulated` (văn bản do người viết lại), dựng từ PAN-PC-11 với seed 20261125 và loại trừ mọi parent, tài liệu nghi vấn và tài liệu nguồn của 5 tập trước (Train/Validation, Test, DEV0, DEV1, DEV-v2). Pool có 280 truy vấn, 2.000 tài liệu (161 nguồn dương, 1.839 distractor) và 399.148 chunk. **Không huấn luyện lại, không chỉnh tham số**: v1 và cấu hình khoá (K = 50, MaxP 4 đoạn, β = 1) giữ nguyên như Test.

| Phần          | Việc                                                                                      | Notebook                            | Chạy ở                                 |
| -------------- | ------------------------------------------------------------------------------------------ | ----------------------------------- | ---------------------------------------- |
| 8a. Dựng pool | Chọn parent, dựng pool, kiểm tra, nén, SHA-256 (Bước 1–4)                           | `p1_colab_simulated_extra`        | Colab                                    |
| 8b. BM25       | BM25 trên pool simulated                                                                  | `p1_kaggle_simulated_extra_bm25`  | Kaggle (CPU), 4,1 phút                  |
| 8c. Dense      | E5 trên pool simulated                                                                    | `p1_kaggle_simulated_extra_dense` | Kaggle (GPU T4), 58,3 phút              |
| 8d. Chấm v1   | Dựng 50 ứng viên, chấm v1 và mô hình gốc, bảng kết quả, bootstrap (Bước 6–7) | `p1_colab_simulated_extra`        | Colab (GPU T4), 3,0 phút mỗi mô hình |

**Thứ tự chạy:** Colab (Bước 1–4, ra `pan-pc11-simulated-v1.zip`) → Kaggle (BM25, Dense) → Colab (Bước 6–7).

**Kết quả chính (mức parent, 179 parent):** Recall@1 của v1 là 0,966, so với 0,933 của BM25 (hiệu số +0,034, khoảng tin cậy 95% [+0,006, +0,067], v1 thắng 7 parent, thua 1, hòa 171). Biên này mỏng, và tập này không có parent dịch hay artificial.

## Ghi chú

- Output được giữ lại ở các notebook để xem kết quả mà không cần chạy (đã bỏ các thanh tiến độ để GitHub hiển thị được). Số liệu chính nằm trong bài báo và trong `docs/benchmarks/`.
- Các ô của v1 trong notebook Colab đã đóng băng: chạy lại sẽ ghi đè dữ liệu và mô hình v1. Phần 8 chỉ đọc v1 từ `finetune/model_final`, không ghi vào đó.
- Kết quả thô (`predictions.jsonl`, `metrics.json`, `run_manifest.json`) nằm trong các file zip lưu trên Drive `KLTN/simulated_extra/`; `research/results/` bị `.gitignore` nên không vào repo.
