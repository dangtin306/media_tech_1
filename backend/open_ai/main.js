const { createContextRoute } = require('./context_gpt_api');
const { createHistoryRoute } = require('./history');
const { createUserIdRoute } = require('./user_id');

const CHAT_BRAND = 'open_ai_api';

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

function getCategoryFromRequest(req, url, rawBody) {
  if (req.method === 'GET') {
    return url.searchParams.get('category') || 'context';
  }

  const payload = parseJsonSafely(rawBody);
  return typeof payload.category === 'string' && payload.category.trim()
    ? payload.category.trim()
    : 'context';
}

function withChatBrand(payload) {
  return {
    brand: CHAT_BRAND,
    ...payload
  };
}

function createBrandedSendJson(sendJson) {
  return (res, statusCode, data) => sendJson(res, statusCode, withChatBrand(data));
}

function createBrandedSendError(sendJson) {
  return (res, statusCode, message) => sendJson(res, statusCode, withChatBrand({
    ok: false,
    error: message
  }));
}

function createMainRoute({ openai, sendJson, sendError, readBody }) {
  const brandedSendJson = createBrandedSendJson(sendJson);
  const brandedSendError = createBrandedSendError(sendJson);
  const historyRoute = createHistoryRoute({
    sendJson: brandedSendJson,
    sendError: brandedSendError
  });
  const userIdRoute = createUserIdRoute({
    sendJson: brandedSendJson,
    sendError: brandedSendError
  });

  return async function mainRoute(req, res, url) {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method === 'POST') {
      const rawBody = await readBody(req);
      const category = getCategoryFromRequest(req, url, rawBody);

      if (category === 'history') {
        return historyRoute(req, res, url, rawBody);
      }

      if (category === 'user_id') {
        return userIdRoute(req, res, url, rawBody);
      }

      const contextRoute = createContextRoute({
        openai,
        sendJson: brandedSendJson,
        sendError: brandedSendError,
        readBody: async () => rawBody
      });
      return contextRoute(req, res, url);
    }

    const category = getCategoryFromRequest(req, url, '');
    if (category === 'history') {
      return historyRoute(req, res, url, '');
    }

    if (category === 'user_id') {
      return userIdRoute(req, res, url, '');
    }

    const contextRoute = createContextRoute({
      openai,
      sendJson: brandedSendJson,
      sendError: brandedSendError,
      readBody
    });
    return contextRoute(req, res, url);
  };
}

module.exports = {
  createMainRoute,
  createTestAi3Route: createMainRoute
};
