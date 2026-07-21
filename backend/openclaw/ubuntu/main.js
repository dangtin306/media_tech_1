const { execFileSync, spawnSync } = require('child_process');

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

function parseMaybeInt(value, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeBoolean(value, fallback = false) {
  if (typeof value === 'boolean') {
    return value;
  }

  return fallback;
}

function runSshCommandWithParamiko({ host, port, user, remoteCommand, password }) {
  const script = [
    'import base64',
    'import paramiko',
    'import sys',
    '',
    'host = sys.argv[1]',
    'port = int(sys.argv[2])',
    'user = sys.argv[3]',
    'password = sys.argv[4]',
    'command = base64.b64decode(sys.argv[5]).decode("utf-8")',
    'client = paramiko.SSHClient()',
    'client.set_missing_host_key_policy(paramiko.AutoAddPolicy())',
    'client.connect(hostname=host, port=port, username=user, password=password, look_for_keys=False, allow_agent=False, timeout=15, banner_timeout=15, auth_timeout=15)',
    'stdin, stdout, stderr = client.exec_command(command, timeout=300)',
    'exit_code = stdout.channel.recv_exit_status()',
    'out = stdout.read().decode("utf-8", errors="replace")',
    'err = stderr.read().decode("utf-8", errors="replace")',
    'client.close()',
    'if out:',
    '    sys.stdout.write(out)',
    'if exit_code != 0:',
    '    if err:',
    '        sys.stderr.write(err)',
    '    sys.exit(exit_code)',
    'if err and not out:',
    '    sys.stdout.write(err)'
  ].join('\n');

  return execFileSync('python', [
    '-c',
    script,
    host,
    String(port),
    user,
    password,
    Buffer.from(remoteCommand, 'utf8').toString('base64')
  ], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 20000
  });
}

function buildRemotePythonCommand(remoteUrl, bodyBase64) {
  return [
    `BODY_B64='${bodyBase64}' TARGET_URL='${remoteUrl}' python3 - <<'PY'`,
    'import base64',
    'import json',
    'import os',
    'import sys',
    'import urllib.error',
    'import urllib.request',
    '',
    'payload = json.loads(base64.b64decode(os.environ["BODY_B64"]).decode("utf-8"))',
    'target_url = os.environ["TARGET_URL"]',
    'data = json.dumps(payload).encode("utf-8")',
    'request = urllib.request.Request(target_url, data=data, headers={"Content-Type": "application/json"})',
    'try:',
    '    with urllib.request.urlopen(request, timeout=300) as response:',
    '        sys.stdout.write(response.read().decode("utf-8"))',
    'except urllib.error.HTTPError as exc:',
    '    sys.stdout.write(exc.read().decode("utf-8"))',
    '    raise',
    'PY'
  ].join('\n');
}

function runSshCommand({ host, port, user, remoteCommand, password }) {
  if (password && process.platform === 'win32') {
    return runSshCommandWithParamiko({ host, port, user, remoteCommand, password });
  }

  const hasSshPass = spawnSync('sshpass', ['-V'], { encoding: 'utf8' }).status === 0;
  const sshArgs = [
    '-p',
    String(port),
    '-o',
    'BatchMode=yes',
    '-o',
    'StrictHostKeyChecking=no',
    '-o',
    'UserKnownHostsFile=/dev/null',
    `${user}@${host}`,
    remoteCommand
  ];

  if (password && hasSshPass) {
    return execFileSync('sshpass', ['-p', password, 'ssh', ...sshArgs], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 15000
    });
  }

  if (password && !hasSshPass) {
    throw new Error('sshpass is required for password-based SSH, or configure SSH key auth');
  }

  return execFileSync('ssh', sshArgs, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 15000
  });
}

function verifyUbuntuSshConnection(config = {}) {
  const host = typeof config.ubuntu_ssh_host === 'string' && config.ubuntu_ssh_host.trim()
    ? config.ubuntu_ssh_host.trim()
    : 'n1.msk.cloreai.ru';
  const port = parseMaybeInt(config.ubuntu_ssh_port, 1331);
  const user = typeof config.ubuntu_ssh_user === 'string' && config.ubuntu_ssh_user.trim()
    ? config.ubuntu_ssh_user.trim()
    : 'root';
  const password = typeof config.ubuntu_ssh_password === 'string' && config.ubuntu_ssh_password.trim()
    ? config.ubuntu_ssh_password.trim()
    : '';

  const stdout = runSshCommand({
    host,
    port,
    user,
    remoteCommand: 'echo __SSH_OK__',
    password
  });
  return String(stdout || '').includes('__SSH_OK__');
}

function callUbuntuOpenClaw({ payload, config, modelName, userKey, sessionKey }) {
  const host = typeof config.ubuntu_ssh_host === 'string' && config.ubuntu_ssh_host.trim()
    ? config.ubuntu_ssh_host.trim()
    : 'n1.msk.cloreai.ru';
  const port = parseMaybeInt(config.ubuntu_ssh_port, 1331);
  const user = typeof config.ubuntu_ssh_user === 'string' && config.ubuntu_ssh_user.trim()
    ? config.ubuntu_ssh_user.trim()
    : 'root';
  const remoteUrl = typeof config.ubuntu_ssh_remote_url === 'string' && config.ubuntu_ssh_remote_url.trim()
    ? config.ubuntu_ssh_remote_url.trim()
    : 'http://127.0.0.1:8005/chat/completions';
  const password = typeof config.ubuntu_ssh_password === 'string' && config.ubuntu_ssh_password.trim()
    ? config.ubuntu_ssh_password.trim()
    : '';
  const useLora = normalizeBoolean(payload.use_lora, normalizeBoolean(config.use_lora, false));

  const requestPayload = {
    model: modelName,
    user: userKey,
    messages: payload.messages,
    reasoning_effort: payload.reasoning_effort,
    temperature: payload.temperature,
    max_tokens: payload.max_tokens,
    top_p: payload.top_p,
    enable_thinking: payload.enable_thinking,
    use_lora: useLora,
    use_rag: payload.use_rag,
    rag_top_k: payload.rag_top_k
  };

  const bodyBase64 = Buffer.from(JSON.stringify(requestPayload), 'utf8').toString('base64');
  const remoteCommand = buildRemotePythonCommand(remoteUrl, bodyBase64);
  const stdout = runSshCommand({
    host,
    port,
    user,
    remoteCommand,
    password
  });

  const text = typeof stdout === 'string' ? stdout.trim() : String(stdout || '').trim();
  if (!text) {
    throw new Error('Ubuntu SSH command returned empty output');
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Ubuntu SSH command returned invalid JSON: ${text.slice(0, 500)}`);
  }
}

function callUbuntuHealth(config = {}) {
  const host = typeof config.ubuntu_ssh_host === 'string' && config.ubuntu_ssh_host.trim()
    ? config.ubuntu_ssh_host.trim()
    : 'n1.msk.cloreai.ru';
  const port = parseMaybeInt(config.ubuntu_ssh_port, 1331);
  const user = typeof config.ubuntu_ssh_user === 'string' && config.ubuntu_ssh_user.trim()
    ? config.ubuntu_ssh_user.trim()
    : 'root';
  const password = typeof config.ubuntu_ssh_password === 'string' && config.ubuntu_ssh_password.trim()
    ? config.ubuntu_ssh_password.trim()
    : '';

  const remoteCommand = "python3 -c 'import sys,urllib.request; sys.stdout.write(urllib.request.urlopen(\"http://127.0.0.1:8005/health\", timeout=15).read().decode(\"utf-8\"))'";

  const stdout = runSshCommand({
    host,
    port,
    user,
    remoteCommand,
    password
  });

  const text = typeof stdout === 'string' ? stdout.trim() : String(stdout || '').trim();
  if (!text) {
    throw new Error('Ubuntu health check returned empty output');
  }

  try {
    return JSON.parse(text);
  } catch {
    return {
      ok: true,
      raw: text
    };
  }
}

function createUbuntuRoute({ sendJson, sendError, readBody, config = {} }) {
  const supportedPaths = new Set([
    '/openclaw/health',
    '/openclaw/v1/health',
    '/openclaw/chat/completions',
    '/openclaw/v1/chat/completions'
  ]);

  return async function ubuntuRoute(req, res, url, rawBody = '') {
    if (!url.pathname.startsWith('/openclaw/')) {
      return false;
    }

    if (req.method !== 'GET' && req.method !== 'POST') {
      return false;
    }

    if (!supportedPaths.has(url.pathname)) {
      return false;
    }

    if (req.method === 'GET' && (url.pathname === '/openclaw/health' || url.pathname === '/openclaw/v1/health')) {
      try {
        const result = callUbuntuHealth({});
        return sendJson(res, 200, {
          ok: true,
          route: url.pathname,
          brand: 'openclaw',
          ubuntu: result
        });
      } catch (error) {
        return sendError(res, 502, error.message || 'Ubuntu health check failed');
      }
    }

    try {
      const payload = req.method === 'GET'
        ? parseJsonSafely(url.searchParams.get('body') || '')
        : parseJsonSafely(rawBody || await readBody(req));

      if (!payload || typeof payload !== 'object') {
        return sendError(res, 400, 'JSON body must be an object');
      }

      const modelName = typeof payload.model === 'string' && payload.model.trim()
        ? payload.model.trim()
        : typeof config.model === 'string' && config.model.trim()
          ? config.model.trim()
          : typeof config.ubuntu_model === 'string' && config.ubuntu_model.trim()
            ? config.ubuntu_model.trim()
            : typeof config.x_openclaw_model === 'string' && config.x_openclaw_model.trim()
              ? config.x_openclaw_model.trim()
              : 'Qwen3.5-4B-V4';
      const userKey = typeof payload.user === 'string' && payload.user.trim()
        ? payload.user.trim()
        : 'media_tech:request';
      const sessionKey = typeof payload.session_key === 'string' && payload.session_key.trim()
        ? payload.session_key.trim()
        : 'agent:media_tech:ubuntu';
      const result = callUbuntuOpenClaw({
        payload,
        config,
        modelName,
        userKey,
        sessionKey
      });

      return sendJson(res, 200, result);
    } catch (error) {
      return sendError(res, 500, error.message || 'Ubuntu SSH route failed');
    }
  };
}

module.exports = {
  callUbuntuOpenClaw,
  createUbuntuRoute,
  verifyUbuntuSshConnection
};
