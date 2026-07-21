# Media Tech Backend

## Run

```bash
npm install
npm run dev
```

`npm run dev` uses `nodemon` for auto reload during development.

## Env

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`.

## API

Base URL:

```text
http://vip.tecom.pro:8006
```

### Health

```bash
curl http://vip.tecom.pro:8006/health
```

### Main Route

Route:

```text
/chat_bot/api
```

Use `category` to choose the behavior:

- `category=context` for chat with OpenAI
- `category=history` for reading stored chat history
- `category=user_id` for mapping `chat_token` to `user_id`

If `category` is omitted, the route defaults to `context`.

Accepted input rules:

- Send exactly one of `user_id` or `chat_token`
- Do not send both at the same time
- If `chat_token` is used, it must exist in `open_ai/users/users_token.json`
- If `chat_token` is used, it is mapped to its `user_id`, then the flow continues like `user_id`

### Context

#### GET with `user_id`

```bash
curl "http://vip.tecom.pro:8006/chat_bot/api?user_id=1&text=iPhone%205s%20c%C3%B3%20Touch%20ID%20kh%C3%B4ng%3F"
```

#### GET with `chat_token`

```bash
curl "http://vip.tecom.pro:8006/chat_bot/api?chat_token=demo_token_001&text=iPhone%205s%20c%C3%B3%20Touch%20ID%20kh%C3%B4ng%3F"
```

#### POST with `user_id`

```bash
curl -X POST http://vip.tecom.pro:8006/chat_bot/api -H "Content-Type: application/json" -d '{"user_id":1,"message":"iPhone 5s có Touch ID không?"}'
```

#### POST with `chat_token`

```bash
curl -X POST http://vip.tecom.pro:8006/chat_bot/api -H "Content-Type: application/json" -d '{"chat_token":"demo_token_001","message":"iPhone 5s có Touch ID không?"}'
```

#### Response example

```json
{
  "ok": true,
  "category": "context",
  "user_id": 1,
  "answer": "..."
}
```

### History

#### GET with `user_id`

```bash
curl "http://vip.tecom.pro:8006/chat_bot/api?category=history&user_id=1"
```

#### GET with `chat_token`

```bash
curl "http://vip.tecom.pro:8006/chat_bot/api?category=history&chat_token=demo_token_001"
```

#### Response example

```json
{
  "ok": true,
  "category": "history",
  "user_id": 1,
  "history": []
}
```

### User ID

Use `category=user_id` to register or look up a `chat_token`.

Rules:

- `chat_token` must be longer than 15 characters
- If the token already exists, it returns the existing `user_id`
- If the token is new, it is appended to `open_ai/users/users_token.json` with `user_id + 1`

#### POST

```bash
curl -X POST http://vip.tecom.pro:8006/chat_bot/api -H "Content-Type: application/json" -d '{"category":"user_id","chat_token":"demo_token_001"}'
```

#### Response example

```json
{
  "ok": true,
  "category": "user_id",
  "chat_token": "demo_token_001",
  "user_id": 2,
  "created": true
}
```

## State Files

- `open_ai/users/users_response_id.json` stores response-id chain state for `context`
- `open_ai/users/users_chat.json` stores chat history by `user_id`
- `open_ai/users/users_token.json` stores `chat_token` to `user_id` mapping for `user_id`
