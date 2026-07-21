const fs = require('fs');
const path = require('path');
const AI_CONFIG = require('./config.json');

const USERS_DIR = path.join(__dirname, 'users');
const STATE_FILE = path.join(USERS_DIR, 'users_response_id.json');
const CHAT_FILE = path.join(USERS_DIR, 'users_chat.json');
const TOKEN_FILE = path.join(USERS_DIR, 'users_token.json');
const SAMPLE_MESSAGE = AI_CONFIG.sample_message;
const CATEGORY = 'context';

function ensureFile(filePath, fallbackValue) {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(fallbackValue, null, 2), 'utf8');
  }
}

function ensureStateFile() {
  ensureFile(STATE_FILE, []);
}

function ensureChatFile() {
  ensureFile(CHAT_FILE, []);
}

function ensureTokenFile() {
  ensureFile(TOKEN_FILE, []);
}

function normalizeChatState(parsed) {
  if (Array.isArray(parsed)) {
    return parsed
      .filter((item) => item && Number.isInteger(item.user_id))
      .map((item) => ({
        user_id: item.user_id,
        latest_response_id: typeof item.latest_response_id === 'string' ? item.latest_response_id : null,
        previous_response_ids: Array.isArray(item.previous_response_ids)
          ? item.previous_response_ids.filter((id) => typeof id === 'string')
          : []
      }));
  }

  if (parsed && Array.isArray(parsed.users)) {
    return normalizeChatState(parsed.users);
  }

  if (parsed && typeof parsed.users === 'object' && parsed.users) {
    return Object.values(parsed.users).flatMap((item) => normalizeChatState([item]));
  }

  return [];
}

function readChatState() {
  ensureStateFile();

  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const users = normalizeChatState(parsed);
    if (!Array.isArray(parsed)) {
      writeChatState(users);
    }
    return users;
  } catch {
    const fallback = [];
    fs.writeFileSync(STATE_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeChatState(users) {
  ensureStateFile();
  fs.writeFileSync(STATE_FILE, JSON.stringify(users, null, 2), 'utf8');
}

function normalizeChatHistory(parsed) {
  if (!Array.isArray(parsed)) {
    return [];
  }

  return parsed
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      user_id: Number.isInteger(item.user_id) ? item.user_id : null,
      history: Array.isArray(item.history)
        ? item.history
            .filter((entry) => entry && typeof entry === 'object')
            .map((entry) => ({
              role: entry.role === 'assistant' ? 'assistant' : 'user',
              content: typeof entry.content === 'string' ? entry.content : '',
              response_id: typeof entry.response_id === 'string' ? entry.response_id : null,
              created_at: typeof entry.created_at === 'string' ? entry.created_at : null
            }))
            .filter((entry) => entry.content)
        : []
    }))
    .filter((item) => Number.isInteger(item.user_id));
}

function readChatHistory() {
  ensureChatFile();

  try {
    const raw = fs.readFileSync(CHAT_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const history = normalizeChatHistory(parsed);
    if (!Array.isArray(parsed)) {
      writeChatHistory(history);
    }
    return history;
  } catch {
    const fallback = [];
    fs.writeFileSync(CHAT_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeChatHistory(history) {
  ensureChatFile();
  fs.writeFileSync(CHAT_FILE, JSON.stringify(history, null, 2), 'utf8');
}

function normalizeTokenState(parsed) {
  if (!Array.isArray(parsed)) {
    return [];
  }

  return parsed
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      chat_token: typeof item.chat_token === 'string' ? item.chat_token : '',
      user_id: Number.isInteger(item.user_id) ? item.user_id : null
    }))
    .filter((item) => item.chat_token && Number.isInteger(item.user_id));
}

function readTokenState() {
  ensureTokenFile();

  try {
    const raw = fs.readFileSync(TOKEN_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const tokens = normalizeTokenState(parsed);
    if (!Array.isArray(parsed)) {
      writeTokenState(tokens);
    }
    return tokens;
  } catch {
    const fallback = [];
    fs.writeFileSync(TOKEN_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeTokenState(state) {
  ensureTokenFile();
  fs.writeFileSync(TOKEN_FILE, JSON.stringify(state, null, 2), 'utf8');
}

function parseUserId(value) {
  if (typeof value !== 'string') {
    return null;
  }

  const trimmed = value.trim();
  if (!/^-?\d+$/.test(trimmed)) {
    return null;
  }

  const userId = Number(trimmed);
  return Number.isSafeInteger(userId) ? userId : null;
}

function parseChatToken(value) {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

function extractTextFromResponse(response) {
  if (typeof response.output_text === 'string' && response.output_text.trim()) {
    return response.output_text.trim();
  }

  const output = Array.isArray(response.output) ? response.output : [];
  for (const item of output) {
    if (item && item.type === 'message' && Array.isArray(item.content)) {
      for (const part of item.content) {
        if (part && part.type === 'output_text' && typeof part.text === 'string' && part.text.trim()) {
          return part.text.trim();
        }
      }
    }
  }

  return '';
}

function getOrCreateUserState(users, userId) {
  const existing = users.find((item) => item.user_id === userId);
  if (existing) {
    return existing;
  }

  const created = {
    user_id: userId,
    latest_response_id: null,
    previous_response_ids: []
  };
  users.push(created);
  return created;
}

function resolveRequestUserId(req, url, rawBody) {
  const source = req.method === 'GET'
    ? {
        userId: parseUserId(url.searchParams.get('user_id')),
        chatToken: parseChatToken(url.searchParams.get('chat_token'))
      }
    : (() => {
        try {
          const payload = rawBody ? JSON.parse(rawBody) : {};
          return {
            userId: parseUserId(String(payload.user_id ?? '')),
            chatToken: parseChatToken(payload.chat_token)
          };
        } catch {
          return {
            userId: null,
            chatToken: ''
          };
        }
      })();

  const hasUserId = source.userId !== null;
  const hasChatToken = Boolean(source.chatToken);

  if (hasUserId && hasChatToken) {
    return {
      error: 'Chỉ được truyền một trong hai biến: user_id hoặc chat_token'
    };
  }

  if (!hasUserId && !hasChatToken) {
    return {
      error: 'Phải có user_id hoặc chat_token'
    };
  }

  if (hasUserId) {
    return {
      userId: source.userId,
      mode: 'user_id'
    };
  }

  const tokens = readTokenState();
  const mapped = tokens.find((item) => item.chat_token === source.chatToken);
  if (!mapped) {
    return {
      error: 'chat_token không tồn tại trong users_token.json'
    };
  }

  return {
    userId: mapped.user_id,
    mode: 'chat_token',
    chatToken: source.chatToken
  };
}

async function askOpenAI(openai, userId, message) {
  const users = readChatState();
  const userState = getOrCreateUserState(users, userId);
  const history = readChatHistory();
  const userHistory = history.find((item) => item.user_id === userId);
  const nextHistory = userHistory || { user_id: userId, history: [] };

  const request = {
    model: AI_CONFIG.model,
    instructions: AI_CONFIG.system_prompt,
    input: message,
    tools: [AI_CONFIG.tools.file_search],
    store: AI_CONFIG.store,
    temperature: AI_CONFIG.temperature,
    top_p: AI_CONFIG.top_p,
    text: AI_CONFIG.text
  };

  if (userState.latest_response_id) {
    request.previous_response_id = userState.latest_response_id;
  }

  const response = await openai.responses.create(request);
  const answer = extractTextFromResponse(response) || AI_CONFIG.fallback_answer;
  const now = new Date().toISOString();

  userState.latest_response_id = response.id;
  userState.previous_response_ids = [...userState.previous_response_ids, response.id];
  writeChatState(users);

  nextHistory.history = [
    ...nextHistory.history,
    {
      role: 'user',
      content: message,
      created_at: now
    },
    {
      role: 'assistant',
      content: answer,
      response_id: response.id,
      created_at: now
    }
  ];

  if (!userHistory) {
    history.push(nextHistory);
  }
  writeChatHistory(history);

  return {
    answer,
    previous_response_id_used: request.previous_response_id || null,
    latest_response_id: response.id,
    user_state: userState,
    chat_history: nextHistory
  };
}

function withCategory(payload) {
  return {
    category: CATEGORY,
    ...payload
  };
}

function createContextRoute({ openai, sendJson, sendError, readBody }) {
  return async function contextRoute(req, res, url) {
    if (req.method === 'GET' && url.pathname === '/chat_bot/api') {
      if (!openai) {
        return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
      }

      const rawResult = resolveRequestUserId(req, url, '');
      if (rawResult.error) {
        return sendError(res, 400, rawResult.error);
      }

      const userId = rawResult.userId;
      const text = url.searchParams.get('text');
      if (text && text.trim()) {
        const result = await askOpenAI(openai, userId, text.trim());
        return sendJson(res, 200, withCategory({
          ok: true,
          user_id: userId,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.latest_response_id
        }));
      }

      const users = readChatState();
      const userState = users.find((item) => item.user_id === userId) || {
        user_id: userId,
        latest_response_id: null,
        previous_response_ids: []
      };

      return sendJson(res, 200, withCategory({
        ok: true,
        endpoint: '/chat_bot/api',
        user_id: userId,
        sampleRequest: {
          user_id: userId,
          message: SAMPLE_MESSAGE
        },
        user_state: userState
      }));
    }

    if (req.method === 'POST' && url.pathname === '/chat_bot/api') {
      try {
        if (!openai) {
          return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
        }

        const rawBody = await readBody(req);
        const rawResult = resolveRequestUserId(req, url, rawBody);
        if (rawResult.error) {
          return sendError(res, 400, rawResult.error);
        }

        const payload = rawBody ? JSON.parse(rawBody) : {};
        if (!payload.message || typeof payload.message !== 'string') {
          return sendError(res, 400, 'Body phải có field "message" dạng chuỗi');
        }

        const result = await askOpenAI(openai, rawResult.userId, payload.message);
        return sendJson(res, 200, withCategory({
          ok: true,
          user_id: rawResult.userId,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.latest_response_id
        }));
      } catch (error) {
        return sendError(res, 400, error.message);
      }
    }

    return false;
  };
}

module.exports = {
  createContextRoute
};
