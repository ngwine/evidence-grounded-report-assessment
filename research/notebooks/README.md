
# Notebooks thực nghiệm Pipeline 1 (PAN-PC-11)

Ba notebook này **ghi lại các lần chạy thật**. Chúng dùng để xem lại; không có ý định chạy lại trên máy cá nhân vì cần GPU, Google Drive hoặc Kaggle và dữ liệu PAN-PC-11. Phần code chạy lại được trên máy nằm ở `research/offline_retrieval/` và `research/tests/`.

| Phần         | Việc                                               | Notebook                                                       | Chạy ở        |
| ------------- | --------------------------------------------------- | -------------------------------------------------------------- | --------------- |
| 1. Dựng pool | Dựng pool Test (300 parent) và Train (500 parent) | `p1_colab_build_pools_and_finetune` (Bước 1–10)           | Colab           |
| 2. BM25       | BM25 trên 2 pool, 2 cách cắt đoạn              | `p1_kaggle_bm25`                                             | Kaggle (CPU)    |
| 3. Dense      | E5 trên 2 pool, 2 cách cắt đoạn                | `p1_kaggle_dense`                                            | Kaggle (GPU T4) |
| 4. Train      | Dữ liệu cặp, fine-tune reranker v1 và v2        | `p1_colab_build_pools_and_finetune` (Bước 11–15, Phần 3) | Colab (GPU)     |
| 5. Val        | Chọn cấu hình rerank trên val rồi khoá        | cùng notebook (Bước 14, 16)                                 | Colab           |
| 6. Test       | Chấm Test một lần với cấu hình đã khoá     | cùng notebook (Bước 17)                                     | Colab (GPU)     |
| 7. Kết quả  | Bảng điểm, bootstrap, kết luận                 | cùng notebook (Bước 18)                                     | Colab           |

**Thứ tự chạy thực tế:** Colab (dựng pool, lưu lên Drive) → Kaggle (BM25, Dense) → Colab (dữ liệu cặp, fine-tune, Test, kết quả).

**Ghi chú:**

- Các ô "vá code" ở đầu notebook Kaggle chỉ cần khi dataset code trên Kaggle còn là bản cũ. Sau khi dựng lại zip code từ repo hiện tại thì không cần nữa.
- Output được giữ lại ở cả ba notebook để xem kết quả mà không cần chạy (đã bỏ các thanh tiến độ để GitHub hiển thị được). Số liệu chính nằm trong bài báo và trong `docs/benchmarks/`.
- Các ô của v1 trong notebook Colab đã đóng băng: chạy lại sẽ ghi đè dữ liệu và mô hình v1.
