# Smart Study Assistant Backend (FastAPI)

Backend hoàn chỉnh cho dự án **Smart Study Assistant**, map trực tiếp tới schema PostgreSQL trong `database/schema.sql`.

## 1. Công nghệ

- FastAPI
- SQLAlchemy 2.x ORM
- PostgreSQL + pgvector tùy chọn
- Alembic (baseline + migration về sau)
- JWT access token + refresh token rotation
- Argon2 password hashing
- PDF/DOCX/TXT ingestion
- PostgreSQL Full-Text Search fallback cho RAG
- OpenAI-compatible AI provider (tùy cấu hình)
- DOCX/PDF export

## 2. Kiến trúc thư mục

```text
app/
├── api/
│   ├── deps.py
│   └── v1/
│       ├── router.py
│       └── routers/
├── core/
│   ├── config.py
│   └── security.py
├── db/
│   ├── models.py        # 45 SQLAlchemy ORM models
│   └── session.py
├── schemas/             # Pydantic request/response schemas
├── services/
│   ├── ai_provider.py
│   ├── document_service.py
│   ├── rag_service.py
│   ├── quiz_service.py
│   ├── flashcard_service.py
│   ├── study_plan_service.py
│   ├── gamification_service.py
│   └── export_service.py
└── main.py

database/
├── create_database.sql
└── schema.sql
```

## 3. Chuẩn bị database bằng pgAdmin 4

Bạn đã có schema trước đó. Nếu chưa có:

1. Mở database `postgres` -> Query Tool.
2. Chạy `database/create_database.sql`.
3. Refresh Databases.
4. Chọn `smart_study_assistant` -> Query Tool.
5. Chạy `database/schema.sql`.

Kiểm tra:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema='public'
  AND table_type='BASE TABLE';
```

Kết quả mong đợi: **45**.

## 4. Cài backend trên Windows

Mở PowerShell/CMD trong thư mục project:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Tạo `.env`:

```powershell
copy .env.example .env
```

Sửa dòng quan trọng:

```env
DATABASE_URL=postgresql+psycopg://postgres:MAT_KHAU_POSTGRES@localhost:5432/smart_study_assistant
JWT_SECRET_KEY=CHUOI_BI_MAT_DAI_VA_NGAU_NHIEN
```

Sinh secret key:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

> Nếu mật khẩu PostgreSQL chứa `@`, `:`, `/`, `#`, `%`... hãy URL-encode mật khẩu trước khi đưa vào `DATABASE_URL`.

## 5. Kiểm tra kết nối PostgreSQL

```powershell
python -m scripts.check_db
```

Bạn nên thấy:

```text
public tables: 45
pgvector enabled: True/False
```

`False` không chặn backend chạy. RAG sẽ dùng PostgreSQL Full-Text Search khi chưa có pgvector.

## 6. Chạy FastAPI

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Hoặc nhấp/chạy:

```text
run_dev.bat
```

Mở:

```text
http://127.0.0.1:8000/docs
```

Swagger UI cho phép thử toàn bộ API.

## 7. Luồng test đầu tiên

### 7.1 Đăng ký

`POST /api/v1/auth/register`

```json
{
  "email": "student@example.com",
  "password": "Password123!",
  "full_name": "Nguyen Van A"
}
```

Copy `access_token`, nhấn **Authorize** trong Swagger và nhập:

```text
Bearer ACCESS_TOKEN
```

### 7.2 Tạo môn học

`POST /api/v1/subjects`

```json
{
  "name": "Lập trình hướng đối tượng",
  "description": "Ôn thi OOP",
  "color_hex": "#3366FF"
}
```

### 7.3 Upload tài liệu

`POST /api/v1/documents/upload`

Form-data:

```text
file        = file PDF/DOCX/TXT
subject_id  = ID môn học
process_now = true
```

Backend thực hiện:

```text
upload -> extract -> clean -> chunk -> optional embedding -> READY
```

### 7.4 Tạo hội thoại RAG

`POST /api/v1/chat/conversations`

```json
{
  "subject_id": 1,
  "title": "Ôn OOP",
  "document_ids": [1]
}
```

Sau đó:

`POST /api/v1/chat/conversations/{id}/ask`

```json
{
  "question": "Encapsulation là gì?",
  "input_mode": "TEXT"
}
```

Nếu chưa cấu hình LLM, hệ thống vẫn retrieval tài liệu và trả các chunks liên quan. Nếu đã cấu hình AI provider, hệ thống sẽ tổng hợp câu trả lời chỉ dựa trên context và lưu citation.

## 8. Cấu hình LLM/Embedding

Backend không khóa vào một nhà cung cấp. Nó gọi API theo giao diện **OpenAI-compatible**.

Trong `.env`:

```env
AI_PROVIDER=openai_compatible
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=
AI_CHAT_MODEL=your-chat-model
AI_EMBEDDING_MODEL=your-embedding-model
```

Nếu chỉ muốn chạy database/API trước:

```env
AI_PROVIDER=disabled
```

Khi AI bị tắt:

- Auth, CRUD, Quiz thủ công, làm bài, chấm điểm, flashcard thủ công, spaced repetition, study plan, analytics, gamification, community, export: **vẫn hoạt động**.
- Chat: dùng retrieval-only fallback.
- AI Quiz/AI Flashcard: trả `503` cho tới khi cấu hình model.

## 9. pgvector

Backend không yêu cầu pgvector để boot.

Nếu database đã có native column `chunk_embeddings.embedding`, ingestion sẽ lưu embedding JSON và đồng thời cập nhật native vector.

Nếu `pgvector` + embedding model đã sẵn sàng, `rag_service.py` tự dùng cosine similarity. Nếu chưa có hoặc vector search lỗi, hệ thống tự fallback về PostgreSQL Full-Text Search để Q&A vẫn hoạt động.

## 10. API modules

| Module        | Prefix                  | Chức năng                                    |
| ------------- | ----------------------- | -------------------------------------------- |
| Auth          | `/api/v1/auth`          | register/login/refresh/logout/me             |
| Users         | `/api/v1/users`         | profile                                      |
| Subjects      | `/api/v1/subjects`      | CRUD môn học                                 |
| Documents     | `/api/v1/documents`     | upload/process/chunks                        |
| Chat          | `/api/v1/chat`          | conversation/RAG/citation                    |
| Quizzes       | `/api/v1/quizzes`       | manual/AI generation/publish/attempt/scoring |
| Flashcards    | `/api/v1/flashcards`    | deck/AI generation/due/review                |
| Study Plans   | `/api/v1/study-plans`   | roadmap/tasks                                |
| Analytics     | `/api/v1/analytics`     | dashboard/topic heatmap/daily                |
| Gamification  | `/api/v1/gamification`  | XP/level/streak/badges                       |
| Community     | `/api/v1/community`     | public post/like/save/fork                   |
| Exports       | `/api/v1/exports`       | PDF/DOCX                                     |
| Notifications | `/api/v1/notifications` | list/read                                    |

## 11. Quiz integrity

Pydantic kiểm tra trước khi ghi:

- đúng 4 options;
- A/B/C/D;
- đúng 1 đáp án đúng.

Database trigger trong `database/schema.sql` kiểm tra lại khi `DRAFT -> PUBLISHED`.

Do đó validation tồn tại ở **2 lớp**: API + PostgreSQL.

## 12. Spaced Repetition

`POST /api/v1/flashcards/{flashcard_id}/review`

Rating:

```text
0 = Again
1 = Hard
2 = Good
3 = Easy
```

Backend cập nhật:

- repetitions
- interval_days
- ease_factor
- lapse_count
- next_review_at
- flashcard_reviews history
- daily stats
- XP/badges

## 13. Analytics

`GET /api/v1/analytics/topics` sử dụng view:

```text
vw_user_topic_performance
```

Luồng truy vết:

```text
user_answers
 -> questions
 -> source_chunk_id
 -> document_chunks
 -> document_sections
 -> weak topic
```

Đây là nền tảng cho heatmap năng lực trên ReactJS.

## 14. Admin account

Sau khi schema đã có roles:

```powershell
python scripts/create_admin.py --email admin@example.com --password "AdminPassword123!" --name "Administrator"
```

## 15. Alembic

Schema SQL hiện tại là **baseline authority**, vì nó chứa trigger, partial index, view và logic pgvector mà ORM thuần không thể hiện đầy đủ.

Sau khi database đã được tạo:

```powershell
alembic stamp 0002_versioned_document_chunks
```

Từ thời điểm này, dùng Alembic cho thay đổi mới. Không chạy `Base.metadata.create_all()` để thay thế `database/schema.sql`.

Khi autogenerate migration, luôn review migration trước khi `upgrade`, đặc biệt với indexes/triggers/views.

## 16. Test

```powershell
pytest -q
```

Smoke test hiện tại kiểm tra FastAPI boot thành công.

## 17. Production checklist

Trước khi deploy thật:

- đổi `JWT_SECRET_KEY`;
- bật HTTPS;
- CORS chỉ cho domain frontend;
- dùng object storage thay local filesystem;
- background worker cho ingestion/embedding/export;
- rate-limit login, AI generation và uploads;
- giới hạn MIME/file signature chặt hơn;
- backup PostgreSQL;
- observability/logging;
- dùng secret manager cho API key;
- thêm antivirus scanning cho file upload nếu public SaaS.
