export default defineEventHandler(async (event) => {
  const body = await readBody<{
    message?: string;
    chat_token?: string;
    user_id?: string | number;
    brand?: string;
    category?: string;
    model?: string;
  }>(event);
  const message = (body?.message || "").trim();

  if (!message) {
    return {
      ok: false,
      error: "Bạn hãy nhập nội dung trước.",
    };
  }

  const chatApiUrl =
    process.env.CHAT_API_URL ||
    process.env.NUXT_PUBLIC_CHAT_API_URL ||
    "http://vip.tecom.pro:8006/chat_bot/api";

  return await $fetch(chatApiUrl, {
    method: "POST",
    body: {
      brand: body?.brand || "openclaw",
      category: body?.category,
      model: body?.model,
      user_id: body?.user_id !== undefined ? body.user_id : undefined,
      chat_token: body?.chat_token || undefined,
      message,
    },
  });
});
