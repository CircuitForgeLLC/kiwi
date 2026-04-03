/**
 * Recipes Store
 *
 * Manages recipe suggestion state and request parameters using Pinia.
 * Dismissed recipe IDs are persisted to localStorage with a 7-day TTL.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { recipesAPI, type RecipeResult, type RecipeSuggestion, type RecipeRequest, type NutritionFilters } from '../services/api'

const DISMISSED_KEY = 'kiwi:dismissed_recipes'
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000

// [id, dismissedAtMs]
type DismissEntry = [number, number]

function loadDismissed(): Set<number> {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY)
    if (!raw) return new Set()
    const entries: DismissEntry[] = JSON.parse(raw)
    const cutoff = Date.now() - DISMISS_TTL_MS
    return new Set(entries.filter(([, ts]) => ts > cutoff).map(([id]) => id))
  } catch {
    return new Set()
  }
}

function saveDismissed(ids: Set<number>) {
  const now = Date.now()
  const entries: DismissEntry[] = [...ids].map((id) => [id, now])
  localStorage.setItem(DISMISSED_KEY, JSON.stringify(entries))
}

export const useRecipesStore = defineStore('recipes', () => {
  // Suggestion result state
  const result = ref<RecipeResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Request parameters
  const level = ref(1)
  const constraints = ref<string[]>([])
  const allergies = ref<string[]>([])
  const hardDayMode = ref(false)
  const maxMissing = ref<number | null>(null)
  const styleId = ref<string | null>(null)
  const category = ref<string | null>(null)
  const wildcardConfirmed = ref(false)
  const nutritionFilters = ref<NutritionFilters>({
    max_calories: null,
    max_sugar_g: null,
    max_carbs_g: null,
    max_sodium_mg: null,
  })

  // Dismissed IDs: persisted to localStorage, 7-day TTL
  const dismissedIds = ref<Set<number>>(loadDismissed())
  // Seen IDs: session-only, used by Load More to avoid repeating results
  const seenIds = ref<Set<number>>(new Set())

  const dismissedCount = computed(() => dismissedIds.value.size)

  function _buildRequest(pantryItems: string[], extraExcluded: number[] = []): RecipeRequest {
    const excluded = new Set([...dismissedIds.value, ...extraExcluded])
    return {
      pantry_items: pantryItems,
      level: level.value,
      constraints: constraints.value,
      allergies: allergies.value,
      expiry_first: true,
      hard_day_mode: hardDayMode.value,
      max_missing: maxMissing.value,
      style_id: styleId.value,
      category: category.value,
      wildcard_confirmed: wildcardConfirmed.value,
      nutrition_filters: nutritionFilters.value,
      excluded_ids: [...excluded],
    }
  }

  function _trackSeen(suggestions: RecipeSuggestion[]) {
    for (const s of suggestions) {
      if (s.id) seenIds.value = new Set([...seenIds.value, s.id])
    }
  }

  async function suggest(pantryItems: string[]) {
    loading.value = true
    error.value = null
    seenIds.value = new Set()

    try {
      result.value = await recipesAPI.suggest(_buildRequest(pantryItems))
      _trackSeen(result.value.suggestions)
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to get recipe suggestions'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(pantryItems: string[]) {
    if (!result.value || loading.value) return
    loading.value = true
    error.value = null

    try {
      // Exclude everything already shown (dismissed + all seen this session)
      const more = await recipesAPI.suggest(_buildRequest(pantryItems, [...seenIds.value]))
      if (more.suggestions.length === 0) {
        error.value = 'No more recipes found — try clearing dismissed or adjusting filters.'
      } else {
        result.value = {
          ...result.value,
          suggestions: [...result.value.suggestions, ...more.suggestions],
          grocery_list: [...new Set([...result.value.grocery_list, ...more.grocery_list])],
          grocery_links: [...result.value.grocery_links, ...more.grocery_links],
        }
        _trackSeen(more.suggestions)
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to load more recipes'
    } finally {
      loading.value = false
    }
  }

  function dismiss(id: number) {
    dismissedIds.value = new Set([...dismissedIds.value, id])
    saveDismissed(dismissedIds.value)
    // Remove from current results immediately
    if (result.value) {
      result.value = {
        ...result.value,
        suggestions: result.value.suggestions.filter((s) => s.id !== id),
      }
    }
  }

  function clearDismissed() {
    dismissedIds.value = new Set()
    localStorage.removeItem(DISMISSED_KEY)
  }

  function clearResult() {
    result.value = null
    error.value = null
    wildcardConfirmed.value = false
  }

  return {
    result,
    loading,
    error,
    level,
    constraints,
    allergies,
    hardDayMode,
    maxMissing,
    styleId,
    category,
    wildcardConfirmed,
    nutritionFilters,
    dismissedIds,
    dismissedCount,
    suggest,
    loadMore,
    dismiss,
    clearDismissed,
    clearResult,
  }
})
