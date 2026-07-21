const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { runGpuWebserviceRequest } = require("./webservice_gpu_run");

const API_LOG_DIR = path.join(__dirname, "..", "api_log");
const QWEN_RUN_INPUT_PATH = path.join(API_LOG_DIR, "qwen_run_input.json");
const QWEN_RUN_OUTPUT_PATH = path.join(API_LOG_DIR, "qwen_run_output.json");
const QWEN_LEVEL_INPUT_PATH = path.join(API_LOG_DIR, "qwen_level_input.json");
const QWEN_LEVEL_OUTPUT_PATH = path.join(API_LOG_DIR, "qwen_level_output.json");

function normalizeBoolean(value, fallback = false) {
  if (typeof value === "boolean") return value;
  return fallback;
}

function isQwenWinMode(config = {}) {
  return normalizeBoolean(config.qwen_win, false);
}

function stripTrailingV1(url) {
  if (typeof url !== "string") return "";
  const trimmed = url.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/v1") ? trimmed.slice(0, -3) : trimmed;
}

function resolveLocalBaseUrl(config = {}) {
  const raw =
    typeof config.qwen_url === "string" && config.qwen_url.trim()
      ? config.qwen_url.trim()
      : typeof config.base_url === "string" && config.base_url.trim()
        ? config.base_url.trim()
        : "http://localhost:8006";
  return stripTrailingV1(raw) || "http://localhost:8006";
}

function normalizeModelCode(value) {
  if (typeof value !== "string") return "";
  return value.trim().toLowerCase();
}

function isUbuntuAgentRunModel(requestPayload = {}, config = {}) {
  const modelCode = normalizeModelCode(
    requestPayload.model_code ??
      requestPayload.ubuntu_model ??
      config.model_code ??
      config.ubuntu_model ??
      "",
  );
  return modelCode === "qwen-3.5/qwen-3.5-ubuntu";
}

function extractResponseText(response) {
  if (typeof response?.data_response === "string") {
    return response.data_response.trim();
  }

  if (response?.data_response && typeof response.data_response === "object") {
    return JSON.stringify(response.data_response);
  }

  if (typeof response?.output_text === "string") {
    return response.output_text.trim();
  }

  if (response?.output_text && typeof response.output_text === "object") {
    return JSON.stringify(response.output_text);
  }

  if (typeof response?.data === "string") {
    return response.data.trim();
  }

  if (response?.data && typeof response.data === "object") {
    return JSON.stringify(response.data);
  }

  return String(response || "").trim();
}

function buildRemoteUrl(baseUrl, pathname) {
  const url = new URL(baseUrl);
  url.pathname = pathname;
  url.search = "";
  url.hash = "";
  return url.toString();
}

function getStageLogPaths(stage = "run") {
  return stage === "level"
    ? {
        input: QWEN_LEVEL_INPUT_PATH,
        output: QWEN_LEVEL_OUTPUT_PATH,
      }
    : {
        input: QWEN_RUN_INPUT_PATH,
        output: QWEN_RUN_OUTPUT_PATH,
      };
}

function writeQwenOutput(entry, stage = "run") {
  try {
    fs.mkdirSync(API_LOG_DIR, { recursive: true });
    const { output } = getStageLogPaths(stage);
    fs.writeFileSync(output, JSON.stringify(entry, null, 2), "utf8");
  } catch {
    // Ignore logging failures.
  }
}

function writeQwenInput(entry, stage = "run") {
  try {
    fs.mkdirSync(API_LOG_DIR, { recursive: true });
    const { input } = getStageLogPaths(stage);
    fs.writeFileSync(input, JSON.stringify(entry, null, 2), "utf8");
  } catch {
    // Ignore logging failures.
  }
}

function runLocalPythonHttpCommand({ method, url, bodyBase64 = "" }) {
  const script = [
    "import base64",
    "import json",
    "import os",
    "import sys",
    "import urllib.request",
    "",
    'payload = json.loads(base64.b64decode(os.environ["BODY_B64"]).decode("utf-8")) if os.environ.get("BODY_B64") else None',
    'target_url = os.environ["TARGET_URL"]',
    'request = urllib.request.Request(target_url, data=(json.dumps(payload).encode("utf-8") if payload is not None else None), headers={"Content-Type": "application/json"}, method=os.environ.get("METHOD", "POST"))',
    "with urllib.request.urlopen(request, timeout=300) as response:",
    "    sys.stdout.write(response.read().decode(\"utf-8\"))",
  ].join("\n");

  return execFileSync("python", ["-c", script], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 60000,
    env: { ...process.env, METHOD: method, TARGET_URL: url, BODY_B64: bodyBase64 },
  });
}

async function verifyUbuntuSshConnection(config = {}) {
  if (isQwenWinMode(config)) {
    return true;
  }

  try {
    await runGpuWebserviceRequest({
      url:
        typeof config.ubuntu_ssh_health_url === "string" && config.ubuntu_ssh_health_url.trim()
          ? config.ubuntu_ssh_health_url.trim()
          : "http://127.0.0.1:8006/openclaw/agent/health",
      data: "",
      service: "get",
      timeoutMs: 40000,
    });
    return true;
  } catch {
    return false;
  }
}

async function callUbuntuOpenClaw({ requestPayload, config = {}, stage = "run" }) {
  const payloadText = JSON.stringify(requestPayload ?? {});
  const bodyBase64 = Buffer.from(payloadText, "utf8").toString("base64");
  const useAgentRunEndpoint = isUbuntuAgentRunModel(requestPayload, config);
  // Store exactly the JSON body sent to the target API.
  writeQwenInput(requestPayload, stage);

  if (isQwenWinMode(config)) {
    const localBaseUrl = resolveLocalBaseUrl(config);
    const remoteBaseUrl =
      typeof config.qwen_win_remote_url === "string" && config.qwen_win_remote_url.trim()
        ? config.qwen_win_remote_url.trim()
        : localBaseUrl;
    const remotePath =
      stage === "level"
        ? "/openclaw/agent/level"
        : useAgentRunEndpoint
          ? "/openclaw/agent/run"
          : "/chat/completions";
    const remoteUrl = buildRemoteUrl(remoteBaseUrl, remotePath);

    const stdout = runLocalPythonHttpCommand({
      method: "POST",
      url: remoteUrl,
      bodyBase64,
    });

    const text = typeof stdout === "string" ? stdout.trim() : String(stdout || "").trim();
    if (!text) throw new Error("Local HTTP command returned empty output");
    const parsed = JSON.parse(text);
    writeQwenOutput({
      timestamp: new Date().toISOString(),
      endpoint: remoteUrl,
      transport: "local_http",
      request: requestPayload,
      response_text: text,
      response: parsed,
    }, stage);
    return parsed;
  }

  const remoteBaseUrl =
    typeof config.ubuntu_ssh_remote_url === "string" && config.ubuntu_ssh_remote_url.trim()
      ? config.ubuntu_ssh_remote_url.trim()
      : "http://127.0.0.1:8005/chat/completions";
  const remotePath =
    stage === "level"
      ? "/openclaw/agent/level"
      : useAgentRunEndpoint
        ? "/openclaw/agent/run"
        : "/chat/completions";
  const remoteUrl = buildRemoteUrl(remoteBaseUrl, remotePath);
  const response = await runGpuWebserviceRequest({
    url: remoteUrl,
    data: requestPayload ?? "",
    service: "post",
    timeoutMs: 40000,
  });

  const text = extractResponseText(response);
  if (!text) throw new Error("GPU websocket command returned empty output");
  const parsed = JSON.parse(text);
  writeQwenOutput({
    timestamp: new Date().toISOString(),
    endpoint: remoteUrl,
    transport: "gpu_websocket",
    request: requestPayload,
    response_text: text,
    response: parsed,
  }, stage);
  return parsed;
}

async function callUbuntuHealth(config = {}) {
  if (isQwenWinMode(config)) {
    const localBaseUrl = resolveLocalBaseUrl(config);
    const healthUrl =
      typeof config.qwen_win_health_url === "string" && config.qwen_win_health_url.trim()
        ? config.qwen_win_health_url.trim()
        : `${localBaseUrl}/openclaw/agent/health`;
    const stdout = runLocalPythonHttpCommand({ method: "GET", url: healthUrl, bodyBase64: "" });
    const text = typeof stdout === "string" ? stdout.trim() : String(stdout || "").trim();
    if (!text) throw new Error("Local health check returned empty output");
    return JSON.parse(text);
  }

  const remoteUrl =
    typeof config.ubuntu_ssh_health_url === "string" && config.ubuntu_ssh_health_url.trim()
      ? config.ubuntu_ssh_health_url.trim()
      : "http://127.0.0.1:8006/openclaw/agent/health";

  const response = await runGpuWebserviceRequest({
    url: remoteUrl,
    data: "",
    service: "get",
    timeoutMs: 40000,
  });

  const text = extractResponseText(response);
  if (!text) throw new Error("GPU websocket health check returned empty output");
  return JSON.parse(text);
}

module.exports = {
  callUbuntuHealth,
  callUbuntuOpenClaw,
  isQwenWinMode,
  resolveLocalBaseUrl,
  runLocalPythonHttpCommand,
  verifyUbuntuSshConnection,
};
