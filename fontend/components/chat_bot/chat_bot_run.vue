<script setup>
const props = defineProps({
  botMode: {
    type: String,
    default: "codex",
  },
  requestKey: {
    type: Number,
    default: 0,
  },
  userMessage: {
    type: String,
    default: "",
  },
  chatToken: {
    type: [String, Number],
    default: "",
  },
  chatUserId: {
    type: [String, Number],
    default: "",
  },
});

const emit = defineEmits(["reply", "error", "loading"]);
const loading = ref(false);
const isQwen = computed(() => props.botMode === "qwen");
const chatApiUrl = useChatApiUrl(props.botMode);
const runtimeConfig = useRuntimeConfig();
const qwenModel = computed(() => runtimeConfig.public?.qwenModel || "Qwen3.5-4B-V4");
const chatBrand = "openclaw";

function looksLikeHtml(text) {
  const value = String(text || "").trim().toLowerCase();
  return value.startsWith("<!doctype") || value.startsWith("<html") || value.includes("</html>") || value.includes("__nuxt__");
}

function buildIdentityBody() {
  if (String(props.chatUserId || "").trim()) {
    return { user_id: props.chatUserId };
  }

  return { chat_token: props.chatToken || undefined };
}

function extractQwenReply(response) {
  return (
    response?.response ||
    response?.output_text ||
    response?.choices?.[0]?.message?.content ||
    response?.answer ||
    response?.reply ||
    response?.message ||
    ""
  );
}

async function processMessage(message) {
  if (!message.trim()) {
    return;
  }

  loading.value = true;
  emit("loading", true);

  try {
    let replyText = "";

    if (chatApiUrl) {
      const response = await $fetch(chatApiUrl, {
        method: "POST",
        body: {
          brand: chatBrand,
          model: isQwen.value ? qwenModel.value : undefined,
          enable_thinking: false,
          use_lora: isQwen.value ? true : undefined,
          use_rag: false,
          max_new_tokens: 256,
          temperature: 0.7,
          top_p: 0.9,
          ...buildIdentityBody(),
          message,
        },
      });

      if (typeof response === "string") {
        replyText = looksLikeHtml(response) ? "" : response;
      } else {
        replyText = response?.answer || response?.reply || response?.message || extractQwenReply(response);
      }
    }

    if (!replyText) {
      replyText = `Mình đã nhận: ${message}`;
    }

    emit("reply", replyText);
  } catch (error) {
    emit("error", error);
  } finally {
    loading.value = false;
    emit("loading", false);
  }
}

watch(
  () => [props.requestKey, props.userMessage],
  ([currentKey, currentMessage], [previousKey] = []) => {
    if (currentKey === previousKey) {
      return;
    }

    processMessage(currentMessage);
  }
);
</script>

<template></template>
