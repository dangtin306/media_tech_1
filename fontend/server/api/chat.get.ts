export default defineEventHandler(async (event) => {
  const query = getQuery<{
    message?: string;
    text?: string;
    query?: string;
    chat_token?: string;
    user_id?: string | number;
    brand?: string;
    category?: string;
    model?: string;
  }>(event);

  const chatApiUrl =
    process.env.CHAT_API_URL ||
    process.env.NUXT_PUBLIC_CHAT_API_URL ||
    "http://vip.tecom.pro:8006/chat_bot/api";

  return await $fetch(chatApiUrl, {
    method: "GET",
    query: {
      brand: query?.brand || "openclaw",
      category: query?.category,
      model: query?.model,
      user_id: query?.user_id,
      chat_token: query?.chat_token,
      message: query?.message || query?.text || query?.query,
    },
  });
});
