/**
 * Saved Recipes Store
 *
 * Manages bookmarked recipes, ratings, style tags, and collections.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { savedRecipesAPI, type SavedRecipe, type RecipeCollection } from '../services/api'

export const useSavedRecipesStore = defineStore('savedRecipes', () => {
  const saved = ref<SavedRecipe[]>([])
  const collections = ref<RecipeCollection[]>([])
  const loading = ref(false)
  const sortBy = ref<'saved_at' | 'rating' | 'title'>('saved_at')
  const activeCollectionId = ref<number | null>(null)

  const savedIds = computed(() => new Set(saved.value.map((s) => s.recipe_id)))

  function isSaved(recipeId: number): boolean {
    return savedIds.value.has(recipeId)
  }

  function getSaved(recipeId: number): SavedRecipe | undefined {
    return saved.value.find((s) => s.recipe_id === recipeId)
  }

  async function load() {
    loading.value = true
    try {
      const [items, cols] = await Promise.all([
        savedRecipesAPI.list({ sort_by: sortBy.value, collection_id: activeCollectionId.value ?? undefined }),
        savedRecipesAPI.listCollections(),
      ])
      saved.value = items
      collections.value = cols
    } finally {
      loading.value = false
    }
  }

  async function save(recipeId: number, notes?: string, rating?: number): Promise<SavedRecipe> {
    const result = await savedRecipesAPI.save(recipeId, notes, rating)
    const idx = saved.value.findIndex((s) => s.recipe_id === recipeId)
    if (idx >= 0) {
      saved.value = [...saved.value.slice(0, idx), result, ...saved.value.slice(idx + 1)]
    } else {
      saved.value = [result, ...saved.value]
    }
    return result
  }

  async function unsave(recipeId: number): Promise<void> {
    await savedRecipesAPI.unsave(recipeId)
    saved.value = saved.value.filter((s) => s.recipe_id !== recipeId)
  }

  async function update(recipeId: number, data: { notes?: string | null; rating?: number | null; style_tags?: string[] }): Promise<SavedRecipe> {
    const result = await savedRecipesAPI.update(recipeId, data)
    const idx = saved.value.findIndex((s) => s.recipe_id === recipeId)
    if (idx >= 0) {
      saved.value = [...saved.value.slice(0, idx), result, ...saved.value.slice(idx + 1)]
    }
    return result
  }

  async function createCollection(name: string, description?: string): Promise<RecipeCollection> {
    const col = await savedRecipesAPI.createCollection(name, description)
    collections.value = [...collections.value, col]
    return col
  }

  async function deleteCollection(id: number): Promise<void> {
    await savedRecipesAPI.deleteCollection(id)
    collections.value = collections.value.filter((c) => c.id !== id)
    if (activeCollectionId.value === id) activeCollectionId.value = null
  }

  return {
    saved, collections, loading, sortBy, activeCollectionId,
    savedIds, isSaved, getSaved,
    load, save, unsave, update, createCollection, deleteCollection,
  }
})
