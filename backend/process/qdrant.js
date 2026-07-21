const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const { execFile } = require('child_process');

const DATA_DIR = path.join(__dirname, '..', '..', 'ai', 'qdrant', 'data_1');
const CONFIG_PATH = path.join(DATA_DIR, 'qdrant_collection_config.json');
const DEFAULT_QDRANT_URL = process.env.QDRANT_URL || 'http://localhost:6333';
const PYTHON_BIN = process.env.QDRANT_PYTHON_BIN || 'python';

function readCollectionConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

const COLLECTION_CONFIG = readCollectionConfig();
const DEFAULT_COLLECTION = process.env.QDRANT_COLLECTION || COLLECTION_CONFIG.collection_name || 'dulich_demo';

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

function parseLimit(value, fallback = 5) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return fallback;
  }
  return Math.min(Math.floor(num), 50);
}

function parseBoolean(value, fallback = true) {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) {
      return true;
    }
    if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) {
      return false;
    }
  }
  return fallback;
}

function normalizeProxyPath(rawPath, fallbackPath) {
  if (typeof rawPath !== 'string' || !rawPath.trim()) {
    return fallbackPath;
  }

  const trimmed = rawPath.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    throw new Error('path chỉ được là path nội bộ của Qdrant, không được là URL đầy đủ');
  }

  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
}

function requestJson(method, targetUrl, body) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(targetUrl);
    const transport = urlObj.protocol === 'https:' ? https : http;
    const payload = body === undefined ? null : JSON.stringify(body);

    const req = transport.request(
      urlObj,
      {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {})
        }
      },
      (res) => {
        let raw = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          raw += chunk;
        });
        res.on('end', () => {
          let parsed = raw;
          if (raw) {
            try {
              parsed = JSON.parse(raw);
            } catch {
              parsed = raw;
            }
          }

          if (res.statusCode >= 400) {
            const error = new Error(`Qdrant trả về HTTP ${res.statusCode}`);
            error.statusCode = res.statusCode;
            error.payload = parsed;
            return reject(error);
          }

          return resolve(parsed);
        });
      }
    );

    req.on('error', reject);
    if (payload) {
      req.write(payload);
    }
    req.end();
  });
}

function runTextSearch({ qdrantUrl, collection, query, limit, withPayload }) {
  const script = [
    'import json, sys, urllib.request',
    'from sklearn.feature_extraction.text import HashingVectorizer',
    '',
    'base = sys.argv[1].rstrip("/")',
    'collection = sys.argv[2]',
    'query = sys.argv[3]',
    'limit = int(sys.argv[4])',
    'with_payload = sys.argv[5] == "1"',
    '',
    'hv = HashingVectorizer(',
    '    n_features=384,',
    '    analyzer="char_wb",',
    '    ngram_range=(3, 5),',
    '    alternate_sign=False,',
    '    norm="l2",',
    '    lowercase=True,',
    ')',
    'vec = hv.transform([query]).toarray()[0]',
    'body = {',
    '    "vector": [round(float(v), 6) for v in vec],',
    '    "limit": limit,',
    '    "with_payload": with_payload,',
    '}',
    'data = json.dumps(body, ensure_ascii=False).encode("utf-8")',
    'req = urllib.request.Request(',
    '    f"{base}/collections/{collection}/points/search",',
    '    data=data,',
    '    method="POST",',
    ')',
    'req.add_header("Content-Type", "application/json")',
    'with urllib.request.urlopen(req, timeout=120) as resp:',
    '    print(resp.read().decode("utf-8"))'
  ].join('\n');

  return new Promise((resolve, reject) => {
    execFile(
      PYTHON_BIN,
      ['-X', 'utf8', '-c', script, qdrantUrl, collection, query, String(limit), withPayload ? '1' : '0'],
      {
        windowsHide: true,
        maxBuffer: 10 * 1024 * 1024,
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8'
        }
      },
      (error, stdout, stderr) => {
        if (error) {
          const details = stderr && stderr.trim() ? stderr.trim() : error.message;
          return reject(new Error(`Không query được Qdrant qua Python: ${details}`));
        }

        try {
          return resolve(JSON.parse(stdout));
        } catch {
          return reject(new Error('Qdrant query trả về dữ liệu không parse được'));
        }
      }
    );
  });
}

function getQueryValue(payload, url) {
  const candidates = [
    payload.query,
    payload.message,
    payload.text,
    url.searchParams.get('query'),
    url.searchParams.get('message'),
    url.searchParams.get('text')
  ];

  for (const value of candidates) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }

  return '';
}

async function handleCollectionInfo(url) {
  const collection = url.searchParams.get('collection') || DEFAULT_COLLECTION;
  const proxyPath = normalizeProxyPath(
    url.searchParams.get('path'),
    `/collections/${collection}`
  );
  return requestJson('GET', `${DEFAULT_QDRANT_URL}${proxyPath}`);
}

async function handlePostRequest(payload) {
  const collection = typeof payload.collection === 'string' && payload.collection.trim()
    ? payload.collection.trim()
    : DEFAULT_COLLECTION;
  const limit = parseLimit(payload.limit, 5);
  const withPayload = parseBoolean(payload.with_payload, true);

  if (typeof payload.path === 'string' && payload.path.trim()) {
    const proxyPath = normalizeProxyPath(payload.path, `/collections/${collection}`);
    const method = typeof payload.method === 'string' && payload.method.trim()
      ? payload.method.trim().toUpperCase()
      : 'POST';
    return requestJson(method, `${DEFAULT_QDRANT_URL}${proxyPath}`, payload.body);
  }

  if (Array.isArray(payload.vector) && payload.vector.length > 0) {
    return requestJson(
      'POST',
      `${DEFAULT_QDRANT_URL}/collections/${collection}/points/search`,
      {
        vector: payload.vector,
        limit,
        with_payload: withPayload,
        ...(payload.filter ? { filter: payload.filter } : {})
      }
    );
  }

  const query = getQueryValue(payload, new URL('http://localhost'));
  if (!query) {
    throw new Error('Body phải có query/message/text, hoặc vector, hoặc path');
  }

  return runTextSearch({
    qdrantUrl: DEFAULT_QDRANT_URL,
    collection,
    query,
    limit,
    withPayload
  });
}

function createQdrantRoute({ sendJson, sendError, readBody }) {
  return async function qdrantRoute(req, res, url) {
    if (url.pathname !== '/qdrant') {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    try {
      if (req.method === 'GET') {
        const query = getQueryValue({}, url);
        if (query) {
          const collection = url.searchParams.get('collection') || DEFAULT_COLLECTION;
          const limit = parseLimit(url.searchParams.get('limit'), 5);
          const withPayload = parseBoolean(url.searchParams.get('with_payload'), true);
          const result = await runTextSearch({
            qdrantUrl: DEFAULT_QDRANT_URL,
            collection,
            query,
            limit,
            withPayload
          });
          return sendJson(res, 200, {
            ok: true,
            route: '/qdrant',
            mode: 'text_search',
            qdrant_url: DEFAULT_QDRANT_URL,
            collection,
            query,
            result
          });
        }

        const result = await handleCollectionInfo(url);
        return sendJson(res, 200, {
          ok: true,
          route: '/qdrant',
          mode: 'info',
          qdrant_url: DEFAULT_QDRANT_URL,
          collection: url.searchParams.get('collection') || DEFAULT_COLLECTION,
          result
        });
      }

      const rawBody = await readBody(req);
      const payload = parseJsonSafely(rawBody);
      const result = await handlePostRequest(payload);
      return sendJson(res, 200, {
        ok: true,
        route: '/qdrant',
        qdrant_url: DEFAULT_QDRANT_URL,
        collection: payload.collection || DEFAULT_COLLECTION,
        result
      });
    } catch (error) {
      const statusCode = error && error.statusCode ? error.statusCode : 400;
      const message = error && error.message ? error.message : 'Qdrant request failed';
      const details = error && error.payload ? error.payload : undefined;
      return sendError(
        res,
        statusCode,
        details ? `${message}: ${JSON.stringify(details)}` : message
      );
    }
  };
}

module.exports = {
  createQdrantRoute
};
