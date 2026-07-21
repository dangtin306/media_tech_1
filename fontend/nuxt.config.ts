export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ["@nuxtjs/tailwindcss"],
  tailwindcss: {
    configPath: [],
    config: {
      theme: {
        extend: {
          boxShadow: {
            chat: "0 18px 50px rgba(80, 38, 128, 0.18)"
          },
          colors: {
            chatPurple: "#6f2c9b",
            chatPurpleDark: "#62349a",
            chatText: "#394153",
            chatBorder: "rgba(123, 70, 176, 0.12)"
          }
        }
      },
      plugins: []
    }
  },
  app: {
    baseURL: "/chat_bot/"
  },
  runtimeConfig: {
    public: {
      chatApiUrl: "/chat_bot/api",
      codexModel: "",
      qwenModel: "Qwen3.5-4B-V4"
    }
  },
  devServer: {
    host: "0.0.0.0",
    port: 8008
  },
  experimental: {
    watcher: "chokidar"
  },
  vite: {
    server: {
      allowedHosts: true
    }
  },
  css: ["~/assets/css/tailwind.css"],
});
