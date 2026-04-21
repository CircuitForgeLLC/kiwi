/**
 * Settings Store
 *
 * Manages user settings (cooking equipment, preferences) using Pinia.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsAPI } from '../services/api'
import type { UnitSystem } from '../utils/units'

export const useSettingsStore = defineStore('settings', () => {
  // State
  const cookingEquipment = ref<string[]>([])
  const unitSystem = ref<UnitSystem>('metric')
  const shoppingLocale = ref<string>('us')
  const loading = ref(false)
  const saved = ref(false)

  // Actions
  async function load() {
    loading.value = true
    try {
      const [rawEquipment, rawUnits, rawLocale] = await Promise.allSettled([
        settingsAPI.getSetting('cooking_equipment'),
        settingsAPI.getSetting('unit_system'),
        settingsAPI.getSetting('shopping_locale'),
      ])
      if (rawEquipment.status === 'fulfilled' && rawEquipment.value) {
        cookingEquipment.value = JSON.parse(rawEquipment.value)
      }
      if (rawUnits.status === 'fulfilled' && rawUnits.value) {
        unitSystem.value = rawUnits.value as UnitSystem
      }
      if (rawLocale.status === 'fulfilled' && rawLocale.value) {
        shoppingLocale.value = rawLocale.value
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
      await Promise.all([
        settingsAPI.setSetting('cooking_equipment', JSON.stringify(cookingEquipment.value)),
        settingsAPI.setSetting('unit_system', unitSystem.value),
        settingsAPI.setSetting('shopping_locale', shoppingLocale.value),
      ])
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
    unitSystem,
    shoppingLocale,
    loading,
    saved,

    // Actions
    load,
    save,
  }
})
