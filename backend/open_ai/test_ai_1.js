const AI_CONFIG = require('./config.json');

const VECTOR_STORE_ID = AI_CONFIG.vector_store_id;
const SYSTEM_PROMPT = AI_CONFIG.system_prompt;
const SAMPLE_MESSAGE = AI_CONFIG.sample_message;

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
  const response = await openai.responses.create({
    model: AI_CONFIG.model,
    instructions: SYSTEM_PROMPT,
    input: message,
    tools: [AI_CONFIG.tools.file_search],
    store: AI_CONFIG.store,
    temperature: AI_CONFIG.temperature,
    top_p: AI_CONFIG.top_p,
    text: AI_CONFIG.text
  });

  return {
    response,
    answer: extractTextFromResponse(response) || AI_CONFIG.fallback_answer
  };
}

function createTestAi1Route({ openai, sendJson, sendError, readBody }) {
  return async function testAi1Route(req, res, url) {
    if (req.method === 'GET' && url.pathname === '/test_ai_1') {
      if (!openai) {
        return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
      }

      const text = url.searchParams.get('text');
      if (text && text.trim()) {
        const { answer } = await askOpenAI(openai, text.trim());
        return sendJson(res, 200, {
          ok: true,
          answer
        });
      }

      const sampleOpenAIResponse = await askOpenAI(openai, SAMPLE_MESSAGE);
      return sendJson(res, 200, {
        ok: true,
        endpoint: '/test_ai_1',
        sampleRequest: {
          message: SAMPLE_MESSAGE
        },
        sampleOpenAIResponse: {
          model: AI_CONFIG.model,
          vector_store_id: VECTOR_STORE_ID,
          answer: sampleOpenAIResponse.answer
        }
      });
    }

    if (req.method === 'POST' && (url.pathname === '/chat' || url.pathname === '/test_ai_1')) {
      try {
        if (!openai) {
          return sendError(res, 500, 'Missing OPENAI_API_KEY in .env');
        }

        const rawBody = await readBody(req);
        const payload = rawBody ? JSON.parse(rawBody) : {};

        if (!payload.message || typeof payload.message !== 'string') {
          return sendError(res, 400, 'Body phải có field "message" dạng chuỗi');
        }

        const { answer } = await askOpenAI(openai, payload.message);
        return sendJson(res, 200, {
          ok: true,
          answer
        });
      } catch (error) {
        return sendError(res, 400, error.message);
      }
    }

    return false;
  };
}

module.exports = {
  createTestAi1Route
};
