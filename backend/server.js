const http = require('http');
const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');
const OpenAI = require('openai');
const { createTestAi1Route } = require('./open_ai/test_ai_1');
const { createTestAi2Route } = require('./open_ai/test_ai_2');
const { createMainRoute } = require('./open_ai/main');
const { createOpenClawRoute } = require('./openclaw/main');
const { readConfig } = require('./openclaw/shared');
const { createUbuntuRoute, verifyUbuntuSshConnection } = require('./openclaw/ubuntu/main');
const { createUbuntuRoute: createQwenRoute } = require('./openclaw/ubuntu/qwen');
const { createLevelRoute: createQwenLevelRoute } = require('./openclaw/ubuntu/qwen_level');
const { createWebservice } = require('./openclaw/ubuntu/webservice');
const { startGpuWebserviceClient } = require('./openclaw/ubuntu/webservice_gpu_start');
const { createQdrantRoute } = require('./process/qdrant');

const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  dotenv.config({ path: envPath });
} else {
  dotenv.config();
}

const PORT = Number(process.env.PORT || 8006);
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const openai = OPENAI_API_KEY ? new OpenAI({ apiKey: OPENAI_API_KEY }) : null;

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Max-Age', '86400');
}

function sendJson(res, statusCode, data) {
  const body = JSON.stringify(data);
  setCorsHeaders(res);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body)
  });
  res.end(body);
}

function sendError(res, statusCode, message) {
  return sendJson(res, statusCode, {
    ok: false,
    error: message
  });
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

function getChatBrandFromRequest(req, url, rawBody) {
  if (req.method === 'GET') {
    return (url.searchParams.get('brand') || 'open_ai_api').trim();
  }

  const payload = parseJsonSafely(rawBody);
  return typeof payload.brand === 'string' && payload.brand.trim()
    ? payload.brand.trim()
    : 'open_ai_api';
}

const testAi1Route = createTestAi1Route({
  openai,
  sendJson,
  sendError,
  readBody
});

const testAi2Route = createTestAi2Route({
  openai,
  sendJson,
  sendError,
  readBody
});

const testAi3Route = createMainRoute({
  openai,
  sendJson,
  sendError,
  readBody
});

const openClawRoute = createOpenClawRoute({
  sendJson,
  sendError,
  readBody
});

const openClawConfig = readConfig();

const openClawUbuntuRoute = createUbuntuRoute({
  sendJson,
  sendError,
  readBody,
  config: openClawConfig
});

const openClawQwenRoute = createQwenRoute({
  sendJson,
  sendError,
  readBody,
  config: openClawConfig
});

const openClawQwenLevelRoute = createQwenLevelRoute({
  sendJson,
  sendError,
  readBody,
  config: openClawConfig
});

let openClawWebserviceRoute;
let openClawGpuClient;

const qdrantRoute = createQdrantRoute({
  sendJson,
  sendError,
  readBody
});

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  setCorsHeaders(res);

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  if (req.method === 'GET' && url.pathname === '/health') {
    return sendJson(res, 200, { ok: true });
  }

  if (url.pathname === '/chatbot/qwen' || url.pathname === '/chatbot/gpu') {
    const handled = await openClawWebserviceRoute(req, res, url);
    if (handled) {
      return;
    }
  }

  await testAi1Route(req, res, url);
  if (res.writableEnded) {
    return;
  }

  await testAi2Route(req, res, url);
  if (res.writableEnded) {
    return;
  }

  if (url.pathname === '/chat_bot/api') {
    const rawBody = req.method === 'POST' ? await readBody(req) : '';
    const brand = getChatBrandFromRequest(req, url, rawBody);

    if (brand === 'openclaw') {
      await openClawRoute(req, res, url, rawBody);
      if (res.writableEnded) {
        return;
      }
    } else {
      const openAiRoute = createMainRoute({
        openai,
        sendJson,
        sendError,
        readBody: async () => rawBody
      });
      await openAiRoute(req, res, url);
      if (res.writableEnded) {
        return;
      }
    }
  }

  if (url.pathname.startsWith('/openclaw/agent/')) {
    const rawBody = req.method === 'POST' ? await readBody(req) : '';
    await openClawUbuntuRoute(req, res, url, rawBody);
    if (res.writableEnded) {
      return;
    }

    await openClawQwenRoute(req, res, url, rawBody);
    if (res.writableEnded) {
      return;
    }

    await openClawQwenLevelRoute(req, res, url, rawBody);
    if (res.writableEnded) {
      return;
    }
  }

  if (url.pathname.startsWith('/openclaw/')) {
    const rawBody = req.method === 'POST' ? await readBody(req) : '';
    await openClawUbuntuRoute(req, res, url, rawBody);
    if (res.writableEnded) {
      return;
    }
  }

  await qdrantRoute(req, res, url);
  if (res.writableEnded) {
    return;
  }

  return sendError(res, 404, 'Not found');
});

openClawWebserviceRoute = createWebservice({
  server,
  sendJson,
  sendError
});

server.on('error', (error) => {
  if (error && error.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is already in use. Stop the existing process and restart the server.`);
    return;
  }

  console.error(error);
});

async function startServer() {
  const qwenWinMode = openClawConfig.qwen_win === true;

  if (qwenWinMode) {
    console.log('[startup] qwen_win=true; skipping Ubuntu SSH preflight');
  } else {
    try {
      const ok = await verifyUbuntuSshConnection(openClawConfig);
      console.log(`[startup] ubuntu_ssh_preflight=${ok ? 'ok' : 'failed'}`);
    } catch (error) {
      console.error(`[startup] ubuntu_ssh_preflight_failed: ${error.message}`);
    }
  }

  server.listen(PORT, () => {
    console.log(`Media Tech backend running on http://localhost:${PORT}`);
    openClawGpuClient = startGpuWebserviceClient({
      config: openClawConfig
    });
  });

  if (qwenWinMode) {
    console.log('[startup] qwen_win=true; skipping Ubuntu SSH prewarm');
  } else {
    void (async () => {
      try {
        const { pingConnection } = require('./openclaw/ubuntu/connect');
        await pingConnection(openClawConfig);
        console.log('[startup] ubuntu_ssh_prewarm=ok');
      } catch (error) {
        console.warn(`[startup] ubuntu_ssh_prewarm_failed: ${error.message}`);
      }
    })();
  }
}

startServer().catch((error) => {
  console.error(error);
});
