const {
  buildServiceSearchResponse,
  getServiceSearchFlag,
  parseBooleanLike,
  shouldShortCircuitServiceSearch,
} = require("./service_search");
const { callUbuntuOpenClaw } = require("../ubuntu/qwen_process");

function resolveUseRagFlag(payload, fallback = false) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return fallback;
  }

  return parseBooleanLike(payload.use_rag, getServiceSearchFlag(payload) || fallback);
}

function buildRagResponseIfNeeded(requestPayload) {
  if (!shouldShortCircuitServiceSearch(requestPayload)) {
    return null;
  }

  return buildServiceSearchResponse(requestPayload);
}

async function handleRagRequest({ requestPayload, config = {}, stage = "run" } = {}) {
  if (!requestPayload || typeof requestPayload !== "object") {
    return null;
  }

  if (!parseBooleanLike(requestPayload.use_rag, false)) {
    return null;
  }

  const shortCircuitResponse = buildRagResponseIfNeeded(requestPayload);
  if (shortCircuitResponse) {
    return shortCircuitResponse;
  }

  return callUbuntuOpenClaw({ requestPayload, config, stage });
}

module.exports = {
  buildRagResponseIfNeeded,
  buildServiceSearchResponse,
  handleRagRequest,
  getServiceSearchFlag,
  parseBooleanLike,
  resolveUseRagFlag,
  shouldShortCircuitServiceSearch,
};
