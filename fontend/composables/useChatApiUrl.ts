export function useChatApiUrl(mode: "codex" | "qwen" = "codex") {
  const runtimeConfig = useRuntimeConfig();
  const publicConfig = runtimeConfig.public || {};
  const codexUrl = publicConfig.chatApiUrl || "/chat_bot/api";
  const qwenUrl = publicConfig.chatApiUrl || "/chat_bot/api";
  return mode === "qwen" ? qwenUrl : codexUrl;
}
