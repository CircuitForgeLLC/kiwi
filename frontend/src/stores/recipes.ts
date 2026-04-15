/**
 * Recipes Store
 *
 * Manages recipe suggestion state and request parameters using Pinia.
 * Dismissed recipe IDs are persisted to localStorage with a 7-day TTL.
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { recipesAPI, type RecipeResult, type RecipeSuggestion, type RecipeRequest, type NutritionFilters } from '../services/api'

const DISMISSED_KEY = 'kiwi:dismissed_recipes'
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000

const COOK_LOG_KEY = 'kiwi:cook_log'
const COOK_LOG_MAX = 200

const BOOKMARKS_KEY = 'kiwi:bookmarks'
const BOOKMARKS_MAX = 50

const MISSING_MODE_KEY = 'kiwi:builder_missing_mode'
const FILTER_MODE_KEY = 'kiwi:builder_filter_mode'

const CONSTRAINTS_KEY = 'kiwi:constraints'
const ALLERGIES_KEY = 'kiwi:allergies'

function loadConstraints(): string[] {
  try {
    const raw = localStorage.getItem(CONSTRAINTS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveConstraints(vals: string[]) {
  localStorage.setItem(CONSTRAINTS_KEY, JSON.stringify(vals))
}

function loadAllergies(): string[] {
  try {
    const raw = localStorage.getItem(ALLERGIES_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveAllergies(vals: string[]) {
  localStorage.setItem(ALLERGIES_KEY, JSON.stringify(vals))
}

type MissingIngredientMode = 'hidden' | 'greyed' | 'add-to-cart'
type BuilderFilterMode = 'text' | 'tags'

// [id, dismissedAtMs]
type DismissEntry = [number, number]

export interface CookLogEntry {
  id: number
  title: string
  cookedAt: number // unix ms
}

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

function loadCookLog(): CookLogEntry[] {
  try {
    const raw = localStorage.getItem(COOK_LOG_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveCookLog(log: CookLogEntry[]) {
  localStorage.setItem(COOK_LOG_KEY, JSON.stringify(log.slice(-COOK_LOG_MAX)))
}

function loadBookmarks(): RecipeSuggestion[] {
  try {
    const raw = localStorage.getItem(BOOKMARKS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveBookmarks(bookmarks: RecipeSuggestion[]) {
  localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(bookmarks.slice(0, BOOKMARKS_MAX)))
}

function loadMissingMode(): MissingIngredientMode {
  const raw = localStorage.getItem(MISSING_MODE_KEY)
  if (raw === 'hidden' || raw === 'greyed' || raw === 'add-to-cart') return raw
  return 'greyed'
}

function loadFilterMode(): BuilderFilterMode {
  return localStorage.getItem(FILTER_MODE_KEY) === 'tags' ? 'tags' : 'text'
}

export const useRecipesStore = defineStore('recipes', () => {
  // Suggestion result state
  const result = ref<RecipeResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Request parameters
  const level = ref(1)
  const constraints = ref<string[]>(loadConstraints())
  const allergies = ref<string[]>(loadAllergies())
  const hardDayMode = ref(false)
  const maxMissing = ref<number | null>(null)
  const styleId = ref<string | null>(null)
  const category = ref<string | null>(null)
  const wildcardConfirmed = ref(false)
  const shoppingMode = ref(false)
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
  // Cook log: persisted to localStorage, max COOK_LOG_MAX entries
  const cookLog = ref<CookLogEntry[]>(loadCookLog())
  // Bookmarks: full RecipeSuggestion snapshots, max BOOKMARKS_MAX
  const bookmarks = ref<RecipeSuggestion[]>(loadBookmarks())

  // Build Your Own wizard preferences -- persisted across sessions
  const missingIngredientMode = ref<MissingIngredientMode>(loadMissingMode())
  const builderFilterMode = ref<BuilderFilterMode>(loadFilterMode())

  // Persist wizard prefs on change
  watch(missingIngredientMode, (val) => localStorage.setItem(MISSING_MODE_KEY, val))
  watch(builderFilterMode, (val) => localStorage.setItem(FILTER_MODE_KEY, val))
  watch(constraints, (val) => saveConstraints(val), { deep: true })
  watch(allergies, (val) => saveAllergies(val), { deep: true })

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
      shopping_mode: shoppingMode.value,
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

  function undismiss(id: number) {
    dismissedIds.value = new Set([...dismissedIds.value].filter((d) => d !== id))
    saveDismissed(dismissedIds.value)
  }

  function clearDismissed() {
    dismissedIds.value = new Set()
    localStorage.removeItem(DISMISSED_KEY)
  }

  function logCook(id: number, title: string) {
    const entry: CookLogEntry = { id, title, cookedAt: Date.now() }
    cookLog.value = [...cookLog.value, entry]
    saveCookLog(cookLog.value)
  }

  function clearCookLog() {
    cookLog.value = []
    localStorage.removeItem(COOK_LOG_KEY)
  }

  function isBookmarked(id: number): boolean {
    return bookmarks.value.some((b) => b.id === id)
  }

  function toggleBookmark(recipe: RecipeSuggestion) {
    if (isBookmarked(recipe.id)) {
      bookmarks.value = bookmarks.value.filter((b) => b.id !== recipe.id)
    } else {
      bookmarks.value = [recipe, ...bookmarks.value]
    }
    saveBookmarks(bookmarks.value)
  }

  function clearBookmarks() {
    bookmarks.value = []
    localStorage.removeItem(BOOKMARKS_KEY)
  }

  function clearConstraints() {
    constraints.value = []
    localStorage.removeItem(CONSTRAINTS_KEY)
  }

  function clearAllergies() {
    allergies.value = []
    localStorage.removeItem(ALLERGIES_KEY)
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
    shoppingMode,
    nutritionFilters,
    dismissedIds,
    dismissedCount,
    cookLog,
    logCook,
    clearCookLog,
    bookmarks,
    isBookmarked,
    toggleBookmark,
    clearBookmarks,
    clearConstraints,
    clearAllergies,
    missingIngredientMode,
    builderFilterMode,
    suggest,
    loadMore,
    dismiss,
    undismiss,
    clearDismissed,
    clearResult,
  }
})
