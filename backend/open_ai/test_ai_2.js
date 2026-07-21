const fs = require('fs');
const path = require('path');
const AI_CONFIG = require('./config.json');

const VECTOR_STORE_ID = AI_CONFIG.vector_store_id;
const SYSTEM_PROMPT = AI_CONFIG.system_prompt;
const SAMPLE_MESSAGE = AI_CONFIG.sample_message;

const USERS_DIR = path.join(__dirname, 'users');
const STATE_FILE = path.join(USERS_DIR, 'test_ai_2.json');

function ensureStateFile() {
  fs.mkdirSync(USERS_DIR, { recursive: true });

  if (!fs.existsSync(STATE_FILE)) {
    fs.writeFileSync(
      STATE_FILE,
      JSON.stringify(
        {
          latest_response_id: null,
          previous_response_ids: []
        },
        null,
        2
      ),
      'utf8'
    );
  }
}

function readState() {
  ensureStateFile();

  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf8');
    const parsed = raw ? JSON.parse(raw) : {};

    return {
      latest_response_id: typeof parsed.latest_response_id === 'string' ? parsed.latest_response_id : null,
      previous_response_ids: Array.isArray(parsed.previous_response_ids) ? parsed.previous_response_ids.filter((id) => typeof id === 'string') : []
    };
  } catch {
    const fallback = {
      latest_response_id: null,
      previous_response_ids: []
    };
    fs.writeFileSync(STATE_FILE, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeState(state) {
  ensureStateFile();
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
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

async function askOpenAI(openai, message) {
  const state = readState();
  const request = {
    model: AI_CONFIG.model,
    instructions: SYSTEM_PROMPT,
    input: message,
    tools: [AI_CONFIG.tools.file_search],
    store: AI_CONFIG.store,
    temperature: AI_CONFIG.temperature,
    top_p: AI_CONFIG.top_p,
    text: AI_CONFIG.text
  };

  if (state.latest_response_id) {
    request.previous_response_id = state.latest_response_id;
  }

  const response = await openai.responses.create(request);
  const answer = extractTextFromResponse(response) || AI_CONFIG.fallback_answer;

  const nextState = {
    latest_response_id: response.id,
    previous_response_ids: [...state.previous_response_ids, response.id]
  };
  writeState(nextState);

  return {
    response,
    answer,
    previous_response_id_used: request.previous_response_id || null,
    stored_state: nextState
  };
}

function createTestAi2Route({ openai, sendJson, sendError, readBody }) {
  return async function testAi2Route(req, res, url) {
    if (req.method === 'GET' && url.pathname === '/test_ai_2') {
      if (!openai) {
        return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
      }

      const text = url.searchParams.get('text');
      if (text && text.trim()) {
        const result = await askOpenAI(openai, text.trim());
        return sendJson(res, 200, {
          ok: true,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.stored_state.latest_response_id
        });
      }

      const state = readState();
      return sendJson(res, 200, {
        ok: true,
        endpoint: '/test_ai_2',
        sampleRequest: {
          message: SAMPLE_MESSAGE
        },
        stored_state: state
      });
    }

    if (req.method === 'POST' && url.pathname === '/test_ai_2') {
      try {
        if (!openai) {
          return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
        }

        const rawBody = await readBody(req);
        const payload = rawBody ? JSON.parse(rawBody) : {};

        if (!payload.message || typeof payload.message !== 'string') {
          return sendError(res, 400, 'Body phải có field "message" dạng chuỗi');
        }

        const result = await askOpenAI(openai, payload.message);
        return sendJson(res, 200, {
          ok: true,
          answer: result.answer,
          previous_response_id_used: result.previous_response_id_used,
          latest_response_id: result.stored_state.latest_response_id
        });
      } catch (error) {
        return sendError(res, 400, error.message);
      }
    }

    return false;
  };
}

module.exports = {
  createTestAi2Route
};
