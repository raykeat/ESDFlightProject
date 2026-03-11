import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      '/api/passenger': {
        target: 'https://personal-4whagfbm.outsystemscloud.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/passenger/, '/Passenger_Srv/rest/PassengerAPI'),
      },
    },
  },
})
