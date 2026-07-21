const { WebSocket } = require('ws');
const {
  getGpuWebserviceState,
  isGpuWebserviceLive,
  writeWebserviceLog,
} = require('./webservice_gpu_start');

function normalizeString(value, fallback = '') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function normalizeService(value, fallback = 'post') {
  const service = normalizeString(value, fallback).toLowerCase();
  return service || fallback;
}

function buildRequesterHeaders() {
  return {
    device: 'backend',
    client: 'backend',
    source: 'backend',
    role: 'backend',
    'x-client': 'backend',
    'x-device': 'backend',
    'x-openclaw-device': 'backend',
    'x-openclaw-client': 'backend',
  };
}

async function runGpuWebserviceRequest({
  url,
  data = '',
  service = 'post',
  timeoutMs = 80000,
} = {}) {
  if (!isGpuWebserviceLive()) {
    const error = new Error('GPU websocket is not connected');
    error.code = 'GPU_WS_NOT_CONNECTED';
    throw error;
  }

  const gpuState = getGpuWebserviceState();
  const wsUrl = normalizeString(gpuState.wsUrl);
  if (!wsUrl) {
    const error = new Error('GPU websocket URL is missing');
    error.code = 'GPU_WS_URL_MISSING';
    throw error;
  }

  const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const payload = {
    device: 'gpu',
    url: normalizeString(url),
    data,
    category: 'api_call',
    service: normalizeService(service),
    request_id: requestId,
  };

  writeWebserviceLog({
    timestamp: new Date().toISOString(),
    event: 'request_out',
    request_id: requestId,
    payload,
  });

  return new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl, {
      headers: buildRequesterHeaders(),
      perMessageDeflate: true,
    });

    let settled = false;
    const finish = (handler, value) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      try {
        socket.close();
      } catch {
        // Ignore.
      }
      handler(value);
    };

    const timer = setTimeout(() => {
      const error = new Error(`GPU websocket response timeout after ${timeoutMs}ms`);
      error.code = 'GPU_WS_TIMEOUT';
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'request_timeout',
        request_id: requestId,
        timeoutMs,
      });
      finish(reject, error);
    }, timeoutMs);

    if (typeof timer.unref === 'function') {
      timer.unref();
    }

    socket.on('open', () => {
      socket.send(JSON.stringify(payload));
    });

    socket.on('message', (raw) => {
      const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : String(raw || '');
      if (!text.trim()) {
        return;
      }

      let message;
      try {
        message = JSON.parse(text);
      } catch {
        return;
      }

      if (!message || typeof message !== 'object') {
        return;
      }

      if (message.category === 'api_run') {
        writeWebserviceLog({
          timestamp: new Date().toISOString(),
          event: 'request_ack',
          request_id: requestId,
          payload: message,
        });
        return;
      }

      if (message.category !== 'api_response') {
        return;
      }

      if (normalizeString(message.request_id) !== requestId) {
        return;
      }

      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'response_in',
        request_id: requestId,
        payload: message,
      });
      finish(resolve, message);
    });

    socket.on('error', (error) => {
      writeWebserviceLog({
        timestamp: new Date().toISOString(),
        event: 'request_error',
        request_id: requestId,
        error: error && error.message ? error.message : 'unknown error',
      });
      finish(reject, error);
    });

    socket.on('close', () => {
      if (!settled) {
        const error = new Error('GPU websocket request socket closed before response');
        error.code = 'GPU_WS_REQUEST_CLOSED';
        finish(reject, error);
      }
    });
  });
}

module.exports = {
  runGpuWebserviceRequest,
};
