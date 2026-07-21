const fs = require('fs');
const path = require('path');
const CONFIG_PATH = path.join(__dirname, 'config.json');
const UBUNTU_CONFIG_PATH = path.join(__dirname, '..', '..', 'server', 'ubuntu', 'config.json');
const USERS_DIR = path.join(__dirname, 'users');
const RESPONSE_STATE_FILE = path.join(USERS_DIR, 'users_response_id.json');
const CHAT_HISTORY_FILE = path.join(USERS_DIR, 'users_chat.json');
const TOKEN_FILE = path.join(USERS_DIR, 'users_token.json');
const REQUEST_LOG_FILE = path.join(USERS_DIR, 'openclaw_request_log.jsonl');

const BRAND = 'openclaw';
const CATEGORY_CONTEXT = 'context';
const CATEGORY_HISTORY = 'history';
const CATEGORY_USER_ID = 'user_id';

function readConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const parsed = raw ? JSON.parse(raw) : {};
    const ubuntuRaw = fs.readFileSync(UBUNTU_CONFIG_PATH, 'utf8');
    const ubuntuConfig = ubuntuRaw ? JSON.parse(ubuntuRaw) : {};
    return {
      ...(parsed && typeof parsed === 'object' ? parsed : {}),
      ...(ubuntuConfig && typeof ubuntuConfig === 'object' ? ubuntuConfig : {})
    };
  } catch {
    try {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }
}

function ensureFile(filePath, fallbackValue) {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(fallbackValue, null, 2), 'utf8');
  }
}

function ensureResponseStateFile() {
  ensureFile(RESPONSE_STATE_FILE, []);
}

function ensureChatHistoryFile() {
  ensureFile(CHAT_HISTORY_FILE, []);
}

function ensureTokenFile() {
  ensureFile(TOKEN_FILE, []);
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

function normalizeResponseState(parsed) {
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
    return normalizeResponseState(parsed.users);
  }

  if (parsed && typeof parsed.users === 'object' && parsed.users) {
    return Object.values(parsed.users).flatMap((item) => normalizeResponseState([item]));
  }

  return [];
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

function readResponseState() {
  ensureResponseStateFile();

  try {
    const raw = fs.readFileSync(RESPONSE_STATE_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const users = normalizeResponseState(parsed);
    if (!Array.isArray(parsed)) {
      writeResponseState(users);
    }
    return users;
  } catch {
    const fallback = [];
    fs.writeFileSync(RESPONSE_STATE_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeResponseState(users) {
  ensureResponseStateFile();
  fs.writeFileSync(RESPONSE_STATE_FILE, JSON.stringify(users, null, 2), 'utf8');
}

function readChatHistory() {
  ensureChatHistoryFile();

  try {
    const raw = fs.readFileSync(CHAT_HISTORY_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const history = normalizeChatHistory(parsed);
    if (!Array.isArray(parsed)) {
      writeChatHistory(history);
    }
    return history;
  } catch {
    const fallback = [];
    fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeChatHistory(history) {
  ensureChatHistoryFile();
  fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(history, null, 2), 'utf8');
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

function appendRequestLog(entry) {
  fs.mkdirSync(USERS_DIR, { recursive: true });
  fs.appendFileSync(REQUEST_LOG_FILE, `${JSON.stringify(entry)}\n`, 'utf8');
}

function extractTextFromResponse(response) {
  if (typeof response.response === 'string' && response.response.trim()) {
    return response.response.trim();
  }

  if (typeof response.output_text === 'string' && response.output_text.trim()) {
    return response.output_text.trim();
  }

  const choices = Array.isArray(response.choices) ? response.choices : [];
  const firstChoice = choices[0];
  const content = firstChoice && firstChoice.message && typeof firstChoice.message.content === 'string'
    ? firstChoice.message.content.trim()
    : '';

  if (content) {
    return content;
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

function getOrCreateResponseState(users, userId) {
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

function getOrCreateChatHistoryRecord(history, userId) {
  const existing = history.find((item) => item.user_id === userId);
  if (existing) {
    return existing;
  }

  const created = {
    user_id: userId,
    history: []
  };
  history.push(created);
  return created;
}

function resolveRequestUserId(req, url, rawBody) {
  const source = req.method === 'GET'
    ? {
        userId: parseUserId(url.searchParams.get('user_id')),
        chatToken: parseChatToken(url.searchParams.get('chat_token'))
      }
    : (() => {
        const payload = parseJsonSafely(rawBody);
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

function resolveRequestIdentity(req, url, rawBody) {
  const raw = req.method === 'GET'
    ? {
        userId: parseUserId(url.searchParams.get('user_id')),
        chatToken: parseChatToken(url.searchParams.get('chat_token'))
      }
    : (() => {
        const payload = parseJsonSafely(rawBody);
        return {
          userId: parseUserId(String(payload.user_id ?? '')),
          chatToken: parseChatToken(payload.chat_token)
        };
      })();

  const hasUserId = raw.userId !== null;
  const hasChatToken = Boolean(raw.chatToken);

  if (hasUserId && hasChatToken) {
    return {
      error: 'Chỉ được truyền một trong hai biến: user_id hoặc chat_token'
    };
  }

  if (!hasUserId && !hasChatToken) {
    return {
      demo: true,
      userId: 0,
      chatToken: '',
      mode: 'demo'
    };
  }

  if (hasUserId) {
    return {
      userId: raw.userId,
      mode: 'user_id'
    };
  }

  const tokens = readTokenState();
  const mapped = tokens.find((item) => item.chat_token === raw.chatToken);
  if (!mapped) {
    return {
      error: 'chat_token không tồn tại trong users_token.json'
    };
  }

  return {
    userId: mapped.user_id,
    mode: 'chat_token',
    chatToken: raw.chatToken
  };
}

function normalizeBaseUrl(rawBaseUrl) {
  const fallback = 'https://oc.hust.media/v1';
  if (typeof rawBaseUrl !== 'string' || !rawBaseUrl.trim()) {
    return fallback;
  }

  const trimmed = rawBaseUrl.trim().replace(/\/+$/, '');
  if (/\/gpt_1\/v1$/i.test(trimmed)) {
    return trimmed.replace(/\/gpt_1\/v1$/i, '/v1');
  }

  if (/\/gpt_1$/i.test(trimmed)) {
    return `${trimmed}/v1`;
  }

  return trimmed;
}

function normalizeModel(rawModel) {
  if (typeof rawModel !== 'string' || !rawModel.trim()) {
    return 'openclaw/default';
  }

  const trimmed = rawModel.trim();
  if (trimmed === 'openclaw' || trimmed === 'openclaw:default') {
    return 'openclaw/default';
  }

  if (/^(agent|openclaw):/i.test(trimmed)) {
    return trimmed
      .replace(/^agent:/i, 'openclaw/')
      .replace(/^openclaw:/i, 'openclaw/');
  }

  return trimmed;
}

function normalizeBackendModel(rawModel) {
  if (typeof rawModel !== 'string' || !rawModel.trim()) {
    return '';
  }

  const trimmed = rawModel.trim();
  const lower = trimmed.toLowerCase();
  const aliasMap = {
    'qwen3.5-4b-ubuntu': 'qwen-3.5/qwen-3.5-ubuntu',
    'qwen3.5-4b': 'qwen-3.5/qwen-3.5',
    'qwen-3.5-ubuntu': 'qwen-3.5/qwen-3.5-ubuntu',
    'qwen-3.5': 'qwen-3.5/qwen-3.5'
  };

  return aliasMap[lower] || trimmed;
}

function normalizeModelCode(value) {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim().toLowerCase();
}

function shouldUseAgentRunEndpoint(payload = {}, config = {}) {
  const modelCode = normalizeModelCode(
    payload.model_code ??
      payload.ubuntu_model ??
      payload.x_openclaw_model ??
      config.model_code ??
      config.ubuntu_model ??
      config.x_openclaw_model ??
      ''
  );

  return modelCode === 'qwen-3.5/qwen-3.5-ubuntu';
}

function normalizeBoolean(value, fallback = false) {
  if (typeof value === 'boolean') {
    return value;
  }

  return fallback;
}

function getConfiguredSessionKey(config) {
  const fallback = 'agent:media_tech';
  if (typeof config.session_key === 'string' && config.session_key.trim()) {
    return config.session_key.trim();
  }

  return fallback;
}

function getConfiguredDemoSessionKey(config) {
  const base = getConfiguredSessionKey(config);
  if (typeof config.session_demo === 'string' && config.session_demo.trim()) {
    return config.session_demo.trim();
  }

  return `${base}:test_1`;
}

function buildConversationUserKey(userId, chatToken, demo = false) {
  if (demo) {
    return 'media_tech:demo';
  }

  if (Number.isInteger(userId)) {
    return `media_tech:user_${userId}`;
  }

  if (typeof chatToken === 'string' && chatToken.trim()) {
    return `media_tech:token_${chatToken.trim()}`;
  }

  return `media_tech:request_${Date.now()}`;
}

function buildConversationIdentity(config, userId, chatToken, demo = false) {
  const base = getConfiguredSessionKey(config);

  if (demo) {
    return {
      user: 'media_tech:demo',
      session_key: getConfiguredDemoSessionKey(config)
    };
  }

  if (Number.isInteger(userId)) {
    return {
      user: `media_tech:user_${userId}`,
      session_key: `${base}:user_${userId}`
    };
  }

  if (typeof chatToken === 'string' && chatToken.trim()) {
    return {
      user: `media_tech:token_${chatToken.trim()}`,
      session_key: `${base}:token_${chatToken.trim()}`
    };
  }

  return {
    user: `media_tech:request_${Date.now()}`,
    session_key: `${base}:request_${Date.now()}`
  };
}

async function callOpenClaw({ prompt, userKey, sessionKey, modelName, payload = {} }) {
  const config = readConfig();
  const baseUrl = normalizeBaseUrl(config.base_url);
  const apiKey = config.api_key || '';
  const selectedModel = typeof modelName === 'string' && modelName.trim()
    ? modelName.trim()
    : config.model || config.agent_model;
  const model = normalizeModel(selectedModel);
  const reasoningEffort = config.reasoning_effort || 'low';
  const temperature = typeof config.temperature === 'number' ? config.temperature : 0.2;
  const maxTokens = Number.isInteger(config.max_tokens) ? config.max_tokens : 128;
  const messageChannel = typeof config.message_channel === 'string' && config.message_channel.trim()
    ? config.message_channel.trim()
    : '';
  const backendModel = normalizeBackendModel(
    typeof payload.x_openclaw_model === 'string' && payload.x_openclaw_model.trim()
      ? payload.x_openclaw_model
      : typeof payload.upstream_model === 'string' && payload.upstream_model.trim()
        ? payload.upstream_model
        : typeof config.upstream_model === 'string' && config.upstream_model.trim()
          ? config.upstream_model
          : typeof config.x_openclaw_model === 'string' && config.x_openclaw_model.trim()
            ? config.x_openclaw_model
            : typeof config.ubuntu_model === 'string' && config.ubuntu_model.trim()
              ? config.ubuntu_model
              : typeof config.model === 'string' && config.model.trim()
                ? config.model
                : ''
  );
  const useLora = normalizeBoolean(
    payload.use_lora,
    normalizeBoolean(config.use_lora, false)
  );
  const useRag = normalizeBoolean(payload.use_rag, false);

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiKey}`
  };

  if (backendModel) {
    headers['x-openclaw-model'] = backendModel;
  }

  if (messageChannel) {
    headers['x-openclaw-message-channel'] = messageChannel;
  }

  if (sessionKey) {
    headers['x-openclaw-session-key'] = sessionKey;
  }

  const requestPath = shouldUseAgentRunEndpoint(payload, config)
    ? '/openclaw/agent/run'
    : '/chat/completions';
  const requestUrl = `${baseUrl}${requestPath}`;
  const requestBody = {
    model,
    user: userKey,
    session_key: sessionKey,
    messages: [
      {
        role: 'user',
        content: prompt
      }
    ],
    reasoning_effort: reasoningEffort,
    temperature,
    max_tokens: maxTokens,
    top_p: typeof payload.top_p === 'number' ? payload.top_p : 0.9,
    enable_thinking: parseBooleanFlag(payload.enable_thinking, false),
    use_lora: useLora,
    use_rag: useRag,
    rag_top_k: Number.isInteger(payload.rag_top_k) ? payload.rag_top_k : 4
  };

  process.stderr.write(
    `[openclaw] POST ${requestUrl}\n${JSON.stringify(requestBody, null, 2)}\n`
  );
  try {
    const response = await fetch(requestUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });

    const text = await response.text();
    let parsed = {};
    try {
      parsed = text ? JSON.parse(text) : {};
    } catch {
      parsed = { raw: text };
    }

    appendRequestLog({
      timestamp: new Date().toISOString(),
      request_url: requestUrl,
      request_body: requestBody,
      response_status: response.status,
      response_body: parsed
    });

    if (!response.ok) {
      const error = new Error(`OpenClaw HTTP ${response.status}`);
      error.statusCode = response.status;
      error.payload = parsed;
      throw error;
    }

    return parsed;
  } catch (error) {
    appendRequestLog({
      timestamp: new Date().toISOString(),
      request_url: requestUrl,
      request_body: requestBody,
      response_error: error && error.message ? error.message : String(error)
    });
    throw error;
  }
}

function getPromptFromRequest(req, url, rawBody) {
  if (req.method === 'GET') {
    return (
      url.searchParams.get('message') ||
      url.searchParams.get('text') ||
      url.searchParams.get('query') ||
      'xin chao'
    ).trim();
  }

  const payload = parseJsonSafely(rawBody);
  return (
    (typeof payload.message === 'string' && payload.message) ||
    (typeof payload.text === 'string' && payload.text) ||
    (typeof payload.query === 'string' && payload.query) ||
    'xin chao'
  ).trim();
}

function parseBooleanFlag(value, fallback = false) {
  if (typeof value === 'boolean') {
    return value;
  }

  if (typeof value === 'number') {
    return value !== 0;
  }

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) {
      return true;
    }
    if (["0", "false", "no", "n", "off"].includes(normalized)) {
      return false;
    }
  }

  return fallback;
}

function getNextUserId(state) {
  const maxUserId = state.reduce((max, item) => (
    Number.isInteger(item.user_id) && item.user_id > max ? item.user_id : max
  ), 0);
  return maxUserId + 1;
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

function isValidChatToken(chatToken) {
  return typeof chatToken === 'string' && chatToken.length > 15;
}

module.exports = {
  BRAND,
  CATEGORY_CONTEXT,
  CATEGORY_HISTORY,
  CATEGORY_USER_ID,
  buildConversationUserKey,
  buildConversationIdentity,
  callOpenClaw,
  extractTextFromResponse,
  getOrCreateChatHistoryRecord,
  getOrCreateResponseState,
  getPromptFromRequest,
  getConfiguredDemoSessionKey,
  getConfiguredSessionKey,
  getNextUserId,
  normalizeBaseUrl,
  normalizeModel,
  normalizeBoolean,
  parseChatToken,
  parseJsonSafely,
  parseUserId,
  readChatHistory,
  readConfig,
  readResponseState,
  readTokenState,
  resolveRequestIdentity,
  resolveRequestUserId,
  upsertChatToken,
  isValidChatToken,
  writeChatHistory,
  writeResponseState,
  writeTokenState
};
