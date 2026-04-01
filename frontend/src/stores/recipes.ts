/**
 * Recipes Store
 *
 * Manages recipe suggestion state and request parameters using Pinia.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { recipesAPI, type RecipeResult, type RecipeRequest } from '../services/api'

export const useRecipesStore = defineStore('recipes', () => {
  // State
  const result = ref<RecipeResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const level = ref(1)
  const constraints = ref<string[]>([])
  const allergies = ref<string[]>([])
  const hardDayMode = ref(false)
  const maxMissing = ref<number | null>(null)
  const styleId = ref<string | null>(null)
  const wildcardConfirmed = ref(false)

  // Actions
  async function suggest(pantryItems: string[]) {
    loading.value = true
    error.value = null

    const req: RecipeRequest = {
      pantry_items: pantryItems,
      level: level.value,
      constraints: constraints.value,
      allergies: allergies.value,
      expiry_first: true,
      hard_day_mode: hardDayMode.value,
      max_missing: maxMissing.value,
      style_id: styleId.value,
      wildcard_confirmed: wildcardConfirmed.value,
    }

    try {
      result.value = await recipesAPI.suggest(req)
    } catch (err: unknown) {
      if (err instanceof Error) {
        error.value = err.message
      } else {
        error.value = 'Failed to get recipe suggestions'
      }
      console.error('Error fetching recipe suggestions:', err)
    } finally {
      loading.value = false
    }
  }

  function clearResult() {
    result.value = null
    error.value = null
    wildcardConfirmed.value = false
  }

  return {
    // State
    result,
    loading,
    error,
    level,
    constraints,
    allergies,
    hardDayMode,
    maxMissing,
    styleId,
    wildcardConfirmed,

    // Actions
    suggest,
    clearResult,
  }
})
