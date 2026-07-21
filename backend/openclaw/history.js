const {
  BRAND,
  CATEGORY_HISTORY,
  readChatHistory,
  resolveRequestUserId
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

function createHistoryRoute({ sendJson, sendError }) {
  const brandedSendJson = createBrandedSendJson(sendJson);
  const brandedSendError = createBrandedSendError(sendJson);

  return async function historyRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    const rawResult = resolveRequestUserId(req, url, rawBody);
    if (rawResult.error) {
      return brandedSendError(res, 400, rawResult.error);
    }

    const historyState = readChatHistory();
    const userHistory = historyState.find((item) => item.user_id === rawResult.userId);

    return brandedSendJson(res, 200, {
      ok: true,
      category: CATEGORY_HISTORY,
      user_id: rawResult.userId,
      chat_token: rawResult.chatToken || null,
      history: userHistory ? userHistory.history : []
    });
  };
}

module.exports = {
  createHistoryRoute
};
