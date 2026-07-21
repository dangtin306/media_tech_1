<script setup>
const props = defineProps({
  botMode: {
    type: String,
    default: "codex",
  },
});

const isOpen = ref(false);
const cookieSuffix = props.botMode === "qwen" ? "qwen" : "codex";
const chatToken = useCookie(`chat_token_${cookieSuffix}`, {
  maxAge: 60 * 60 * 24 * 30,
  path: "/",
  sameSite: "lax",
});
const chatUserId = useCookie(`chat_user_id_${cookieSuffix}`, {
  maxAge: 60 * 60 * 24 * 30,
  path: "/",
  sameSite: "lax",
});

const isQwen = computed(() => props.botMode === "qwen");
const chatTitle = computed(() => (isQwen.value ? "Qwen3.5-4B-V4" : "TuongTac.tv"));
const runtimeConfig = useRuntimeConfig();
const qwenModel = computed(() => runtimeConfig.public?.qwenModel || "Qwen3.5-4B-V4");
const introMessages = computed(() => (
  isQwen.value
    ? [
        "Xin chào, tôi là Qwen3.5-4B-V4",
        "Mình có thể hỗ trợ gì cho bạn?",
      ]
    : [
        "Xin chào, em là trợ lý AI của TuongTac.tv",
        "Mình cần em hỗ trợ gì ạ?",
      ]
));
const introIndex = ref(0);
let introTimer = null;

const introText = computed(() => introMessages.value[introIndex.value] || introMessages.value[0]);

function generateChatToken(length = 20) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const bytes = new Uint32Array(length);

  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (value) => chars[value % chars.length]).join("");
  }

  let token = "";
  for (let index = 0; index < length; index += 1) {
    token += chars[Math.floor(Math.random() * chars.length)];
  }
  return token;
}

async function syncChatUserId() {
  try {
    const response = await $fetch(useChatApiUrl(props.botMode), {
      method: "POST",
      body: {
        brand: "openclaw",
        category: "user_id",
        model: isQwen.value ? qwenModel.value : undefined,
        chat_token: chatToken.value,
      },
    });

    if (response?.user_id !== undefined && response?.user_id !== null) {
      chatUserId.value = String(response.user_id);
    }
  } catch {
    // Keep the widget usable even if the backend is temporarily unavailable.
  }
}

if (!chatToken.value) {
  chatToken.value = generateChatToken(20);
}

if (import.meta.client) {
  void syncChatUserId();
}

onMounted(() => {
  introTimer = window.setInterval(() => {
    introIndex.value = (introIndex.value + 1) % introMessages.value.length;
  }, 2800);
});

onBeforeUnmount(() => {
  if (introTimer) {
    window.clearInterval(introTimer);
    introTimer = null;
  }
});

function openChat() {
  isOpen.value = true;
}

function closeChat() {
  isOpen.value = false;
}

function resetChat() {
  chatToken.value = "";
  chatUserId.value = "";

  if (import.meta.client) {
    chatToken.value = generateChatToken(20);
    void syncChatUserId();
  }
}
</script>

<template>
  <div class="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3 max-sm:bottom-3 max-sm:right-3">
    <Transition name="fade-slide">
      <div
        v-if="!isOpen"
        class="w-[min(360px,calc(100vw-40px))] rounded-[28px] border border-chatBorder bg-white px-5 py-4 shadow-chat max-sm:w-[min(320px,calc(100vw-28px))]"
      >
        <div class="flex items-center gap-2.5">
          <div
            class="grid h-[40px] w-[40px] place-items-center rounded-full bg-[radial-gradient(circle_at_30%_30%,#f1d45a_0_18%,#9a59c6_19%_48%,#652f98_49%_100%)] text-[12px] font-extrabold text-white shadow-[inset_0_0_0_3px_rgba(255,255,255,0.35)]"
          >
            AI
          </div>
          <p class="m-0 text-[17px] font-extrabold text-chatPurpleDark">
            {{ chatTitle }}
          </p>
        </div>

        <Transition name="intro-swap" mode="out-in">
          <p :key="introIndex" class="mt-4 text-[22px] font-medium leading-[1.35] text-chatText max-sm:text-[20px]">
            {{ introText }}
          </p>
        </Transition>
      </div>
    </Transition>

    <ChatBotBox
      v-if="isOpen"
      :chat-token="chatToken"
      :chat-user-id="chatUserId"
      :bot-mode="props.botMode"
      @close="closeChat"
      @reset="resetChat"
    />

    <button
      v-if="!isOpen"
      class="grid h-[70px] w-[70px] place-items-center rounded-full border-0 bg-[radial-gradient(circle_at_30%_30%,#f2d86d_0_15%,#b66bd3_16_40%,#6f2c9b_41_100%)] text-white shadow-[0_14px_30px_rgba(111,44,155,0.34)]"
      type="button"
      aria-label="Mở chat hỗ trợ"
      @click="openChat"
    >
      <span
        class="relative grid h-[58px] w-[58px] place-items-center overflow-hidden rounded-full bg-[linear-gradient(135deg,#a866d7_0%,#6f2c9b_100%)] text-[16px] font-extrabold leading-none text-white shadow-[inset_0_0_0_4px_rgba(255,255,255,0.18)]"
      >
        <span
          class="absolute left-[8px] top-[7px] h-[22px] w-[22px] rounded-full bg-[#f3d85f]"
          aria-hidden="true"
        />
        <span class="relative translate-y-[1px]">AI</span>
      </span>
    </button>
  </div>
</template>

<style scoped>
.intro-swap-enter-active,
.intro-swap-leave-active {
  transition:
    opacity 220ms ease,
    transform 220ms ease;
}

.intro-swap-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.intro-swap-enter-to {
  opacity: 1;
  transform: translateY(0);
}

.intro-swap-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.intro-swap-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
