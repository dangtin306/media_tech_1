const { CATEGORY_CONTEXT, CATEGORY_HISTORY, CATEGORY_USER_ID } = require('./shared');
const { createContextRoute } = require('./context');
const { createHistoryRoute } = require('./history');
const { createUserIdRoute } = require('./user_id');

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
    return url.searchParams.get('category') || CATEGORY_CONTEXT;
  }

  const payload = parseJsonSafely(rawBody);
  return typeof payload.category === 'string' && payload.category.trim()
    ? payload.category.trim()
    : CATEGORY_CONTEXT;
}

function createOpenClawRoute({ sendJson, sendError }) {
  const contextRoute = createContextRoute({ sendJson, sendError });
  const historyRoute = createHistoryRoute({ sendJson, sendError });
  const userIdRoute = createUserIdRoute({ sendJson, sendError });

  return async function openClawRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    const category = getCategoryFromRequest(req, url, rawBody);

    if (category === CATEGORY_HISTORY) {
      return historyRoute(req, res, url, rawBody);
    }

    if (category === CATEGORY_USER_ID) {
      return userIdRoute(req, res, url, rawBody);
    }

    return contextRoute(req, res, url, rawBody);
  };
}

module.exports = {
  createOpenClawRoute
};
