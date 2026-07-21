const crypto = require("crypto");

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

function getServiceSearchFlag(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return false;
  }

  return parseBooleanLike(
    payload["service-search"] ?? payload.service_search ?? payload.serviceSearch,
    false,
  );
}

function shouldShortCircuitServiceSearch(payload) {
  return getServiceSearchFlag(payload);
}

function buildServiceSearchResponse(payload = {}) {
  const now = Math.floor(Date.now() / 1000);
  const model =
    (typeof payload.model === "string" && payload.model.trim()) || "Qwen3.5-4B-V3";

  return {
    choices: [
      {
        finish_reason: "stop",
        index: 0,
        message: {
          content: "hello world",
          role: "assistant",
        },
      },
    ],
    created: now,
    enable_thinking: false,
    id: `chatcmpl-${crypto.randomUUID().replace(/-/g, "")}`,
    model,
    object: "chat.completion",
    output_text: "hello world",
    rag_top_k: Number.isFinite(Number(payload.rag_top_k)) ? Number(payload.rag_top_k) : 4,
    retrieved_context: "",
    usage: {
      completion_tokens: 0,
      prompt_tokens: 0,
      total_tokens: 0,
    },
    use_lora: false,
    use_rag: false,
  };
}

module.exports = {
  buildServiceSearchResponse,
  getServiceSearchFlag,
  parseBooleanLike,
  shouldShortCircuitServiceSearch,
};
