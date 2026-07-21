const fs = require("fs");
const path = require("path");
const { callUbuntuOpenClaw } = require("./qwen_process");
const { buildQwenRequestPayload } = require("./qwen");

const API_LOG_DIR = path.join(__dirname, "..", "api_log");
const QWEN_LEVEL_INPUT_PATH = path.join(API_LOG_DIR, "qwen_level_input.json");
const QWEN_LEVEL_OUTPUT_PATH = path.join(API_LOG_DIR, "qwen_level_output.json");

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

function writeLevelLog(filePath, entry) {
  try {
    fs.mkdirSync(API_LOG_DIR, { recursive: true });
    fs.writeFileSync(filePath, JSON.stringify(entry, null, 2), "utf8");
  } catch {
    // Ignore logging failures.
  }
}

function buildLevelRequestPayload(payload, config) {
  const incomingSystemContext =
    (typeof payload.system_context === "string" && payload.system_context.trim()) ||
    (typeof payload.systemContext === "string" && payload.systemContext.trim());
  const levelSystemContext = incomingSystemContext || [
    "Bạn là bộ phân loại level cho hệ thống.",
    "Chỉ được trả về đúng MỘT ký tự số: 1, 2, 3 hoặc 4.",
    "Không giải thích.",
    "Không markdown.",
    "Không thêm dấu câu.",
    "Không thêm chữ khác ngoài số.",
  ].join(" ");
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
  const useLora = false;
  const normalizedOptions = normalizeOptionalObject(payload.options);
  const userMessage =
    (typeof payload.user_message === "string" && payload.user_message.trim()
      ? payload.user_message.trim()
      : "") ||
    (typeof payload.message === "string" && payload.message.trim()
      ? payload.message.trim()
      : "") ||
    (typeof payload.content === "string" && payload.content.trim()
      ? payload.content.trim()
      : "") ||
    "hello world";

  return buildQwenRequestPayload({
    payload: {
      ...payload,
      system_context: levelSystemContext,
      user_message: userMessage,
      enable_thinking: false,
      scenario:
        typeof payload.scenario === "string" && payload.scenario.trim()
          ? payload.scenario.trim()
          : "customer_consulting",
      history: Array.isArray(payload.history) ? payload.history : [],
      user_state: normalizeOptionalObject(payload.user_state),
      runtime,
      options: normalizedOptions,
      metadata: normalizeOptionalObject(payload.metadata),
      model_code: typeof payload.model_code === "string" ? payload.model_code : undefined,
    },
    config,
    modelName,
    userKey,
    sessionKey,
    useLora,
    normalizedOptions,
  });
}

function createLevelRoute({ sendJson, sendError, readBody, config = {} }) {
  return async function levelRoute(req, res, url, rawBody = "") {
    if (url.pathname !== "/openclaw/agent/level") return false;
    if (req.method !== "POST") return sendError(res, 405, "Method not allowed");

    try {
      const payload = parseJsonSafely(rawBody || (await readBody(req)));
      if (!payload || typeof payload !== "object") {
        return sendError(res, 400, "JSON body must be an object");
      }

      const requestPayload = buildLevelRequestPayload(payload, config);
      // Keep the input log byte-for-byte equivalent in structure to the API body.
      writeLevelLog(QWEN_LEVEL_INPUT_PATH, requestPayload);
      const result = await callUbuntuOpenClaw({ requestPayload, config, stage: "level" });
      writeLevelLog(QWEN_LEVEL_OUTPUT_PATH, {
        timestamp: new Date().toISOString(),
        request: requestPayload,
        response: result,
      });
      return sendJson(res, 200, result);
    } catch (error) {
      return sendError(res, 500, error.message || "Ubuntu level route failed");
    }
  };
}

module.exports = {
  createLevelRoute,
};
