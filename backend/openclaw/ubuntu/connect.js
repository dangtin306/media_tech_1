const { Client } = require("ssh2");

const states = new Map();

function debugLog(message) {
  if (process.env.SSH_WORKER_DEBUG === "1") {
    console.error(`[ssh2] ${message}`);
  }
}

function parseMaybeInt(value, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeString(value, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function getConnectionKey(config = {}) {
  const host = normalizeString(config.ubuntu_ssh_host, "n1.msk.cloreai.ru");
  const port = parseMaybeInt(config.ubuntu_ssh_port, 1331);
  const user = normalizeString(config.ubuntu_ssh_user, "root");
  const password = normalizeString(config.ubuntu_ssh_password, "");
  return `${host}:${port}:${user}:${password ? "pw" : "nopw"}`;
}

function cleanupState(state) {
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }

  state.busy = false;
  state.connected = false;
}

function rejectAll(state, error) {
  if (state.readyReject) {
    state.readyReject(error);
    state.readyReject = null;
    state.readyResolve = null;
  }

  if (state.current) {
    clearTimeout(state.current.timer);
    state.current.reject(error);
    state.current = null;
  }

  while (state.queue.length > 0) {
    const item = state.queue.shift();
    clearTimeout(item.timer);
    item.reject(error);
  }
}

function createState(config = {}) {
  const key = getConnectionKey(config);
  const host = normalizeString(config.ubuntu_ssh_host, "n1.msk.cloreai.ru");
  const port = parseMaybeInt(config.ubuntu_ssh_port, 1331);
  const user = normalizeString(config.ubuntu_ssh_user, "root");
  const password = normalizeString(config.ubuntu_ssh_password, "");

  const client = new Client();
  const state = {
    key,
    host,
    port,
    user,
    password,
    client,
    connected: false,
    busy: false,
    queue: [],
    current: null,
    readyPromise: null,
    readyResolve: null,
    readyReject: null,
    reconnectTimer: null,
  };

  state.readyPromise = new Promise((resolve, reject) => {
    state.readyResolve = resolve;
    state.readyReject = reject;
  });

  client.on("ready", () => {
    debugLog(`ready ${key}`);
    state.connected = true;
    if (state.readyResolve) {
      state.readyResolve(state);
      state.readyResolve = null;
      state.readyReject = null;
    }
    drainQueue(state);
  });

  client.on("close", () => {
    debugLog(`close ${key}`);
    const error = new Error("ssh connection closed");
    rejectAll(state, error);
    cleanupState(state);
    states.delete(key);
  });

  client.on("error", (error) => {
    debugLog(`error ${key} ${error.message}`);
    if (!state.connected && state.readyReject) {
      state.readyReject(error);
      state.readyResolve = null;
      state.readyReject = null;
      cleanupState(state);
      states.delete(key);
    }
  });

  client.connect({
    host,
    port,
    username: user,
    password,
    readyTimeout: 30000,
    keepaliveInterval: 100000,
    keepaliveCountMax: 3,
    tryKeyboard: false,
  });

  return state;
}

function getOrCreateState(config = {}) {
  const key = getConnectionKey(config);
  let state = states.get(key);

  if (state && state.connected) {
    if (state.reconnectTimer) {
      clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
    return state;
  }

  if (!state) {
    state = createState(config);
    states.set(key, state);
  }

  return state;
}

function scheduleReconnect(state) {
  if (state.reconnectTimer) {
    return;
  }

  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    try {
      state.client.end();
    } catch {
      // Ignore.
    }
    states.delete(state.key);
  }, 1000000);

  if (typeof state.reconnectTimer.unref === "function") {
    state.reconnectTimer.unref();
  }
}

function drainQueue(state) {
  if (!state.connected || state.busy || state.current || state.queue.length === 0) {
    return;
  }

  const item = state.queue.shift();
  state.current = item;
  state.busy = true;

  debugLog(`exec ${state.key} ${item.id}`);

  let stdout = "";
  let stderr = "";
  let finished = false;
  const timeoutTimer = setTimeout(() => {
    const error = new Error(`ssh2 command timeout after ${item.timeoutMs}ms`);
    try {
      state.client.end();
    } catch {
      // Ignore.
    }
    states.delete(state.key);
    finish(error);
  }, item.timeoutMs);

  item.timer = timeoutTimer;

  const finish = (error, result) => {
    if (finished) {
      return;
    }

    finished = true;
    clearTimeout(item.timer);
    state.busy = false;
    state.current = null;

    if (error) {
      item.reject(error);
    } else {
      item.resolve(result);
    }

    if (state.queue.length === 0) {
      scheduleReconnect(state);
    }

    process.nextTick(() => drainQueue(state));
  };

  state.client.exec(item.command, (err, stream) => {
    if (err) {
      try {
        state.client.end();
      } catch {
        // Ignore.
      }
      states.delete(state.key);
      finish(err);
      return;
    }

    stream.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });

    stream.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    stream.on("close", (code) => {
      debugLog(`close-stream ${state.key} ${item.id} code=${code}`);
      if (code !== 0) {
        const error = new Error(stderr || stdout || `ssh command failed with code ${code}`);
        error.exitCode = code;
        error.stdout = stdout;
        error.stderr = stderr;
        finish(error);
        return;
      }

      finish(null, { stdout, stderr, exit_code: code });
    });

    stream.on("error", (error) => {
      try {
        state.client.end();
      } catch {
        // Ignore.
      }
      states.delete(state.key);
      finish(error);
    });
  });

  if (typeof timeoutTimer.unref === "function") {
    timeoutTimer.unref();
  }
}

async function ensureState(config = {}) {
  const state = getOrCreateState(config);
  if (state.connected) {
    return state;
  }

  return state.readyPromise;
}

async function execRemoteCommandOnce(config = {}, remoteCommand, timeoutMs = 60000) {
  const state = await ensureState(config);
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return new Promise((resolve, reject) => {
    if (state.reconnectTimer) {
      clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }

    state.queue.push({
      id,
      command: remoteCommand,
      timeoutMs,
      resolve: (result) => resolve(typeof result.stdout === "string" ? result.stdout : ""),
      reject,
      timer: null,
    });

    drainQueue(state);
  });
}

async function execRemoteCommand(config = {}, remoteCommand, timeoutMs = 60000, maxAttempts = 3) {
  let lastError = null;

  for (let attempt = 1; attempt <= Math.max(1, maxAttempts); attempt += 1) {
    try {
      return await execRemoteCommandOnce(config, remoteCommand, timeoutMs);
    } catch (error) {
      lastError = error;
      debugLog(`attempt ${attempt} failed: ${error.message}`);
      await closeConnection(config);
      if (attempt >= Math.max(1, maxAttempts)) {
        break;
      }
    }
  }

  throw lastError || new Error("ssh command failed");
}

async function pingConnection(config = {}) {
  const output = await execRemoteCommand(config, "echo __SSH_OK__", 15000, 3);
  return String(output || "").includes("__SSH_OK__");
}

async function closeConnection(config = {}) {
  const key = getConnectionKey(config);
  const state = states.get(key);
  if (!state) {
    return;
  }

  try {
    state.client.end();
  } catch {
    // Ignore.
  }

  cleanupState(state);
  states.delete(key);
}

module.exports = {
  closeConnection,
  execRemoteCommand,
  pingConnection,
};
