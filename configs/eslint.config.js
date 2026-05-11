import { globalIgnores } from 'eslint/config'
import pluginVue from 'eslint-plugin-vue'
import pluginSecurity from 'eslint-plugin-security'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'

export default defineConfigWithVueTs(
  globalIgnores([
    '**/dist/**',
    '**/dist-ssr/**',
    '**/node_modules/**',
    '**/coverage/**',
    '**/build/**',
  ]),
  {
    files: ['**/*.{js,jsx,mjs,cjs,ts,tsx,vue}'],
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  pluginSecurity.configs.recommended,
  {
    rules: {
      'vue/multi-word-component-names': 'off',
    },
  }
)
