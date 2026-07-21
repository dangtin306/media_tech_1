/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app.vue",
    "./components/**/*.{vue,js,ts}",
    "./layouts/**/*.vue",
    "./pages/**/*.vue",
    "./plugins/**/*.{js,ts}",
    "./server/**/*.{js,ts}",
  ],
  theme: {
    extend: {
      boxShadow: {
        chat: "0 18px 50px rgba(80, 38, 128, 0.18)",
      },
      colors: {
        chatPurple: "#6f2c9b",
        chatPurpleDark: "#62349a",
        chatText: "#394153",
        chatBorder: "rgba(123, 70, 176, 0.12)",
      },
    },
  },
  plugins: [],
};
