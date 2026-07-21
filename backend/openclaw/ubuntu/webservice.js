const { WebSocketServer } = require('ws');

const WEB_SERVICE_PATHS = new Set(['/chatbot/gpu', '/chatbot/qwen']);
const ALLOWED_SENDER_ROLES = new Set(['backend', 'gpu', 'windows', 'win']);

function parseJsonMessage(payload) {
  if (typeof payload === 'string') {
    try {
      return JSON.parse(payload);
    } catch {
      return null;
    }
  }

  if (Buffer.isBuffer(payload)) {
    try {
      return JSON.parse(payload.toString('utf8'));
    } catch {
      return null;
    }
  }

  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    return payload;
  }

  return null;
}

function normalizeRole(value) {
  return String(value || '').trim().toLowerCase();
}

function debugWebservice(message, extra = {}) {
  try {
    console.log(`[webservice] ${message}${Object.keys(extra).length ? ` ${JSON.stringify(extra)}` : ''}`);
  } catch {
    // Ignore debug logging failures.
  }
}

function countMatchingSockets(wss, predicate) {
  let count = 0;
  for (const targetSocket of wss.clients) {
    if (predicate(targetSocket)) {
      count += 1;
    }
  }
  return count;
}

function createWebservice({ server, sendJson, sendError } = {}) {
  const wss = new WebSocketServer({ noServer: true });
  const pendingRequests = new Map();

  wss.on('connection', (socket, request) => {
    const requestUrl = new URL(request.url, 'http://localhost');
    const clientKind = String(
      request.headers.client ||
      request.headers['x-client'] ||
      request.headers['x-openclaw-client'] ||
      request.headers.role ||
      request.headers.source ||
      ''
    ).trim();
    const headerDevice = String(
      request.headers.device ||
      request.headers['x-device'] ||
      request.headers['x-openclaw-device'] ||
      ''
    ).trim();
    const senderRole = normalizeRole(clientKind || headerDevice || '');

    socket.clientKind = clientKind;
    socket.device = headerDevice;
    const message = JSON.stringify({
      ok: true,
      route: requestUrl.pathname,
      message: 'hello world'
    });

    socket.send(message);

    socket.on('message', (payload) => {
      const data = parseJsonMessage(payload);

      if (data && data.category === 'api_response') {
        const responseRequestId = String(data.request_id || data.requestId || '').trim();
        const responsePayload = {
          device: String(data.device || 'backend').trim() || 'backend',
          url: data.url ?? '',
          data_response: data.data_response ?? data.data ?? '',
          category: 'api_response',
          service: data.service ?? '',
          status: data.status ?? 200,
          request_id: responseRequestId,
        };

        let delivered = false;
        let deliveryReason = 'not_sent';
        const pendingSocket = responseRequestId ? pendingRequests.get(responseRequestId) : null;
        const backendReceivers = countMatchingSockets(
          wss,
          (targetSocket) =>
            targetSocket !== socket &&
            String(targetSocket.device || '').trim() === 'backend' &&
            targetSocket.readyState === 1,
        );

        debugWebservice('api_response inbound', {
          request_id: responseRequestId,
          pending: Boolean(pendingSocket),
          pending_state: pendingSocket ? pendingSocket.readyState : null,
          backend_receivers: backendReceivers,
          from_device: String(socket.device || '').trim() || null,
        });

        if (responseRequestId && pendingRequests.has(responseRequestId)) {
          const targetSocket = pendingRequests.get(responseRequestId);
          if (targetSocket && targetSocket.readyState === 1) {
            targetSocket.send(JSON.stringify(responsePayload));
            delivered = true;
            deliveryReason = 'delivered_to_pending_socket';
          } else {
            deliveryReason = 'pending_socket_not_open';
          }
          pendingRequests.delete(responseRequestId);
        }

        if (!delivered) {
          let fallbackDelivered = false;
          for (const targetSocket of wss.clients) {
            if (targetSocket === socket) {
              continue;
            }

            if (String(targetSocket.device || '').trim() !== 'backend') {
              continue;
            }

            if (targetSocket.readyState !== 1) {
              continue;
            }

            targetSocket.send(JSON.stringify(responsePayload));
            delivered = true;
            fallbackDelivered = true;
            deliveryReason = 'delivered_to_backend_fallback';
            break;
          }

          if (!fallbackDelivered && deliveryReason === 'not_sent') {
            deliveryReason = backendReceivers > 0 ? 'backend_fallback_failed' : 'no_backend_receiver';
          }
        }

        debugWebservice('api_response relay result', {
          request_id: responseRequestId,
          status: delivered ? 'sent' : 'not_sent',
          reason: deliveryReason,
          pending_exists: Boolean(pendingSocket),
          backend_receivers: backendReceivers,
        });

        socket.send(JSON.stringify({
          status: delivered ? 'sent' : 'not_sent',
          category: 'api_response',
          request_id: responseRequestId,
          reason: delivered ? 'delivered' : deliveryReason,
          relayCount: delivered ? 1 : 0,
        }));
        return;
      }

      if (!ALLOWED_SENDER_ROLES.has(senderRole)) {
        socket.send(JSON.stringify({
          status: 'not_sent',
          reason: 'backend, gpu, windows, or win header required',
          relayCount: 0
        }));
        return;
      }

      if (!data || data.category !== 'api_call') {
        socket.send(JSON.stringify({
          status: 'not_sent',
          reason: 'category not found',
          relayCount: 0
        }));
        return;
      }

      const device = String(data.device || socket.device || '').trim();
      if (!device) {
        socket.send(JSON.stringify({
          status: 'not_sent',
          reason: 'missing device in message body',
          relayCount: 0
        }));
        return;
      }

      const requestId = String(data.request_id || data.requestId || `${Date.now()}-${Math.random().toString(16).slice(2)}`).trim();
      pendingRequests.set(requestId, socket);

      const outbound = JSON.stringify({
        device,
        url: data.url ?? '',
        data: data.data ?? '',
        category: data.category,
        service: data.service ?? '',
        request_id: requestId
      });

      let relayCount = 0;
      const matchingReceivers = countMatchingSockets(
        wss,
        (targetSocket) =>
          targetSocket !== socket &&
          String(targetSocket.device || '').trim() === device &&
          targetSocket.readyState === 1,
      );

      for (const targetSocket of wss.clients) {
        if (targetSocket === socket) {
          continue;
        }

        if (String(targetSocket.device || '').trim() !== device) {
          continue;
        }

        if (targetSocket.readyState !== 1) {
          continue;
        }

        targetSocket.send(outbound);
        relayCount += 1;
      }

      debugWebservice('api_call relay result', {
        request_id: requestId,
        device,
        relayCount,
        matching_receivers: matchingReceivers,
      });

      socket.send(JSON.stringify({
        device,
        url: data.url ?? '',
        data: data.data ?? '',
        category: 'api_run',
        service: data.service ?? '',
        request_id: requestId,
        status: relayCount > 0 ? 'sent' : 'not_sent',
        reason: relayCount > 0 ? 'delivered' : 'no_matching_device_receiver',
        relayCount
      }));
    });

    socket.isAlive = true;
    socket.on('pong', () => {
      socket.isAlive = true;
    });

    socket.on('error', () => {
      // Ignore websocket errors; connection will close naturally.
    });

    socket.on('close', () => {
      for (const [requestId, targetSocket] of pendingRequests.entries()) {
        if (targetSocket === socket) {
          pendingRequests.delete(requestId);
        }
      }
    });
  });

  const heartbeatInterval = setInterval(() => {
    wss.clients.forEach((socket) => {
      if (socket.isAlive === false) {
        socket.terminate();
        return;
      }

      socket.isAlive = false;
      try {
        socket.ping();
      } catch {
        socket.terminate();
      }
    });
  }, 25000);

  if (typeof heartbeatInterval.unref === 'function') {
    heartbeatInterval.unref();
  }

  wss.on('close', () => {
    clearInterval(heartbeatInterval);
  });

  if (server && typeof server.on === 'function') {
    server.on('upgrade', (request, socket, head) => {
      try {
        const url = new URL(request.url, 'http://localhost');
        if (!WEB_SERVICE_PATHS.has(url.pathname)) {
          return;
        }

        wss.handleUpgrade(request, socket, head, (ws) => {
          wss.emit('connection', ws, request);
        });
      } catch {
        socket.destroy();
      }
    });
  }

  return async function webserviceRoute(req, res, url) {
    if (!WEB_SERVICE_PATHS.has(url.pathname)) {
      return false;
    }

    if (req.method !== 'GET') {
      if (typeof sendError === 'function') {
        return sendError(res, 405, 'Method not allowed');
      }
      return true;
    }

    if (typeof sendJson === 'function') {
      return sendJson(res, 200, {
        ok: true,
        route: url.pathname,
        message: 'hello world',
        websocket: true
      });
    }

    return true;
  };
}

module.exports = {
  createWebservice
};
