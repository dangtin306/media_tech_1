const {
  BRAND,
  CATEGORY_USER_ID,
  isValidChatToken,
  parseJsonSafely,
  parseChatToken,
  readTokenState,
  getNextUserId,
  writeTokenState
} = require('./shared');

function createBrandedSendJson(sendJson) {
  return (res, statusCode, data) => sendJson(res, statusCode, { brand: BRAND, ...data });
}

function createBrandedSendError(sendJson) {
  return (res, statusCode, message) => sendJson(res, statusCode, {
    brand: BRAND,
    ok: false,
    error: message
  });
}

function upsertChatToken(chatToken) {
  const state = readTokenState();
  const existing = state.find((item) => item.chat_token === chatToken);

  if (existing) {
    return {
      created: false,
      record: existing
    };
  }

  const record = {
    chat_token: chatToken,
    user_id: getNextUserId(state)
  };
  const nextState = [...state, record];
  writeTokenState(nextState);

  return {
    created: true,
    record
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
  const brandedSendJson = createBrandedSendJson(sendJson);
  const brandedSendError = createBrandedSendError(sendJson);

  return async function userIdRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    const chatToken = extractChatToken(req, url, rawBody);
    if (!chatToken) {
      return brandedSendError(res, 400, 'chat_token phải là chuỗi');
    }

    if (!isValidChatToken(chatToken)) {
      return brandedSendError(res, 400, 'chat_token phải dài hơn 15 ký tự');
    }

    const result = upsertChatToken(chatToken);
    return brandedSendJson(res, 200, {
      ok: true,
      category: CATEGORY_USER_ID,
      chat_token: result.record.chat_token,
      user_id: result.record.user_id,
      created: result.created
    });
  };
}

module.exports = {
  createUserIdRoute
};
