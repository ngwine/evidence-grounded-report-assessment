# Integrations

Adapter cho các thành phần bên ngoài. Business module chỉ phụ thuộc
interface/contract để có thể thay parser, model, retrieval engine hoặc provider
sau benchmark.

| Adapter | Trách nhiệm |
|---|---|
| `parsers` | Bóc tách PDF/DOCX thành cấu trúc chương, mục, đoạn văn |
| `indexing` | Lập chỉ mục BM25 (lexical) và Dense Vector (embedding) |
| `retrieval` | Hybrid Retrieval, RRF, Cross-Encoder re-ranking |
| `graph` | Evidence Graph – biểu diễn và truy xuất quan hệ tri thức (HippoRAG-style) |
| `local_ai` | Local AI runtime (LLM inference, embedding generation) |
| `storage` | File storage cho uploads và model weights |
| `search_provider` | External search; fail-closed, mặc định disabled |

