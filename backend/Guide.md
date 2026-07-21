# Media Tech Backend Guide

## Run

```bash
npm install
npm run dev
```

`npm run dev` dùng `nodemon` để tự reload khi sửa code.

## Env

Tạo file `.env` từ `.env.example`.

Biến đang dùng:

- `OPENAI_API_KEY`
- `PORT` mặc định là `8006`
- `QDRANT_URL` mặc định là `http://localhost:6333`
- `QDRANT_COLLECTION` mặc định lấy từ `llms\media_tech\ai\qdrant\data_1\qdrant_collection_config.json`
- `QDRANT_PYTHON_BIN` mặc định là `python`

## Base URL

Local:

```text
http://localhost:8006
```

Public theo README cũ:

```text
http://vip.tecom.pro:8006
```

## API

### GET `/health`

Kiểm tra backend còn sống.

```bash
curl http://localhost:8006/health
```

### GET `/qdrant`

Vai trò:
- nếu không có `query`: trả info collection từ Qdrant
- nếu có `query`: search text trên collection Qdrant bằng logic hash 384 của bộ `llms\media_tech\ai\qdrant\data_1`

Ví dụ lấy info collection:

```bash
curl "http://localhost:8006/qdrant"
```

Ví dụ search text:

```bash
curl "http://localhost:8006/qdrant?query=spa%20ha%20noi&limit=2"
```

Query params hỗ trợ:

- `query` hoặc `text` hoặc `message`
- `limit`
- `collection`
- `with_payload`
- `path`

Ví dụ gọi path nội bộ của Qdrant qua backend:

```bash
curl "http://localhost:8006/qdrant?path=/collections/dulich_demo"
```

### POST `/qdrant`

Vai trò:
- search text bằng body JSON
- search vector nếu truyền `vector`
- proxy request sang path nội bộ của Qdrant nếu truyền `path`

Ví dụ search text:

```bash
curl -X POST http://localhost:8006/qdrant -H "Content-Type: application/json" -d "{\"query\":\"quán trà sữa ở hải phòng\",\"limit\":5}"
```

Ví dụ search vector:

```bash
curl -X POST http://localhost:8006/qdrant -H "Content-Type: application/json" -d "{\"vector\":[0.1,0.2,0.3],\"limit\":3}"
```

Ví dụ proxy sang endpoint search của Qdrant:

```bash
curl -X POST http://localhost:8006/qdrant -H "Content-Type: application/json" -d "{\"path\":\"/collections/dulich_demo/points/search\",\"body\":{\"vector\":[0.1,0.2,0.3],\"limit\":3,\"with_payload\":true}}"
```

Response route này luôn có dạng khung:

```json
{
  "ok": true,
  "route": "/qdrant",
  "result": {}
}
```

### GET hoặc POST `/chat_bot/api`

Route chính cho flow OpenAI.

`category` hỗ trợ:

- `context`
- `history`
- `user_id`

Nếu không truyền `category` thì mặc định là `context`.

Quy tắc input:

- chỉ truyền một trong hai: `user_id` hoặc `chat_token`
- không truyền đồng thời cả hai
- nếu dùng `chat_token` thì token phải tồn tại trong `open_ai/users/users_token.json`

### Context

GET với `user_id`:

```bash
curl "http://localhost:8006/chat_bot/api?user_id=1&text=iPhone%205s%20có%20Touch%20ID%20không?"
```

GET với `chat_token`:

```bash
curl "http://localhost:8006/chat_bot/api?chat_token=demo_token_001&text=iPhone%205s%20có%20Touch%20ID%20không?"
```

POST với `user_id`:

```bash
curl -X POST http://localhost:8006/chat_bot/api -H "Content-Type: application/json" -d "{\"user_id\":1,\"message\":\"iPhone 5s có Touch ID không?\"}"
```

POST với `chat_token`:

```bash
curl -X POST http://localhost:8006/chat_bot/api -H "Content-Type: application/json" -d "{\"chat_token\":\"demo_token_001\",\"message\":\"iPhone 5s có Touch ID không?\"}"
```

### History

GET:

```bash
curl "http://localhost:8006/chat_bot/api?category=history&user_id=1"
```

hoặc:

```bash
curl "http://localhost:8006/chat_bot/api?category=history&chat_token=demo_token_001"
```

### User ID

Dùng để tạo hoặc tra cứu `chat_token`.

Quy tắc:

- `chat_token` phải dài hơn `15` ký tự
- token cũ thì trả lại `user_id` cũ
- token mới thì sinh `user_id` mới và append vào `open_ai/users/users_token.json`

Ví dụ:

```bash
curl -X POST http://localhost:8006/chat_bot/api -H "Content-Type: application/json" -d "{\"category\":\"user_id\",\"chat_token\":\"demo_token_001_123456\"}"
```

## Route Test

Các route test đang tồn tại:

- `GET|POST /test_ai_1`
- `GET|POST /test_ai_2`
- `GET|POST /test_ai_3`
- `POST /chat`

## State Files

- `open_ai/users/users_response_id.json`: lưu response chain theo `user_id`
- `open_ai/users/users_chat.json`: lưu history chat
- `open_ai/users/users_token.json`: mapping `chat_token -> user_id`
- `open_ai/users/test_ai_2.json`: state test cho `/test_ai_2`
- `open_ai/users/test_ai_3.json`: state test cho `/test_ai_3`
