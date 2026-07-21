const fs = require('fs');
const path = require('path');
const AI_CONFIG = require('./config.json');

const USERS_DIR = path.join(__dirname, 'users');
const STATE_FILE = path.join(USERS_DIR, 'test_ai_3.json');
const SAMPLE_MESSAGE = AI_CONFIG.sample_message;

function ensureStateFile() {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(STATE_FILE)) {
    fs.writeFileSync(STATE_FILE, JSON.stringify([], null, 2), 'utf8');
  }
}

function normalizeState(parsed) {
  if (Array.isArray(parsed)) {
    return parsed.filter((item) => item && Number.isInteger(item.user_id)).map((item) => ({
      user_id: item.user_id,
      latest_response_id: typeof item.latest_response_id === 'string' ? item.latest_response_id : null,
      previous_response_ids: Array.isArray(item.previous_response_ids)
        ? item.previous_response_ids.filter((id) => typeof id === 'string')
        : []
    }));
  }

  if (parsed && Array.isArray(parsed.users)) {
    return normalizeState(parsed.users);
  }

  if (parsed && typeof parsed.users === 'object' && parsed.users) {
    return Object.values(parsed.users).flatMap((item) => normalizeState([item]));
  }

  return [];
}

function readState() {
  ensureStateFile();

  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : [];
    const users = normalizeState(parsed);
    if (!Array.isArray(parsed)) {
      writeState(users);
    }
    return users;
  } catch {
    const fallback = [];
    fs.writeFileSync(STATE_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeState(users) {
  ensureStateFile();
  fs.writeFileSync(STATE_FILE, JSON.stringify(users, null, 2), 'utf8');
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

async function askOpenAI(openai, userId, message) {
  const users = readState();
  const userState = getOrCreateUserState(users, userId);

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

  userState.latest_response_id = response.id;
  userState.previous_response_ids = [...userState.previous_response_ids, response.id];
  writeState(users);

  return {
    answer,
    previous_response_id_used: request.previous_response_id || null,
    latest_response_id: response.id,
    user_state: userState
  };
}

function createTestAi3Route({ openai, sendJson, sendError, readBody }) {
  return async function testAi3Route(req, res, url) {
    if (req.method === 'GET' && url.pathname === '/test_ai_3') {
      if (!openai) {
        return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
      }

      const userId = parseUserId(url.searchParams.get('user_id'));
      if (userId === null) {
        return sendError(res, 400, 'user_id phải là số');
      }

      const text = url.searchParams.get('text');
      if (text && text.trim()) {
        const result = await askOpenAI(openai, userId, text.trim());
        return sendJson(res, 200, {
          ok: true,
          user_id: userId,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.latest_response_id
        });
      }

      const users = readState();
      const userState = users.find((item) => item.user_id === userId) || {
        user_id: userId,
        latest_response_id: null,
        previous_response_ids: []
      };

      return sendJson(res, 200, {
        ok: true,
        endpoint: '/test_ai_3',
        user_id: userId,
        sampleRequest: {
          user_id: userId,
          message: SAMPLE_MESSAGE
        },
        user_state: userState
      });
    }

    if (req.method === 'POST' && url.pathname === '/test_ai_3') {
      try {
        if (!openai) {
          return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
        }

        const rawBody = await readBody(req);
        const payload = rawBody ? JSON.parse(rawBody) : {};
        const userId = parseUserId(String(payload.user_id ?? ''));

        if (userId === null) {
          return sendError(res, 400, 'user_id phải là số');
        }

        if (!payload.message || typeof payload.message !== 'string') {
          return sendError(res, 400, 'Body phải có field "message" dạng chuỗi');
        }

        const result = await askOpenAI(openai, userId, payload.message);
        return sendJson(res, 200, {
          ok: true,
          user_id: userId,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.latest_response_id
        });
      } catch (error) {
        return sendError(res, 400, error.message);
      }
    }

    return false;
  };
}

module.exports = {
  createTestAi3Route
};
