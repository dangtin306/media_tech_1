const fs = require('fs');
const path = require('path');

const USERS_DIR = path.join(__dirname, 'users');
const CHAT_HISTORY_FILE = path.join(USERS_DIR, 'users_chat.json');
const TOKEN_FILE = path.join(USERS_DIR, 'users_token.json');

function ensureFile(filePath, fallbackValue) {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(fallbackValue, null, 2), 'utf8');
  }
}

function ensureChatHistoryFile() {
  ensureFile(CHAT_HISTORY_FILE, []);
}

function ensureTokenFile() {
  ensureFile(TOKEN_FILE, []);
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

function readChatHistoryState() {
  ensureChatHistoryFile();

  try {
    const raw = fs.readFileSync(CHAT_HISTORY_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const history = normalizeChatHistory(parsed);
    if (!Array.isArray(parsed)) {
      fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(history, null, 2), 'utf8');
    }
    return history;
  } catch {
    const fallback = [];
    fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
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
      fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens, null, 2), 'utf8');
    }
    return tokens;
  } catch {
    const fallback = [];
    fs.writeFileSync(TOKEN_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function resolveRequestUserId(req, url, rawBody = '') {
  const source = req.method === 'GET'
    ? {
        userId: parseUserId(url.searchParams.get('user_id')),
        chatToken: parseChatToken(url.searchParams.get('chat_token'))
      }
    : (() => {
        const payload = rawBody ? JSON.parse(rawBody) : {};
        return {
          userId: parseUserId(String(payload.user_id ?? '')),
          chatToken: parseChatToken(payload.chat_token)
        };
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
      userId: source.userId
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
    userId: mapped.user_id
  };
}

function createHistoryRoute({ sendJson, sendError }) {
  return async function historyRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    const rawResult = resolveRequestUserId(req, url, rawBody);
    if (rawResult.error) {
      return sendError(res, 400, rawResult.error);
    }

    const historyState = readChatHistoryState();
    const userHistory = historyState.find((item) => item.user_id === rawResult.userId);

    return sendJson(res, 200, {
      ok: true,
      category: 'history',
      user_id: rawResult.userId,
      history: userHistory ? userHistory.history : []
    });
  };
}

module.exports = {
  createHistoryRoute
};
