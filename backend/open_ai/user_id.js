const fs = require('fs');
const path = require('path');

const CATEGORY = 'user_id';
const USERS_DIR = path.join(__dirname, 'users');
const STATE_FILE = path.join(USERS_DIR, 'users_token.json');

function ensureStateFile() {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(STATE_FILE)) {
    fs.writeFileSync(STATE_FILE, JSON.stringify([], null, 2), 'utf8');
  }
}

function readState() {
  ensureStateFile();

  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];

    if (!Array.isArray(parsed)) {
      writeState([]);
      return [];
    }

    return parsed
      .filter((item) => item && typeof item === 'object')
      .map((item) => ({
        chat_token: typeof item.chat_token === 'string' ? item.chat_token : '',
        user_id: Number.isInteger(item.user_id) ? item.user_id : null
      }))
      .filter((item) => item.chat_token && Number.isInteger(item.user_id));
  } catch {
    const fallback = [];
    writeState(fallback);
    return fallback;
  }
}

function writeState(state) {
  ensureStateFile();
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}

function parseJsonSafely(rawBody) {
  if (typeof rawBody !== 'string' || !rawBody.trim()) {
    return {};
  }

  try {
    return JSON.parse(rawBody);
  } catch {
    return {};
  }
}

function parseChatToken(value) {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

function isValidChatToken(chatToken) {
  return typeof chatToken === 'string' && chatToken.length > 15;
}

function getNextUserId(state) {
  const maxUserId = state.reduce((max, item) => (
    Number.isInteger(item.user_id) && item.user_id > max ? item.user_id : max
  ), 0);
  return maxUserId + 1;
}

function upsertChatToken(chatToken) {
  const state = readState();
  const existing = state.find((item) => item.chat_token === chatToken);

  if (existing) {
    return {
      created: false,
      record: existing,
      state
    };
  }

  const record = {
    chat_token: chatToken,
    user_id: getNextUserId(state)
  };
  const nextState = [...state, record];
  writeState(nextState);

  return {
    created: true,
    record,
    state: nextState
  };
}

function extractChatToken(req, url, rawBody) {
  if (req.method === 'GET') {
    return parseChatToken(url.searchParams.get('chat_token'));
  }

  const payload = parseJsonSafely(rawBody);
  return parseChatToken(payload.chat_token);
}

function createUserIdRoute({ sendJson, sendError }) {
  return async function userIdRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    const chatToken = extractChatToken(req, url, rawBody);
    if (!chatToken) {
      return sendError(res, 400, 'chat_token phải là chuỗi');
    }

    if (!isValidChatToken(chatToken)) {
      return sendError(res, 400, 'chat_token phải dài hơn 15 ký tự');
    }

    const result = upsertChatToken(chatToken);
    return sendJson(res, 200, {
      ok: true,
      category: CATEGORY,
      chat_token: result.record.chat_token,
      user_id: result.record.user_id,
      created: result.created
    });
  };
}

module.exports = {
  createUserIdRoute
};
