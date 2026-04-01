/**
 * Settings Store
 *
 * Manages user settings (cooking equipment, preferences) using Pinia.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsAPI } from '../services/api'

export const useSettingsStore = defineStore('settings', () => {
  // State
  const cookingEquipment = ref<string[]>([])
  const loading = ref(false)
  const saved = ref(false)

  // Actions
  async function load() {
    loading.value = true
    try {
      const raw = await settingsAPI.getSetting('cooking_equipment')
      if (raw) {
        cookingEquipment.value = JSON.parse(raw)
      }
    } catch (err: unknown) {
      console.error('Failed to load settings:', err)
    } finally {
      loading.value = false
    }
  }

  async function save() {
    loading.value = true
    try {
      await settingsAPI.setSetting('cooking_equipment', JSON.stringify(cookingEquipment.value))
      saved.value = true
      setTimeout(() => {
        saved.value = false
      }, 2000)
    } catch (err: unknown) {
      console.error('Failed to save settings:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    cookingEquipment,
    loading,
    saved,

    // Actions
    load,
    save,
  }
})
