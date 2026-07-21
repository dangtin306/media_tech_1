const fs = require("fs");
const path = require("path");
const { callUbuntuHealth, callUbuntuOpenClaw } = require("./qwen_process");
const {
  handleRagRequest,
  resolveUseRagFlag,
} = require("../rag/rag_process");

function parseJsonSafely(rawBody) {
  if (typeof rawBody !== "string" || !rawBody.trim()) return {};
  try {
    return JSON.parse(rawBody);
  } catch {
    return {};
  }
}

function normalizeOptionalObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function parseBooleanLike(value, fallback = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  }
  return fallback;
}

function writeQwenLog(entry) {
  try {
    const logPath = path.join(__dirname, "..", "api_log", "request_input.json");
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.writeFileSync(logPath, JSON.stringify(entry, null, 2), "utf8");
  } catch {
    // Ignore logging failures.
  }
}

function parseMaybeNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function parseMaybeBoolean(value, fallback = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  }
  if (typeof value === "number") return value !== 0;
  return fallback;
}

function normalizeMessageContent(content) {
  if (typeof content === "string") return content.trim();

  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part.trim();
        if (part && typeof part === "object") {
          if (typeof part.text === "string") return part.text.trim();
          if (typeof part.content === "string") return part.content.trim();
        }
        return "";
      })
      .filter(Boolean)
      .join(" ");
  }

  return "";
}

function buildAgentMessages(payload) {
  const messages = [];
  const systemParts = [];

  if (typeof payload.system_context === "string" && payload.system_context.trim()) {
    systemParts.push(payload.system_context.trim());
  }

  const scenarioText =
    typeof payload.scenario === "string" && payload.scenario.trim()
      ? payload.scenario.trim()
      : "";
  if (scenarioText) systemParts.push(`scenario: ${scenarioText}`);

  const userState = normalizeOptionalObject(payload.user_state);
  if (Object.keys(userState).length > 0) systemParts.push(`user_state: ${JSON.stringify(userState)}`);

  const metadata = normalizeOptionalObject(payload.metadata);
  if (Object.keys(metadata).length > 0) systemParts.push(`metadata: ${JSON.stringify(metadata)}`);

  if (systemParts.length > 0) {
    messages.push({ role: "system", content: systemParts.join("\n\n") });
  }

  const history = Array.isArray(payload.history) ? payload.history : [];
  for (const item of history) {
    if (!item) continue;
    if (typeof item === "string") {
      const content = item.trim();
      if (content) messages.push({ role: "user", content });
      continue;
    }
    if (typeof item !== "object") continue;

    const rawRole =
      typeof item.role === "string" && item.role.trim()
        ? item.role.trim().toLowerCase()
        : "user";
    const content = normalizeMessageContent(item.content);
    if (!content) continue;
    const role = ["user", "assistant", "tool"].includes(rawRole) ? rawRole : "user";
    messages.push({ role, content });
  }

  const userMessage =
    (typeof payload.user_message === "string" && payload.user_message.trim()
      ? payload.user_message.trim()
      : "") ||
    (typeof payload.message === "string" && payload.message.trim()
      ? payload.message.trim()
      : "") ||
    (typeof payload.content === "string" && payload.content.trim()
      ? payload.content.trim()
      : "");

  if (userMessage) messages.push({ role: "user", content: userMessage });
  if (messages.length === 0) messages.push({ role: "user", content: "xin chao" });
  return messages;
}

function buildQwenRequestPayload({ payload, config, modelName, userKey, sessionKey, useLora, normalizedOptions }) {
  const temperature = parseMaybeNumber(payload.temperature) ?? parseMaybeNumber(config.temperature) ?? 0.7;
  const maxTokens = parseMaybeNumber(payload.max_tokens) ?? parseMaybeNumber(config.max_tokens) ?? 256;
  const enableThinking = parseMaybeBoolean(
    payload.enable_thinking,
    parseMaybeBoolean(config.enable_thinking, false),
  );

  return {
    session_id: payload.session_id,
    turn_id: payload.turn_id,
    system_context: typeof payload.system_context === "string" ? payload.system_context : "",
    user_message: payload.user_message,
    history: Array.isArray(payload.history) ? payload.history : [],
    scenario: payload.scenario,
    user_state: normalizeOptionalObject(payload.user_state),
    runtime: normalizeOptionalObject(payload.runtime),
    options: normalizedOptions,
    metadata: normalizeOptionalObject(payload.metadata),
    model: modelName,
    user: userKey,
    session_key: sessionKey,
    messages: buildAgentMessages(payload),
    reasoning_effort: payload.reasoning_effort,
    temperature,
    max_tokens: maxTokens,
    top_p: payload.top_p,
    enable_thinking: enableThinking,
    use_lora: useLora,
    use_rag: resolveUseRagFlag(payload, false),
    rag_top_k: payload.rag_top_k,
    model_code: typeof payload.model_code === "string" ? payload.model_code : undefined,
    x_openclaw_model:
      typeof payload.x_openclaw_model === "string" ? payload.x_openclaw_model : undefined,
    ubuntu_model: typeof payload.ubuntu_model === "string" ? payload.ubuntu_model : undefined,
  };
}

function createUbuntuRoute({ sendJson, sendError, readBody, config = {} }) {
  return async function ubuntuRoute(req, res, url, rawBody = "") {
    if (!url.pathname.startsWith("/openclaw/")) return false;

    if (url.pathname === "/openclaw/health" || url.pathname === "/openclaw/v1/health") {
      if (req.method !== "GET") return sendError(res, 405, "Method not allowed");
      try {
        const health = await callUbuntuHealth(config);
        return sendJson(res, 200, { ok: true, route: url.pathname, brand: "openclaw", ubuntu: health });
      } catch (error) {
        return sendError(res, 502, error.message || "Ubuntu health check failed");
      }
    }

    if (url.pathname === "/openclaw/agent/health") {
      if (req.method !== "GET") return sendError(res, 405, "Method not allowed");
      return sendJson(res, 200, {
        ok: true,
        route: url.pathname,
        brand: "openclaw",
        runtime: "qwen-agent",
      });
    }

    if (url.pathname === "/openclaw/agent/level") {
      if (req.method !== "POST") return false;

      const payload = parseJsonSafely(rawBody || (await readBody(req)));
      writeQwenLog({
        timestamp: new Date().toISOString(),
        path: url.pathname,
        method: req.method,
        payload,
      });

      return false;
    }

    if (
      url.pathname !== "/openclaw/chat/completions" &&
      url.pathname !== "/openclaw/v1/chat/completions" &&
      url.pathname !== "/openclaw/agent/run"
    ) {
      return false;
    }

    if (req.method !== "POST") return sendError(res, 405, "Method not allowed");

    try {
      const payload = parseJsonSafely(rawBody || (await readBody(req)));
      if (!payload || typeof payload !== "object") {
        return sendError(res, 400, "JSON body must be an object");
      }

      const runtime = normalizeOptionalObject(payload.runtime);
      const modelName =
        (typeof runtime.model === "string" && runtime.model.trim()) ||
        (typeof payload.model === "string" && payload.model.trim()) ||
        (typeof config.model === "string" && config.model.trim()) ||
        (typeof config.ubuntu_model === "string" && config.ubuntu_model.trim()) ||
        (typeof config.x_openclaw_model === "string" && config.x_openclaw_model.trim()) ||
        "Qwen3.5-4B-V4";
      const userKey =
        (typeof payload.user === "string" && payload.user.trim()) ||
        (typeof payload.user_id === "string" && payload.user_id.trim()) ||
        (typeof payload.session_id === "string" && payload.session_id.trim()) ||
        "media_tech:request";
      const sessionKey =
        (typeof payload.session_key === "string" && payload.session_key.trim()) ||
        (typeof payload.session_id === "string" && payload.session_id.trim()) ||
        "agent:media_tech:ubuntu";
      const useLora = typeof payload.use_lora === "boolean" ? payload.use_lora : (typeof config.use_lora === "boolean" ? config.use_lora : true);
      const normalizedOptions = normalizeOptionalObject(payload.options);

      writeQwenLog({
        timestamp: new Date().toISOString(),
        path: url.pathname,
        method: req.method,
        payload,
      });

      const requestPayload = buildQwenRequestPayload({
        payload,
        config,
        modelName,
        userKey,
        sessionKey,
        useLora,
        normalizedOptions,
      });

      if (requestPayload.use_rag) {
        const ragResponse = await handleRagRequest({
          requestPayload,
          config,
          stage: "run",
        });
        if (ragResponse) {
          writeQwenLog({
            timestamp: new Date().toISOString(),
            path: url.pathname,
            method: req.method,
            payload,
            use_rag_handled: true,
          });
          return sendJson(res, 200, ragResponse);
        }
      }

      const result = await callUbuntuOpenClaw({ requestPayload, config, stage: "run" });
      return sendJson(res, 200, result);
    } catch (error) {
      return sendError(res, 500, error.message || "Qwen GPU websocket route failed");
    }
  };
}

module.exports = {
  buildAgentMessages,
  buildQwenRequestPayload,
  createUbuntuRoute,
};
