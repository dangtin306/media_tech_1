const fs = require('fs');
const path = require('path');
const { WebSocket } = require('ws');

const DEFAULT_GPU_WS_URL = 'wss://oc.hust.media/chatbot/gpu';
const API_LOG_DIR = path.join(__dirname, '..', 'api_log');
const WEBSERVICE_LOG_PATH = path.join(API_LOG_DIR, 'webservice.json');
const MAX_LOG_LINES = 20;
const clientState = {
  socket: null,
  wsUrl: '',
  device: 'gpu',
  connected: false,
};
const pendingResponses = new Map();

function normalizeString(value, fallback = '') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function normalizeMethod(value, fallback = 'POST') {
  const method = normalizeString(value, fallback).toUpperCase();
  return method || fallback;
}

function buildHeaders(device = 'gpu') {
  return {
    device,
    client: device,
    source: device,
    role: device,
    'x-client': device,
    'x-device': device,
    'x-openclaw-device': device,
    'x-openclaw-client': device,
  };
}

function resolveGpuWsUrl(config = {}) {
  return normalizeString(
    config.webservice_gpu_ws_url ||
      config.webservice_gpu_url ||
      config.gpu_ws_url ||
      config.gpu_websocket_url,
    DEFAULT_GPU_WS_URL,
  );
}

function writeWebserviceLog(entry) {
  try {
    fs.mkdirSync(API_LOG_DIR, { recursive: true });
    const nextLine = JSON.stringify(entry);
    let lines = [];

    if (fs.existsSync(WEBSERVICE_LOG_PATH)) {
      const current = fs.readFileSync(WEBSERVICE_LOG_PATH, 'utf8');
      lines = current
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    }

    lines.push(nextLine);
    if (lines.length > MAX_LOG_LINES) {
      lines = lines.slice(lines.length - MAX_LOG_LINES);
    }

    fs.writeFileSync(WEBSERVICE_LOG_PATH, `${lines.join('\n')}${lines.length ? '\n' : ''}`, 'utf8');
  } catch {
    // Ignore logging failures.
  }
}

function isGpuWebserviceLive() {
  return Boolean(clientState.socket && clientState.socket.readyState === WebSocket.OPEN && clientState.connected);
}

function getGpuWebserviceState() {
  return {
    connected: clientState.connected,
    device: clientState.device,
    wsUrl: clientState.wsUrl,
  };
}

function sendGpuWebserviceMessage(payload) {
  if (!isGpuWebserviceLive()) {
    const error = new Error('GPU websocket is not connected');
    error.code = 'GPU_WS_NOT_CONNECTED';
    throw error;
  }

  const text = JSON.stringify(payload);
  clientState.socket.send(text);
  return true;
}

function waitForGpuWebserviceResponse(requestId, timeoutMs = 80000) {
  return new Promise((resolve, reject) => {
    const normalizedRequestId = normalizeString(requestId);
    if (!normalizedRequestId) {
      reject(new Error('missing request_id'));
      return;
    }

    const timer = setTimeout(() => {
      pendingResponses.delete(normalizedRequestId);
      const error = new Error(`GPU websocket response timeout after ${timeoutMs}ms`);
      error.code = 'GPU_WS_TIMEOUT';
      reject(error);
    }, timeoutMs);

    if (typeof timer.unref === 'function') {
      timer.unref();
    }

    pendingResponses.set(normalizedRequestId, {
      resolve: (data) => {
        clearTimeout(timer);
        resolve(data);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });
  });
}

function rejectAllPendingResponses(error) {
  for (const [requestId, waiter] of pendingResponses.entries()) {
    pendingResponses.delete(requestId);
    waiter.reject(error);
  }
}

function toRequestBody(data) {
  if (data === undefined || data === null) {
    return '';
  }

  if (typeof data === 'string') {
    return data;
  }

  if (Buffer.isBuffer(data)) {
    return data.toString('utf8');
  }

  if (typeof data === 'object') {
    return JSON.stringify(data);
  }

  return String(data);
}

async function performHttpRequest(payload = {}) {
  const url = normalizeString(payload.url);
  if (!url) {
    throw new Error('missing url');
  }

  const method = normalizeMethod(payload.service || payload.method || 'POST');
  const headers = { ...(payload.headers && typeof payload.headers === 'object' ? payload.headers : {}) };
  const bodyText = toRequestBody(payload.data ?? payload.body ?? '');
  const requestInit = {
    method,
    headers,
  };

  if (method !== 'GET' && method !== 'HEAD') {
    if (bodyText) {
      if (!headers['content-type'] && !headers['Content-Type']) {
        headers['content-type'] = 'application/json';
      }
      requestInit.body = bodyText;
    }
  }

  const response = await fetch(url, requestInit);
  const responseText = await response.text();

  return {
    status: response.status,
    text: responseText,
  };
}

function startGpuWebserviceClient({ config = {}, wsUrl } = {}) {
  if (clientState.socket) {
    return {
      close() {
        if (clientState.socket) {
          try {
            clientState.socket.close();
          } catch {
            // Ignore.
          }
        }
      }
    };
  }

  const resolvedWsUrl = normalizeString(wsUrl, resolveGpuWsUrl(config));
  const device = 'gpu';
  const headers = buildHeaders(device);
  let socket = null;
  let reconnectTimer = null;
  let closedManually = false;

  const log = (message) => {
    console.log(`[webservice-gpu] ${message}`);
  };

  writeWebserviceLog({
    timestamp: new Date().toISOString(),
    event: 'starting',
    wsUrl: resolvedWsUrl,
    device,
  });

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const scheduleReconnect = () => {
    if (reconnectTimer) {
      return;
    }

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 30000);

    if (typeof reconnectTimer.unref === 'function') {
      reconnectTimer.unref();
    }
  };

  const sendJson = (data) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false;
    }

    socket.send(JSON.stringify(data));
    return true;
  };

  const handleApiCall = async (data) => {
    const requestId = normalizeString(data.request_id || data.requestId);
    writeWebserviceLog({
      timestamp: new Date().toISOString(),
      event: 'api_call',
      request_id: requestId,
      payload: data,
    });
    try {
      const result = await performHttpRequest(data);
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'api_response',
        request_id: requestId,
        status: result.status,
        response_text: result.text,
      });
      sendJson({
        device,
        url: data.url ?? '',
        data_response: result.text,
        category: 'api_response',
        service: data.service ?? data.method ?? 'POST',
        status: result.status,
        request_id: requestId,
      });
    } catch (error) {
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'api_error',
        request_id: requestId,
        error: error && error.message ? error.message : 'request failed',
      });
      sendJson({
        device,
        url: data.url ?? '',
        data_response: '',
        error: error && error.message ? error.message : 'request failed',
        category: 'api_response',
        service: data.service ?? data.method ?? 'POST',
        status: 500,
        request_id: requestId,
      });
    }
  };

  function connect() {
    clearReconnectTimer();

    socket = new WebSocket(resolvedWsUrl, {
      headers,
      perMessageDeflate: true,
    });
    clientState.socket = socket;
    clientState.wsUrl = resolvedWsUrl;
    clientState.device = device;
    clientState.connected = false;

    socket.on('open', () => {
      clientState.connected = true;
      log(`connected to ${resolvedWsUrl}`);
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'connected',
        wsUrl: resolvedWsUrl,
        device,
      });
    });

    socket.on('message', (raw) => {
      const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : String(raw || '');
      if (!text.trim()) {
        return;
      }

      let data;
      try {
        data = JSON.parse(text);
      } catch {
        return;
      }

      if (!data || typeof data !== 'object') {
        return;
      }

      if (data.category === 'api_response') {
        const responseRequestId = normalizeString(data.request_id || data.requestId);
        writeWebserviceLog({
          timestamp: new Date().toISOString(),
          event: 'response_in',
          request_id: responseRequestId,
          payload: data,
        });
        if (responseRequestId && pendingResponses.has(responseRequestId)) {
          const waiter = pendingResponses.get(responseRequestId);
          pendingResponses.delete(responseRequestId);
          waiter.resolve(data);
        }
        return;
      }

      if (data.category !== 'api_call') {
        return;
      }

      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'api_call_ignored',
        request_id: normalizeString(data.request_id || data.requestId),
        reason: 'start client keeps websocket alive only; ubuntu gpu worker handles api_call',
        payload: data,
      });
    });

    socket.on('close', () => {
      clientState.connected = false;
      clientState.socket = null;
      log('disconnected');
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'disconnected',
        wsUrl: resolvedWsUrl,
        device,
      });
      rejectAllPendingResponses(new Error('GPU websocket disconnected'));
      scheduleReconnect();
    });

    socket.on('error', (error) => {
      log(`error: ${error.message}`);
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'error',
        wsUrl: resolvedWsUrl,
        device,
        error: error && error.message ? error.message : 'unknown error',
      });
    });
  }

  connect();

  return {
    close() {
      closedManually = true;
      clearReconnectTimer();
      clientState.connected = false;
      if (socket) {
        try {
          socket.close();
        } catch {
          // Ignore.
        }
      }
    }
  };
}

module.exports = {
  getGpuWebserviceState,
  isGpuWebserviceLive,
  sendGpuWebserviceMessage,
  startGpuWebserviceClient,
  resolveGpuWsUrl,
  waitForGpuWebserviceResponse,
  writeWebserviceLog,
};
