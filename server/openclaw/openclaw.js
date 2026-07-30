const fs = require('fs');
const http = require('http');
const path = require('path');
const { WebSocketServer } = require('/opt/openclaw/node_modules/ws');

const PORT = Number(process.env.PORT || 8802);
const WS_PATH = process.env.WS_PATH || '/chatbot/gpu';
const CONFIG_PATH = process.env.OPENCLAW_CONFIG_PATH || path.join(__dirname, 'config.json');
const CONTROL_UI_DIR = path.join(__dirname, 'control-ui', 'control-ui');
const CONTROL_UI_CONFIG_PATH = '/__openclaw/control-ui-config.json';

function readConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function json(res, statusCode, data) {
  const body = JSON.stringify(data);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function html(res, statusCode, body) {
  res.writeHead(statusCode, {
    'Content-Type': 'text/html; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function fileExists(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function safeResolveStaticPath(requestPath) {
  const normalized = path.posix.normalize(`/${requestPath || ''}`.replace(/^\/+/, '/'));
  const candidate = path.join(CONTROL_UI_DIR, normalized);
  const resolvedRoot = path.resolve(CONTROL_UI_DIR) + path.sep;
  const resolvedCandidate = path.resolve(candidate);
  if (!resolvedCandidate.startsWith(resolvedRoot)) {
    return null;
  }
  return resolvedCandidate;
}

function contentTypeFor(filePath) {
  switch (path.extname(filePath).toLowerCase()) {
    case '.js':
      return 'application/javascript; charset=utf-8';
    case '.mjs':
      return 'application/javascript; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.svg':
      return 'image/svg+xml';
    case '.png':
      return 'image/png';
    case '.ico':
      return 'image/x-icon';
    case '.webmanifest':
      return 'application/manifest+json; charset=utf-8';
    case '.map':
      return 'application/json; charset=utf-8';
    case '.html':
    default:
      return 'text/html; charset=utf-8';
  }
}

function serveFile(res, filePath, { cacheControl = 'no-cache' } = {}) {
  const data = fs.readFileSync(filePath);
  res.writeHead(200, {
    'Content-Type': contentTypeFor(filePath),
    'Cache-Control': cacheControl,
    'Content-Length': data.length,
  });
  res.end(data);
}

function serveControlUiIndex(res) {
  const indexPath = path.join(CONTROL_UI_DIR, 'index.html');
  if (!fileExists(indexPath)) {
    return json(res, 500, { ok: false, error: 'OpenClaw Control UI assets are missing' });
  }
  return serveFile(res, indexPath);
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

function resolveFrontendUiUrl(req) {
  const hostHeader = String(req.headers.host || '').trim();
  const hostname = hostHeader ? hostHeader.split(':')[0] : 'localhost';
  return `http://${hostname}:8008/chat_bot/qwen`;
}

const server = http.createServer((req, res) => {
  const requestUrl = new URL(req.url || '/', 'http://localhost');
  const pathname = requestUrl.pathname;

  if (req.method === 'GET' && pathname === CONTROL_UI_CONFIG_PATH) {
    return json(res, 200, {
      assistantName: readConfig().assistantName || 'OpenClaw',
      assistantAvatar: readConfig().assistantAvatar || null,
      assistantAgentId: readConfig().assistantAgentId || null,
      serverVersion: readConfig().serverVersion || 'local-openclaw',
    });
  }

  if (req.method === 'GET' && (pathname === '/' || pathname === '/dashboard' || pathname === '/index.html')) {
    return serveControlUiIndex(res);
  }

  const staticPrefixes = ['/assets/', '/favicon.svg', '/favicon.ico', '/favicon-32.png', '/apple-touch-icon.png', '/manifest.webmanifest'];
  const isStaticAsset = staticPrefixes.some((prefix) => pathname === prefix.slice(0, -1) || pathname.startsWith(prefix));
  if (req.method === 'GET' && isStaticAsset) {
    const staticPath = pathname === '/manifest.webmanifest'
      ? path.join(CONTROL_UI_DIR, 'manifest.webmanifest')
      : safeResolveStaticPath(pathname.slice(1));
    if (staticPath && fileExists(staticPath)) {
      return serveFile(res, staticPath);
    }
    if (pathname.startsWith('/assets/')) {
      const assetPath = safeResolveStaticPath(pathname.slice(1));
      if (assetPath && fileExists(assetPath)) {
        return serveFile(res, assetPath);
      }
    }
    return json(res, 404, { ok: false, error: 'Not found' });
  }

  if (req.method === 'GET' && (pathname === '/health' || pathname === '/v1/health')) {
    return json(res, 200, {
      ok: true,
      service: 'openclaw',
      wsPath: WS_PATH,
      dashboard: '/',
      ui: `http://${String(req.headers.host || 'localhost')}/`,
      controlUiConfig: CONTROL_UI_CONFIG_PATH,
    });
  }

  if (req.method === 'GET' && pathname === WS_PATH) {
    return json(res, 200, { ok: true, service: 'openclaw', websocket: true });
  }

  if (req.method === 'GET' && pathname === '/openclaw/agent/health') {
    return json(res, 200, { ok: true, route: '/openclaw/agent/health', brand: 'openclaw', runtime: 'openclaw' });
  }

  const postRoutes = new Set(['/v1/chat/completions', '/chat/completions', '/openclaw/chat/completions', '/openclaw/agent/run']);
  if (req.method === 'POST' && postRoutes.has(pathname)) {
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

  if (req.method === 'GET') {
    const assetPath = safeResolveStaticPath(pathname.replace(/^\//, ''));
    if (assetPath && fileExists(assetPath)) {
      return serveFile(res, assetPath);
    }
    return serveControlUiIndex(res);
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
    if (url.pathname !== '/' && url.pathname !== WS_PATH) {
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
