<script setup>
const props = defineProps({
  botMode: {
    type: String,
    default: "codex",
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

const emit = defineEmits(["close", "reset"]);

const isQwen = computed(() => props.botMode === "qwen");
const chatTitle = computed(() => (isQwen.value ? "Qwen3.5-4B-V4" : "TuongTac.tv"));
const chatSubtitle = computed(() => (isQwen.value ? "Qwen route" : "Customer support"));
const defaultMessages = computed(() => [
  {
    id: 1,
    role: "bot",
    text: isQwen.value
      ? "Xin chào, tôi là Qwen3.5-4B-V4."
      : "Xin chào, em là trợ lý AI của TuongTac.tv",
  },
  {
    id: 2,
    role: "bot",
    text: isQwen.value
      ? "Mình có thể hỗ trợ gì cho bạn?"
      : "Mình cần em hỗ trợ gì ạ?",
  },
]);

const messages = ref([]);
const isLoadingHistory = ref(true);
const inputMessage = ref("");
const requestKey = ref(0);
const pendingMessage = ref("");
const scrollArea = ref(null);
const isSending = ref(false);
const showTypingIndicator = computed(() => !isLoadingHistory.value && isSending.value);
const chatApiUrl = useChatApiUrl(props.botMode);
const chatBrand = "openclaw";

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function formatMessageHtml(text) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").trim();

  if (!normalized) {
    return "";
  }

  const blocks = normalized.split(/\n{2,}/);

  return blocks
    .map((block) => {
      const lines = block.split("\n");
      const isListBlock = lines.every((line) => /^\s*[-*]\s+/.test(line));

      if (isListBlock) {
        const items = lines
          .map((line) => line.replace(/^\s*[-*]\s+/, ""))
          .map((line) => `<li>${formatInlineMarkdown(line)}</li>`)
          .join("");

        return `<ul>${items}</ul>`;
      }

      return lines.map((line) => formatInlineMarkdown(line)).join("<br>");
    })
    .join("<br><br>");
}

function mapHistoryToMessages(historyItems) {
  return historyItems
    .filter((item) => item && typeof item === "object")
    .map((item, index) => ({
      id: `${item.created_at || "history"}-${index}`,
      role: item.role === "assistant" ? "bot" : "user",
      text: typeof item.content === "string" ? item.content : "",
    }))
    .filter((item) => item.text);
}

function buildIdentityQuery() {
  if (String(props.chatUserId || "").trim()) {
    return { user_id: props.chatUserId };
  }

  return { chat_token: props.chatToken || undefined };
}

async function loadHistory() {
  isLoadingHistory.value = true;

  try {
    const response = await $fetch(chatApiUrl, {
      method: "GET",
      query: {
        brand: chatBrand,
        category: "history",
        ...buildIdentityQuery(),
      },
    });

    const historyMessages = Array.isArray(response?.history)
      ? mapHistoryToMessages(response.history)
      : [];

    messages.value = historyMessages.length ? historyMessages : [...defaultMessages.value];
  } catch {
    messages.value = [...defaultMessages.value];
  } finally {
    isLoadingHistory.value = false;
  }
}

watch(
  () => [props.chatToken, props.chatUserId, props.botMode],
  () => {
    void loadHistory();
  }
);

onMounted(() => {
  void loadHistory();
});

watch(
  messages,
  async () => {
    await nextTick();
    const el = scrollArea.value;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  },
  { deep: true }
);

watch(showTypingIndicator, async () => {
  await nextTick();
  const el = scrollArea.value;
  if (el && typeof el.scrollTo === "function") {
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }
});

function sendMessage() {
  const text = inputMessage.value.trim();

  if (!text || isSending.value) {
    return;
  }

  messages.value.push({
    id: Date.now(),
    role: "user",
    text,
  });

  pendingMessage.value = text;
  requestKey.value += 1;
  inputMessage.value = "";
}

function onReply(text) {
  messages.value.push({
    id: Date.now() + 1,
    role: "bot",
    text,
  });
}

function onError() {
  messages.value.push({
    id: Date.now() + 2,
    role: "bot",
    text: "Hiện tại AI đang lỗi, vui lòng thử lại sau.",
  });
}

function onLoading(value) {
  isSending.value = Boolean(value);
}
</script>

<template>
  <div
    class="relative flex h-[710px] w-[min(430px,calc(100vw-32px))] flex-col overflow-hidden rounded-[28px] border border-chatBorder bg-white px-5 pb-5 pt-0 shadow-chat max-sm:h-[650px] max-sm:w-[min(340px,calc(100vw-22px))]"
  >
    <div
      v-if="isLoadingHistory"
      class="absolute inset-0 z-20 grid place-items-center rounded-[28px] bg-white/80 backdrop-blur-[2px]"
    >
      <div class="rounded-full bg-chatPurple px-4 py-2 text-[14px] font-semibold text-white shadow-chat">
        Đợi chút...
      </div>
    </div>

    <div class="mx-[-20px] flex items-center justify-between gap-3 bg-chatPurple px-5 py-[10px]">
      <div class="flex min-w-0 items-center gap-3">
        <p class="m-0 text-[18px] font-extrabold text-white">
          {{ chatTitle }}
        </p>
        <span class="rounded-full bg-white/15 px-2 py-1 text-[11px] font-medium text-white/90">
          {{ chatSubtitle }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          class="grid h-[40px] w-[40px] place-items-center rounded-[10px] bg-white/15 text-[18px] leading-none text-white"
          type="button"
          aria-label="Đặt lại chat"
          title="Đặt lại chat"
          @click="emit('reset')"
        >
          ↻
        </button>

        <button
          class="grid h-[40px] w-[40px] place-items-center rounded-[10px] bg-white/15 text-[28px] leading-none text-white"
          type="button"
          aria-label="Thu gọn chat"
          @click="emit('close')"
        >
          -
        </button>
      </div>
    </div>

    <div ref="scrollArea" class="mx-[-20px] flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 pb-4 pt-6 [scrollbar-gutter:stable]">
      <div
        v-for="item in messages"
        :key="item.id"
        :class="[
          'flex w-full',
          item.role === 'user' ? 'justify-end' : 'justify-start',
        ]"
      >
        <div
          :class="[
            'inline-block max-w-[86%] rounded-[20px] px-[14px] py-[12px] text-[15px] leading-[1.45] whitespace-pre-line break-words max-sm:text-[13px]',
            item.role === 'user'
              ? 'bg-chatPurple text-white'
              : 'bg-[#f5efff] text-chatText shadow-[0_1px_0_rgba(123,70,176,0.05)]',
          ]"
        >
          <div
            class="chat-markdown"
            v-html="item.role === 'bot' ? formatMessageHtml(item.text) : escapeHtml(item.text).replace(/\n/g, '<br>')"
          ></div>
        </div>
      </div>

      <div v-if="showTypingIndicator" class="flex w-full justify-start">
        <div class="flex max-w-[86%] flex-col items-start gap-1">
          <div class="flex items-center gap-2">
            <div
              class="grid h-[34px] w-[34px] flex-none place-items-center rounded-full bg-[radial-gradient(circle_at_30%_30%,#f1d45a_0_18%,#9a59c6_19%_48%,#652f98_49%_100%)] text-[11px] font-extrabold text-white shadow-[inset_0_0_0_2px_rgba(255,255,255,0.35)]"
            >
              AI
            </div>
            <div class="flex items-center gap-2 rounded-[18px] bg-[#f1f1f5] px-4 py-3 shadow-[0_1px_0_rgba(123,70,176,0.05)]">
              <span class="h-2.5 w-2.5 animate-bounce rounded-full bg-[#d0d0d7]" style="animation-delay:0ms" />
              <span class="h-2.5 w-2.5 animate-bounce rounded-full bg-[#c7c7cf]" style="animation-delay:140ms" />
              <span class="h-2.5 w-2.5 animate-bounce rounded-full bg-[#bdbdc7]" style="animation-delay:280ms" />
            </div>
          </div>
          <p class="pl-[42px] text-[14px] leading-none text-[#7f8798] max-sm:text-[13px]">
            Đang soạn tin nhắn...
          </p>
        </div>
      </div>
    </div>

    <form class="mt-auto flex flex-none items-center gap-2 rounded-full border border-[rgba(123,70,176,0.14)] bg-white px-3 py-2" @submit.prevent="sendMessage">
      <input
        v-model="inputMessage"
        class="min-w-0 flex-1 border-0 bg-transparent font-[inherit] outline-none"
        type="text"
        placeholder="Nhập tin nhắn..."
        aria-label="Nhập tin nhắn"
      />
      <button
        class="grid h-[38px] w-[38px] place-items-center rounded-full bg-chatPurple text-white"
        type="submit"
        aria-label="Gửi tin nhắn"
      >
        <svg
          viewBox="0 0 24 24"
          class="h-[20px] w-[20px]"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M5 12h11m0 0-4.5-4.5m4.5 4.5-4.5 4.5"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2.25"
          />
        </svg>
      </button>
    </form>

    <ChatBotRun
      :bot-mode="props.botMode"
      :chat-token="props.chatToken"
      :chat-user-id="props.chatUserId"
      :request-key="requestKey"
      :user-message="pendingMessage"
      @reply="onReply"
      @error="onError"
      @loading="onLoading"
    />
  </div>
</template>

<style scoped>
.chat-markdown :deep(strong) {
  font-weight: 700;
}

.chat-markdown :deep(code) {
  border-radius: 0.35rem;
  background: rgba(111, 44, 155, 0.08);
  padding: 0.08rem 0.32rem;
  font-size: 0.92em;
}

.chat-markdown :deep(ul) {
  margin: 0.25rem 0 0;
  padding-left: 1.15rem;
}

.chat-markdown :deep(li + li) {
  margin-top: 0.2rem;
}
</style>
