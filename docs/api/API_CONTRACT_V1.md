# W2.3 — API Contract v1

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | `0.1.0-draft` |
| Ngày | 10/09/2026 |
| Trạng thái | REVIEW CANDIDATE |
| WBS | `W2.3` |
| Owner | Nguyễn Trần Ngọc Quý (Q) |
| Reviewer | Võ Thị Kim Yến (Y) |
| Phụ thuộc | `W2.1`, `W2.2` |
| Machine-readable contract | [`openapi-v1.yaml`](./openapi-v1.yaml) |

## 1. Mục đích và phạm vi

Contract này khóa boundary HTTP cho luồng P0:

- session authentication, workspace scope và RBAC;
- report/source upload và immutable document version;
- job/run/progress cho tác vụ dài;
- chunk/evidence với stable locator;
- rubric version, analysis proposal, lecturer review và publication;
- error envelope, cursor pagination, idempotency và optimistic concurrency.

Đây là contract toàn phạm vi, không phải danh sách mọi route đã hiện thực.
[Authenticated Mongo app](../architecture/authenticated-mongo-app.md) đã có
session/workspace, rubric lifecycle, report/source upload/version, PARSE job
và chunk routes. INDEX/ANALYZE, review/publication/lifecycle/graph API vẫn chưa
nối vào app này. Report và source upload đều cần governance_record_id hợp lệ
trước khi parse; không có bypass quyền bằng chế độ demo.

## 2. Quyết định protocol

| Hạng mục | Quyết định v1 |
|---|---|
| Base path | `/api/v1` |
| Media type | JSON UTF-8; upload dùng `multipart/form-data` |
| Auth | Server-side session bằng cookie `HttpOnly`, `SameSite=Lax`; production/network deployment bắt buộc `Secure` |
| CSRF | Mọi authenticated unsafe method phải có `X-CSRF-Token`; login dùng origin/rate-limit protection |
| API identifier | Chuỗi opaque; client không suy luận MongoDB `ObjectId` |
| Timestamp | RFC 3339 UTC |
| Long task | Trả `202 Accepted` với `job_id` và resource/run ID; không chạy parse/AI trong request |
| Concurrency | Mutable resource trả `ETag`; update/action yêu cầu `If-Match` |
| Idempotency | `Idempotency-Key` bắt buộc cho create/action có side effect hoặc retry qua mạng |
| Pagination | Cursor opaque; `limit` mặc định 25, tối đa 100; stable order có tie-break `_id` nội bộ |
| Request trace | Client có thể gửi `X-Request-ID`; server validate hoặc tạo mới và luôn trả lại |
| Error | Một envelope thống nhất, không trả stack trace, path, secret hoặc raw content |

Session cookie không phải quyết định deployment Internet-ready. Nếu `OQ-18`
chuyển demo từ localhost sang LAN/Internet, phải review TLS, cookie domain,
reverse proxy, session store, expiry và CSRF trước khi triển khai.

## 3. Authorization model

Server lấy actor, role và workspace membership từ session/authoritative store;
không tin `user_id`, `role`, `workspace_id` hoặc owner do body tự khai báo.

| Capability | Student | Lecturer | Admin |
|---|---:|---:|---:|
| Xem workspace được gán | Có | Có | Có |
| Upload/xem report của mình | Có | Có trong scope | Không |
| Upload/quản lý corpus source | Không | Có trong scope | Không |
| Xem chunk/evidence report khác | Không | Có khi được gán | Không |
| Tạo/publish rubric | Không | Có | Không |
| Chạy similarity/assessment | Không | Có | Không |
| Review/publish proposal | Không | Có trong scope | Không |
| Yêu cầu xóa | Có điều kiện (resource của mình) | Có điều kiện (scope/ủy quyền) | Có điều kiện (authority record) |

Trong bảng trên, `Có` vẫn bị giới hạn bởi workspace/resource scope; `Không`
nghĩa là role đó không có capability trong contract v1. `Có điều kiện` là
**deny mặc định**: role đơn thuần không cấp capability; server chỉ cho phép
theo policy/authority record có version, được lưu ở
authoritative store và khớp actor, workspace, resource, purpose, thời hạn.
Client không được tự khai policy. Một người có nhiều membership được xét từng
membership; Admin không tự động kế thừa quyền học thuật của Lecturer.

Quy tắc bắt buộc:

1. filter workspace/owner/purpose/tombstone trước retrieval và trước trả lỗi;
2. cross-scope ID trả `404 RESOURCE_NOT_FOUND`, không xác nhận resource tồn tại;
3. dataset/source thiếu governance `APPROVED` trả `409 GOVERNANCE_NOT_APPROVED`
   trước enqueue index/run;
4. worker/admin không có endpoint tự publish proposal;
5. student chỉ đọc publication đã `ACTIVE`, không đọc proposal/review nội bộ.

## 4. Header contract

| Header | Hướng | Khi bắt buộc | Ý nghĩa |
|---|---|---|---|
| `X-Request-ID` | Request/response | Response luôn có | Correlation ID an toàn |
| `X-CSRF-Token` | Request | Unsafe authenticated method | Chống CSRF cho cookie session |
| `Idempotency-Key` | Request | Upload, create run, retry, review, publish, delete | Deduplicate cùng actor/scope/operation |
| `If-Match` | Request | Update/state action trên mutable resource | Giá trị dạng `"rev-<n>"` |
| `ETag` | Response | Resource mutable | Revision hiện hành |
| `Retry-After` | Response | `429`, một số `503` | Số giây trước retry |

Cùng `Idempotency-Key` và canonical request hash phải trả cùng operation/result.
Cùng key nhưng body khác trả `409 IDEMPOTENCY_KEY_REUSED`.

## 5. Endpoint v1

### 5.1. Auth và workspace

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/auth/sessions` | Anonymous | `200`; set session cookie và trả CSRF token + actor |
| `GET` | `/auth/me` | Authenticated | Actor, workspace memberships/capabilities |
| `DELETE` | `/auth/session` | Authenticated | `204`; revoke session |
| `GET` | `/workspaces` | Authenticated | Cursor page các workspace được phép |

Login failure luôn dùng thông báo chung `INVALID_CREDENTIALS`, không tiết lộ
email có tồn tại. Session fixation phải bị chặn bằng rotate session ID.

### 5.2. Report và source

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/reports` | Student/Lecturer | Tạo logical report + version 1; `202` và parse `job_id` |
| `GET` | `/workspaces/{workspace_id}/reports` | Scoped | Cursor page report summaries |
| `GET` | `/workspaces/{workspace_id}/reports/{report_id}` | Scoped | Report + current version/state |
| `POST` | `/workspaces/{workspace_id}/reports/{report_id}/versions` | Owner/scoped Lecturer | Tạo immutable version tiếp theo; `202` |
| `POST` | `/workspaces/{workspace_id}/sources` | Lecturer | Tạo source version; governance chưa duyệt vẫn quarantine, không index |
| `GET` | `/workspaces/{workspace_id}/sources` | Lecturer | Cursor page source summaries |
| `GET` | `/workspaces/{workspace_id}/sources/{source_id}` | Lecturer | Source + governance/current version |
| `POST` | `/workspaces/{workspace_id}/sources/{source_id}/versions` | Lecturer | Tạo immutable source version; `202` |
| `GET` | `/workspaces/{workspace_id}/document-versions/{version_id}` | Scoped | Processing/lifecycle/provenance summary |
| `GET` | `/workspaces/{workspace_id}/document-versions/{version_id}/chunks` | Scoped Lecturer/owner | Cursor page chunk + locator |

Upload request gồm `file`, `document_key`, `title`; source thêm
`governance_record_id`. Server sniff magic/MIME, giới hạn size/path, sinh
storage key và checksum. Filename chỉ là untrusted display metadata.

Không có endpoint overwrite file/version. Retry parse dùng job action, không
upload lại dưới cùng version.

### 5.3. Job và progress

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `GET` | `/workspaces/{workspace_id}/jobs/{job_id}` | Scoped owner/Lecturer | State, bounded progress, attempt và safe error code |
| `POST` | `/workspaces/{workspace_id}/jobs/{job_id}:cancel` | Authorized caller | `202`; cancellation_requested |
| `POST` | `/workspaces/{workspace_id}/jobs/{job_id}:retry` | Authorized caller | `202`; cùng resource/config, attempt hữu hạn |

API không expose `lease_owner`, internal checkpoint, stack trace hoặc payload
content. State terminal: `SUCCEEDED`, `FAILED_FINAL`, `CANCELLED`.

### 5.4. Rubric

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/rubrics` | Lecturer | Tạo rubric + draft version đầu |
| `GET` | `/workspaces/{workspace_id}/rubrics` | Lecturer | Cursor page rubric summaries |
| `GET` | `/workspaces/{workspace_id}/rubrics/{rubric_id}` | Lecturer | Rubric + current version |
| `POST` | `/workspaces/{workspace_id}/rubrics/{rubric_id}/versions` | Lecturer | Clone/tạo draft version |
| `PUT` | `/workspaces/{workspace_id}/rubric-versions/{version_id}` | Lecturer | Replace draft với `If-Match` |
| `POST` | `/workspaces/{workspace_id}/rubric-versions/{version_id}:publish` | Lecturer | Validate và publish immutable version |

Published rubric version không update tại chỗ. Weight/rule invalid trả `422`
với field issue; rubric đã được run dùng chỉ có thể clone version.

### 5.5. Analysis, evidence và proposal

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/reports/{report_id}/analysis-runs` | Lecturer | `202`; khóa report/source/index/rubric/config version |
| `GET` | `/workspaces/{workspace_id}/analysis-runs/{run_id}` | Scoped Lecturer | Run state/progress/provenance summary |
| `GET` | `/workspaces/{workspace_id}/analysis-runs/{run_id}/evidence` | Scoped Lecturer | Cursor page evidence items |
| `GET` | `/workspaces/{workspace_id}/analysis-runs/{run_id}/proposal` | Scoped Lecturer | Similarity/assessment proposal khi sẵn sàng |

Create run bị chặn nếu report chưa `READY`, source/dataset chưa được duyệt,
index generation stale/sai scope hoặc rubric chưa published. Request chỉ gửi
ID/version/config đã cho phép; worker resolve authoritative state lại sau claim.

Evidence response bắt buộc có source version, raw locator, bounded quote/hash,
retrieval score và quan hệ `SUPPORTED`, `CONTRADICTED` hoặc `INSUFFICIENT`.
Checklist outcome chỉ là `MET`, `UNMET`, `CANNOT_ASSESS`.

### 5.6. Review và publication

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/assessment-proposals/{proposal_id}/reviews` | Lecturer | `201`; `ACCEPT`, `EDIT` hoặc `REJECT` với evidence validation |
| `GET` | `/workspaces/{workspace_id}/assessment-proposals/{proposal_id}/reviews` | Lecturer | Review history trong scope |
| `POST` | `/workspaces/{workspace_id}/reports/{report_id}/publications` | Lecturer | `201`; publish đúng proposal + review accepted |
| `GET` | `/workspaces/{workspace_id}/reports/{report_id}/publications/current` | Owner/scoped Lecturer | Publication active đã sanitize |

Review yêu cầu `If-Match` proposal revision và `Idempotency-Key`. `EDIT` yêu
cầu reason và giá trị chỉnh; `REJECT` yêu cầu reason. Evidence ID phải thuộc
cùng run/report và locator resolve được. Publish là action riêng, không suy ra
tự động từ `ACCEPT`.

### 5.7. Lifecycle

| Method | Path | Actor | Kết quả chính |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/deletion-requests` | Authorized requester | `202`; tạo request/tombstone theo policy |
| `GET` | `/workspaces/{workspace_id}/deletion-requests/{request_id}` | Authorized requester | State, count và verification summary không chứa content |

API không hứa xóa vật lý đồng bộ. Sau khi tombstone commit, mọi read/retrieval/
job mới bị deny ngay; cleanup file/chunk/index/evidence chạy bất đồng bộ.

## 6. Resource state và HTTP status

| Tình huống | HTTP | Error code/response |
|---|---:|---|
| Create async hợp lệ | `202` | `AsyncOperation` |
| Create review/publication đồng bộ | `201` | Resource + `ETag` nếu mutable |
| Validation field sai | `422` | `VALIDATION_FAILED` + safe field issues |
| Chưa đăng nhập | `401` | `AUTHENTICATION_REQUIRED` |
| Có session nhưng thiếu capability | `403` | `FORBIDDEN` |
| Cursor sai, hết hạn hoặc không khớp scope/filter/sort | `400` | `INVALID_CURSOR` |
| Resource không tồn tại/ngoài scope | `404` | `RESOURCE_NOT_FOUND` |
| Governance chưa được phê duyệt | `409` | `GOVERNANCE_NOT_APPROVED` |
| Purpose yêu cầu không nằm trong governance record hiện hành | `409` | `PURPOSE_NOT_ALLOWED` |
| Revision/idempotency/state conflict | `409` | Code cụ thể |
| File/media type/size sai | `415`/`413` | `UNSUPPORTED_MEDIA_TYPE`/`PAYLOAD_TOO_LARGE` |
| Rate/quota | `429` | `RATE_LIMITED`, có `Retry-After` |
| Dependency tạm lỗi | `503` | `DEPENDENCY_UNAVAILABLE`, không lộ nội bộ |

`200` không được dùng cho response chứa lỗi nghiệp vụ. `500` chỉ trả
`INTERNAL_ERROR` + request ID; chi tiết nằm trong redacted server log.

## 7. Error envelope

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Resource changed; reload and retry.",
    "request_id": "01J...",
    "details": [
      {
        "field": "If-Match",
        "reason": "STALE_REVISION"
      }
    ]
  }
}
```

Code v1 tối thiểu:

`AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`, `CSRF_INVALID`, `FORBIDDEN`,
`RESOURCE_NOT_FOUND`, `VALIDATION_FAILED`, `REVISION_CONFLICT`,
`INVALID_STATE_TRANSITION`, `IDEMPOTENCY_KEY_REUSED`, `GOVERNANCE_NOT_APPROVED`,
`PURPOSE_NOT_ALLOWED`, `INVALID_CURSOR`, `RESOURCE_TOMBSTONED`, `REPORT_NOT_READY`,
`INDEX_GENERATION_STALE`, `EVIDENCE_INVALID`, `PAYLOAD_TOO_LARGE`,
`UNSUPPORTED_MEDIA_TYPE`, `RATE_LIMITED`, `DEPENDENCY_UNAVAILABLE`,
`INTERNAL_ERROR`.

Message không phải stable API contract; client branch theo `code`, không parse
message. `details` chỉ chứa allowlisted field/reason, không chứa file text,
evidence quote, DB query hoặc exception.

`PURPOSE_NOT_ALLOWED` dùng khi governance record đang `APPROVED`, nhưng thao tác
đang yêu cầu (ví dụ index cho chấm báo cáo hoặc chạy experiment) không có trong
`allowed_purposes` của record hiện hành. Lỗi này được kiểm tra trước index,
retrieval và enqueue run; nó khác `403 FORBIDDEN` (actor thiếu capability) và
`409 GOVERNANCE_NOT_APPROVED` (record chưa ở trạng thái được duyệt).

## 8. Cursor pagination

Request:

```text
GET /api/v1/workspaces/{workspace_id}/reports?limit=25&cursor=<opaque>
```

Response:

```json
{
  "items": [],
  "page": {
    "limit": 25,
    "has_more": false,
    "next_cursor": null
  }
}
```

Cursor là random server-side handle hoặc token được authenticated-encrypt
(AEAD), không chỉ ký payload đọc được. Server bind/hash endpoint, actor,
workspace, scope, filter và sort; đồng thời authorize lại membership/policy ở
mỗi page vì cursor không thay thế authorization. Cursor sai/hết hạn trả
`400 INVALID_CURSOR`; không đưa raw query, content hay danh sách Mongo ObjectId
vào cursor.

V1 dùng keyset pagination theo sort tuple bất biến do server định nghĩa và một
unique tie-break. Page đầu khóa high-watermark/as-of boundary vào cursor đã ký;
các page sau giữ cùng boundary, nên item được insert sau page đầu chỉ xuất hiện
trong pagination session mới. Nếu schema/sort/scope thay đổi, cursor cũ bị từ
chối thay vì âm thầm trả một lát cắt khác.

## 9. Evidence và contradiction contract

Hai tầng trạng thái không được trộn:

| Tầng | Enum | Ý nghĩa |
|---|---|---|
| Claim–evidence | `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT` | Quan hệ của evidence span với claim |
| Checklist | `MET`, `UNMET`, `CANNOT_ASSESS` | Kết quả áp rubric sau verification |

“Báo cáo nói A, tài liệu đối chứng nói B” chỉ map
`CONTRADICTED → UNMET` khi B đã được duyệt cho purpose, đủ thẩm quyền và A/B
cùng context. Nếu authority/context chưa đủ thì map
`INSUFFICIENT → CANNOT_ASSESS`. Response giữ cả span A/B và reason code; client
không tự suy luận lại từ quote text.

## 10. Contract tests bắt buộc khi implementation

`AT-W23-*` kiểm tra HTTP contract; `AT-W21-*` kiểm tra kịch bản đối kháng ở
nhiều tầng. Hai bộ test bổ sung cho nhau, không map 1-1. Đặc biệt,
`AT-W23-03` kiểm idempotency của mọi endpoint có side effect, còn
`AT-W21-05`, `AT-W21-10`, `AT-W21-13` lần lượt kiểm replay job, publish và
lifecycle ở tầng tích hợp.

| ID | Test | Threat/control/test liên quan |
|---|---|---|
| `AT-W23-01` | Unauthenticated và CSRF-invalid unsafe request bị chặn | `T-W21-01`; `AT-W21-01` |
| `AT-W23-02` | Cross-workspace/report ID không làm lộ existence/content | `T-W21-02`; `AT-W21-02` |
| `AT-W23-03` | Cùng idempotency key/body trả cùng operation; body khác trả conflict | `C-W21-04`, `C-W21-08`, `C-W21-11`; `AT-W21-05`, `AT-W21-10`, `AT-W21-13` |
| `AT-W23-04` | Stale `If-Match` không overwrite review/rubric/state | `T-W21-10`; `AT-W21-10` |
| `AT-W23-05` | Upload sai MIME/size/path không tạo committed version/job | `T-W21-03`; `AT-W21-03` |
| `AT-W23-06` | API trả `202`, HTTP worker không block request | `T-W21-04`, `T-W21-05`; `AT-W21-05`, `AT-W21-12` |
| `AT-W23-07` | Dataset/source chưa duyệt không tạo index/experiment run | `T-W21-12`; `AT-W21-14` |
| `AT-W23-08` | Evidence cross-run/fake ID/invalid locator bị reject | `T-W21-08`; `AT-W21-08` |
| `AT-W23-09` | Worker/admin không publish; student không đọc draft/review | `T-W21-10`; `AT-W21-10` |
| `AT-W23-10` | Tombstone chặn read/run trước khi physical cascade hoàn tất | `T-W21-13`; `AT-W21-13` |
| `AT-W23-11` | Error/log không chứa content, secret, stack hoặc storage path | `T-W21-11`; `AT-W21-11` |
| `AT-W23-12` | Cursor bind endpoint/actor/scope/filter/sort và stable khi có insert đồng thời | `T-W21-18`, `C-W21-14`; `AT-W21-19` |

## 11. Điểm còn chờ review

- Session duration, remember-me và password/SSO source chưa được khóa.
- Upload size/quota/timeout phải benchmark và chốt ở `W3.3/G-03`.
- Retention/delete authority/SLA/backup aging chờ `W2.6.3` và GVHD/data owner.
- Rubric payload chi tiết chờ Yến khóa template/guideline `W2.5`.
- Similarity proposal schema chi tiết được mở rộng khi `EP-04-S07` bắt đầu.

Các điểm trên không cho phép bỏ auth/scope/governance/evidence guard khỏi v1.

## 12. Definition of Done `W2.3`

- [x] Có base path, auth/CSRF/RBAC và scope rule.
- [x] Bao phủ report/source/upload/version/job/chunk.
- [x] Bao phủ rubric/run/evidence/proposal/review/publication/delete request.
- [x] Có error envelope, pagination, idempotency và revision contract.
- [x] Có evidence/checklist enum và contradiction mapping nhất quán `W2.2`.
- [x] Có OpenAPI draft parse được.
- [ ] Yến review endpoint theo wireframe/permission/rubric flow.
- [x] Đồng bộ review PR `W2.2`: quan hệ
  `document_elements → chunks` qua `chunks.element_ids`; ADR/Data Dictionary
  đã được phê duyệt và merge trong PR #6.
- [ ] Contract tests chạy khi API được hiện thực ở `W3.x`.

`W2.3` chỉ chuyển `DONE` sau review; implementation/test runtime không được ghi
là đã hoàn thành trong design task này.
