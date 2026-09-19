import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// 本项目源码（main.js/manifest.json/pages.json）位于仓库根目录而非 src/
process.env.UNI_INPUT_DIR = process.env.UNI_INPUT_DIR || __dirname

export default defineConfig({
  plugins: [uni()],
})
