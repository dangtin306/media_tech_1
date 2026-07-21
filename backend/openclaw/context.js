const {
  BRAND,
  CATEGORY_CONTEXT,
  getOrCreateChatHistoryRecord,
  getOrCreateResponseState,
  callOpenClaw,
  buildConversationIdentity,
  extractTextFromResponse,
  parseJsonSafely,
  readConfig,
  readResponseState,
  readChatHistory,
  resolveRequestIdentity,
  writeResponseState,
  writeChatHistory
} = require('./shared');

function withCategory(payload) {
  return {
    category: CATEGORY_CONTEXT,
    ...payload
  };
}

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

function getModelFromRequest(req, url, rawBody) {
  if (req.method === 'GET') {
    const model = url.searchParams.get('model');
    return typeof model === 'string' && model.trim() ? model.trim() : '';
  }

  const payload = parseJsonSafely(rawBody);
  return typeof payload.model === 'string' && payload.model.trim()
    ? payload.model.trim()
    : '';
}

function getDefaultAgentId(config) {
  if (typeof config.session_key === 'string') {
    const match = config.session_key.trim().match(/^agent:([^:]+)(?::.*)?$/i);
    if (match && match[1]) {
      return match[1].trim();
    }
  }

  return 'media_tech';
}

function resolveGatewayModelName(rawModel, config) {
  const defaultAgentId = getDefaultAgentId(config);
  const fallbackModel = `openclaw/${defaultAgentId}`;

  if (typeof rawModel !== 'string' || !rawModel.trim()) {
    return fallbackModel;
  }

  const trimmed = rawModel.trim();

  if (trimmed === 'openclaw' || trimmed === 'openclaw/default') {
    return trimmed;
  }

  if (/^openclaw\/[^/]+$/i.test(trimmed)) {
    const suffix = trimmed.slice('openclaw/'.length).trim();
    if (!suffix || suffix.toLowerCase() === 'default') {
      return 'openclaw/default';
    }

    if (suffix.toLowerCase() === defaultAgentId.toLowerCase()) {
      return `openclaw/${defaultAgentId}`;
    }

    // Keep simple agent ids, but collapse legacy aliases with punctuation to
    // the configured agent id so the Gateway accepts the request.
    if (/^[a-z0-9_]+$/i.test(suffix)) {
      return trimmed;
    }

    return fallbackModel;
  }

  return fallbackModel;
}

async function askOpenClaw(userId, message, chatToken = '', demo = false, modelName = '', payload = {}) {
  const config = readConfig();
  const responseState = readResponseState();
  const chatHistory = readChatHistory();
  const userState = getOrCreateResponseState(responseState, userId);
  const userHistory = getOrCreateChatHistoryRecord(chatHistory, userId);
  const identity = buildConversationIdentity(config, userId, chatToken, demo);
  const resolvedModel = resolveGatewayModelName(modelName, config);
  const result = await callOpenClaw({
    prompt: message,
    userKey: identity.user,
    sessionKey: identity.session_key,
    modelName: resolvedModel,
    payload
  });

  const answer = extractTextFromResponse(result);
  const responseId = typeof result.id === 'string'
    ? result.id
    : typeof result.response_id === 'string'
      ? result.response_id
      : null;
  const now = new Date().toISOString();

  if (responseId) {
    userState.latest_response_id = responseId;
    userState.previous_response_ids = [...userState.previous_response_ids, responseId];
  }
  writeResponseState(responseState);

  userHistory.history = [
    ...userHistory.history,
    {
      role: 'user',
      content: message,
      created_at: now
    },
    {
      role: 'assistant',
      content: answer || '',
      response_id: responseId,
      created_at: now
    }
  ];
  writeChatHistory(chatHistory);

  return {
    answer,
    response_id: responseId,
    model: resolvedModel,
    user_state: userState,
    chat_history: userHistory
  };
}

function createContextRoute({ sendJson, sendError }) {
  const brandedSendJson = createBrandedSendJson(sendJson);
  const brandedSendError = createBrandedSendError(sendJson);

  return async function contextRoute(req, res, url, rawBody = '') {
    if (url.pathname !== '/chat_bot/api') {
      return false;
    }

    if (req.method === 'GET') {
      const rawResult = resolveRequestIdentity(req, url, '');
      const modelName = getModelFromRequest(req, url, '');
      if (rawResult.error) {
        return brandedSendError(res, 400, rawResult.error);
      }

      const text = url.searchParams.get('text');
      if (text && text.trim()) {
        try {
          const result = await askOpenClaw(
            rawResult.userId,
            text.trim(),
            rawResult.chatToken || '',
            Boolean(rawResult.demo),
            modelName
          );
          return brandedSendJson(res, 200, withCategory({
            ok: true,
            user_id: rawResult.userId,
            chat_token: rawResult.chatToken || null,
            model: result.model,
            session_key: rawResult.demo
              ? readConfig().session_demo || `${readConfig().session_key || 'agent:media_tech'}:test_1`
              : `${readConfig().session_key || 'agent:media_tech'}:user_${rawResult.userId}`,
            answer: result.answer,
            previous_response_id_used: null,
            latest_response_id: result.response_id
          }));
        } catch (error) {
          const statusCode = error && error.statusCode ? error.statusCode : 400;
          const details = error && error.payload ? error.payload : undefined;
          const message = error && error.message ? error.message : 'OpenClaw request failed';
          return brandedSendError(
            res,
            statusCode,
            details ? `${message}: ${JSON.stringify(details)}` : message
          );
        }
      }

      const users = readResponseState();
      const userState = users.find((item) => item.user_id === rawResult.userId) || {
        user_id: rawResult.userId,
        latest_response_id: null,
        previous_response_ids: []
      };
      const config = readConfig();
      const sampleMessage = typeof config.sample_message === 'string' && config.sample_message.trim()
        ? config.sample_message.trim()
        : 'xin chao';
      const sessionKey = rawResult.demo
        ? (config.session_demo || `${config.session_key || 'agent:media_tech'}:test_1`)
        : `${config.session_key || 'agent:media_tech'}:user_${rawResult.userId}`;

      return brandedSendJson(res, 200, withCategory({
        ok: true,
        endpoint: '/chat_bot/api',
        user_id: rawResult.userId,
        chat_token: rawResult.chatToken || null,
        session_key: sessionKey,
        sampleRequest: {
          user_id: rawResult.userId,
          message: sampleMessage
        },
        user_state: userState
      }));
    }

    if (req.method === 'POST') {
      try {
        const rawResult = resolveRequestIdentity(req, url, rawBody);
        const modelName = getModelFromRequest(req, url, rawBody);
        if (rawResult.error) {
          return brandedSendError(res, 400, rawResult.error);
        }

        const payload = parseJsonSafely(rawBody);
        if (!payload.message || typeof payload.message !== 'string') {
          return brandedSendError(res, 400, 'Body phải có field "message" dạng chuỗi');
        }

        const result = await askOpenClaw(
          rawResult.userId,
          payload.message,
          rawResult.chatToken || '',
          Boolean(rawResult.demo),
          modelName,
          payload
        );
        const config = readConfig();
        const sessionKey = rawResult.demo
          ? (config.session_demo || `${config.session_key || 'agent:media_tech'}:test_1`)
          : `${config.session_key || 'agent:media_tech'}:user_${rawResult.userId}`;
        return brandedSendJson(res, 200, withCategory({
          ok: true,
          user_id: rawResult.userId,
          chat_token: rawResult.chatToken || null,
          model: result.model,
          session_key: sessionKey,
          answer: result.answer,
          previous_response_id_used: null,
          latest_response_id: result.response_id
        }));
      } catch (error) {
        const details = error && error.payload ? error.payload : undefined;
        const message = error && error.message ? error.message : 'OpenClaw request failed';
        return brandedSendError(
          res,
          400,
          details ? `${message}: ${JSON.stringify(details)}` : message
        );
      }
    }

    return false;
  };
}

module.exports = {
  createContextRoute
};
