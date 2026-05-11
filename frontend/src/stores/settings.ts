import { defineStore } from 'pinia'
import { ref, watch, nextTick } from 'vue'
import { settingsAPI } from '../services/api'
import type { UnitSystem } from '../utils/units'
import type { SensoryPreferences } from '../services/api'
import { DEFAULT_SENSORY_PREFERENCES } from '../services/api'

export type TimeFirstLayout = 'auto' | 'time_first' | 'normal'

function debounce(fn: () => void, ms: number): () => void {
  let t: ReturnType<typeof setTimeout>
  return () => { clearTimeout(t); t = setTimeout(fn, ms) }
}

export const useSettingsStore = defineStore('settings', () => {
  const cookingEquipment = ref<string[]>([])
  const unitSystem = ref<UnitSystem>('metric')
  const shoppingLocale = ref<string>('us')
  const sensoryPreferences = ref<SensoryPreferences>({ ...DEFAULT_SENSORY_PREFERENCES })
  const timeFirstLayout = ref<TimeFirstLayout>('auto')
  const loading = ref(false)
  const saved = ref(false)

  // Prevents autosave watchers from firing during initial load hydration.
  // Set to true after nextTick() at the end of load() — by that point all
  // watcher jobs queued by the hydration assignments have already flushed.
  let _hydrated = false

  function _flash() {
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  }

  async function _saveKey(key: string, value: string): Promise<void> {
    if (!_hydrated) return
    try {
      await settingsAPI.setSetting(key, value)
      _flash()
    } catch (err: unknown) {
      console.error('Autosave failed for key:', key, err)
    }
  }

  const _autosave = {
    equipment: debounce(() => _saveKey('cooking_equipment', JSON.stringify(cookingEquipment.value)), 600),
    unit:      debounce(() => _saveKey('unit_system', unitSystem.value), 600),
    locale:    debounce(() => _saveKey('shopping_locale', shoppingLocale.value), 600),
    sensory:   debounce(() => _saveKey('sensory_preferences', JSON.stringify(sensoryPreferences.value)), 600),
    layout:    debounce(() => _saveKey('time_first_layout', timeFirstLayout.value), 600),
  }

  watch(cookingEquipment, _autosave.equipment, { deep: true })
  watch(unitSystem, _autosave.unit)
  watch(shoppingLocale, _autosave.locale)
  watch(sensoryPreferences, _autosave.sensory, { deep: true })
  watch(timeFirstLayout, _autosave.layout)

  async function load() {
    loading.value = true
    try {
      const [rawEquipment, rawUnits, rawLocale, rawSensory, rawTimeFirst] = await Promise.allSettled([
        settingsAPI.getSetting('cooking_equipment'),
        settingsAPI.getSetting('unit_system'),
        settingsAPI.getSetting('shopping_locale'),
        settingsAPI.getSetting('sensory_preferences'),
        settingsAPI.getSetting('time_first_layout'),
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
      if (rawSensory.status === 'fulfilled' && rawSensory.value) {
        try {
          sensoryPreferences.value = JSON.parse(rawSensory.value)
        } catch {
          sensoryPreferences.value = { ...DEFAULT_SENSORY_PREFERENCES }
        }
      }
      if (rawTimeFirst.status === 'fulfilled' && rawTimeFirst.value) {
        timeFirstLayout.value = rawTimeFirst.value as TimeFirstLayout
      }
    } catch (err: unknown) {
      console.error('Failed to load settings:', err)
    } finally {
      loading.value = false
    }
    // Yield past the watcher flush triggered by hydration assignments above.
    // After nextTick, any pending watcher jobs from this load() have already
    // run (and been ignored by _hydrated guard), so user-driven changes from
    // here forward will correctly trigger autosave.
    await nextTick()
    _hydrated = true
  }

  // Kept for explicit full-save scenarios (e.g. fallback, tests).
  async function save() {
    loading.value = true
    try {
      await Promise.all([
        settingsAPI.setSetting('cooking_equipment', JSON.stringify(cookingEquipment.value)),
        settingsAPI.setSetting('unit_system', unitSystem.value),
        settingsAPI.setSetting('shopping_locale', shoppingLocale.value),
        settingsAPI.setSetting('sensory_preferences', JSON.stringify(sensoryPreferences.value)),
        settingsAPI.setSetting('time_first_layout', timeFirstLayout.value),
      ])
      _flash()
    } catch (err: unknown) {
      console.error('Failed to save settings:', err)
    } finally {
      loading.value = false
    }
  }

  // Kept for backward compat; autosave handles sensory changes now.
  async function saveSensory() {
    try {
      await settingsAPI.setSetting('sensory_preferences', JSON.stringify(sensoryPreferences.value))
      _flash()
    } catch (err: unknown) {
      console.error('Failed to save sensory preferences:', err)
    }
  }

  return {
    cookingEquipment,
    unitSystem,
    shoppingLocale,
    sensoryPreferences,
    timeFirstLayout,
    loading,
    saved,
    load,
    save,
    saveSensory,
  }
})
