# Backend URI Guide

## Backend Agent - Port 8006

### Health check

```text
GET http://localhost:8006/openclaw/agent/health
```

### Agent run

URI input chính của agent:

```text
POST http://localhost:8006/openclaw/agent/run
```

Request này nhận `system_context`, `user_message`, `history`, `use_lora`,
`use_rag` và các tùy chọn chạy agent.

### Agent level

```text
POST http://localhost:8006/openclaw/agent/level
```

### Chat completions

```text
POST http://localhost:8006/chat/completions
```

### Chat search

```text
POST http://localhost:8006/chat/search
```

Dùng để gửi yêu cầu tìm kiếm hội thoại/dữ liệu tìm kiếm qua backend.

## Qwen Worker - Port 8005

```text
GET  http://localhost:8005/health
POST http://localhost:8005/openclaw/agent/run
POST http://localhost:8005/openclaw/agent/level
POST http://localhost:8005/chat/completions
```

Port `8005` là worker Qwen phía sau. Client/agent nên gọi port `8006`, không
gọi trực tiếp port `8005`.

## Cloud GPU WebSocket

Khi `qwen_win` là `false`, backend giữ kết nối tới cloud GPU bằng:

```text
wss://oc.hust.media/chatbot/gpu
```

Request từ `/openclaw/agent/run` được chuyển qua WebSocket tới GPU worker.
Trường `use_rag: true` được truyền theo request để worker xử lý RAG.

## Local OpenAI-Compatible Input

```text
POST http://localhost:8796/v1/chat/completions
```

Đây là lớp tương thích OpenAI của backend, sau đó request được định tuyến tới
agent GPU hoặc worker tương ứng.
