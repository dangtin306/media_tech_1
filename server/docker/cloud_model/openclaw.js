const http = require('http');
const { WebSocketServer } = require('/workspace/backend/node_modules/ws');

const PORT = Number(process.env.PORT || 8796);
const WS_PATH = process.env.WS_PATH || '/chatbot/gpu';

function json(res, statusCode, data) {
  const body = JSON.stringify(data);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function parseJsonSafely(raw) {
  if (typeof raw !== 'string' || !raw.trim()) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) {
        req.destroy();
        reject(new Error('Request body too large'));
      }
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

function extractPrompt(payload) {
  const data = payload && typeof payload.data === 'object' ? payload.data : null;
  if (data) {
    if (typeof data.user_message === 'string' && data.user_message.trim()) {
      return data.user_message.trim();
    }
    if (Array.isArray(data.messages)) {
      const lastUser = [...data.messages].reverse().find((item) => item && item.role === 'user' && typeof item.content === 'string' && item.content.trim());
      if (lastUser) {
        return lastUser.content.trim();
      }
    }
  }

  if (typeof payload?.data === 'string' && payload.data.trim()) {
    const parsed = parseJsonSafely(payload.data);
    if (parsed) {
      return extractPrompt({ data: parsed });
    }
    return payload.data.trim();
  }

  return 'xin chao';
}

function buildResponseText(payload) {
  const prompt = extractPrompt(payload);
  const response = {
    ok: true,
    source: 'openclaw',
    response: `SIMULATED GPU RESPONSE: ${prompt}`,
    output_text: `SIMULATED GPU RESPONSE: ${prompt}`,
    echo: payload?.data ?? null,
  };
  return JSON.stringify(response);
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && (req.url === '/health' || req.url === '/v1/health')) {
    return json(res, 200, { ok: true, service: 'openclaw', wsPath: WS_PATH });
  }

  if (req.method === 'GET' && req.url === WS_PATH) {
    return json(res, 200, { ok: true, service: 'openclaw', websocket: true });
  }

  if (req.method === 'GET' && req.url === '/openclaw/agent/health') {
    return json(res, 200, { ok: true, route: '/openclaw/agent/health', brand: 'openclaw', runtime: 'openclaw' });
  }

  const postRoutes = new Set(['/v1/chat/completions', '/chat/completions', '/openclaw/chat/completions', '/openclaw/agent/run']);
  if (req.method === 'POST' && postRoutes.has(req.url || '')) {
    readBody(req)
      .then((body) => {
        const payload = parseJsonSafely(body) || {};
        const responseText = buildResponseText(payload);
        return json(res, 200, {
          ok: true,
          id: `openclaw-${Date.now()}`,
          response: responseText,
          output_text: responseText,
          data_response: responseText,
          model: payload.model || 'openclaw/qwen-agent',
          usage: {
            prompt_tokens: 1,
            completion_tokens: 1,
            total_tokens: 2,
          },
        });
      })
      .catch((error) => json(res, 500, { ok: false, error: error.message || 'request failed' }));
    return;
  }

  return json(res, 404, { ok: false, error: 'Not found' });
});

const wss = new WebSocketServer({ noServer: true });

wss.on('connection', (socket) => {
  socket.on('message', (raw) => {
    const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : String(raw || '');
    if (!text.trim()) {
      return;
    }

    const payload = parseJsonSafely(text);
    if (!payload || typeof payload !== 'object') {
      return;
    }

    if (payload.category !== 'api_call') {
      return;
    }

    const requestId = typeof payload.request_id === 'string' ? payload.request_id.trim() : '';
    const responsePayload = {
      device: 'gpu',
      url: payload.url ?? '',
      data_response: buildResponseText(payload),
      category: 'api_response',
      service: payload.service ?? 'POST',
      status: 200,
      request_id: requestId,
    };

    socket.send(JSON.stringify(responsePayload));
  });
});

server.on('upgrade', (req, socket, head) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname !== WS_PATH) {
      socket.destroy();
      return;
    }

    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  } catch {
    socket.destroy();
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`openclaw listening on http://0.0.0.0:${PORT}${WS_PATH}`);
});
