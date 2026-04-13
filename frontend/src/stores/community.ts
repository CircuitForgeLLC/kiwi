// frontend/src/stores/community.ts
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../services/api'

export interface CommunityPost {
  slug: string
  pseudonym: string
  post_type: 'plan' | 'recipe_success' | 'recipe_blooper'
  published: string
  title: string
  description: string | null
  photo_url: string | null
  slots: Array<{ day: string; meal_type: string; recipe_id: number; recipe_name: string }>
  recipe_id: number | null
  recipe_name: string | null
  level: number | null
  outcome_notes: string | null
  element_profiles: {
    seasoning_score: number
    richness_score: number
    brightness_score: number
    depth_score: number
    aroma_score: number
    structure_score: number
    texture_profile: string
  }
  dietary_tags: string[]
  allergen_flags: string[]
  fat_pct: number | null
  protein_pct: number | null
  moisture_pct: number | null
}

export const useCommunityStore = defineStore('community', () => {
  const posts = ref<CommunityPost[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const page = ref(1)
  const hasMore = ref(true)
  const pseudonym = ref<string | null>(null)

  // Filters
  const filterDietaryTags = ref<string[]>([])
  const filterPostType = ref<'plan' | 'recipe_success' | 'recipe_blooper' | null>(null)

  const isEmpty = computed(() => !loading.value && posts.value.length === 0)

  async function loadPosts(reset = false) {
    if (loading.value) return
    if (reset) {
      posts.value = []
      page.value = 1
      hasMore.value = true
    }
    if (!hasMore.value) return

    loading.value = true
    error.value = null
    try {
      const params: Record<string, string | number> = {
        page: page.value,
        page_size: 20,
      }
      if (filterPostType.value) params.post_type = filterPostType.value
      if (filterDietaryTags.value.length) params.dietary_tags = filterDietaryTags.value.join(',')

      const res = await api.get('/community/posts', { params })
      const newPosts: CommunityPost[] = res.data.posts ?? []
      posts.value = reset ? newPosts : [...posts.value, ...newPosts]
      hasMore.value = newPosts.length === 20
      page.value += 1
    } catch (err: any) {
      error.value = err?.response?.data?.detail ?? 'Could not load community posts.'
    } finally {
      loading.value = false
    }
  }

  async function forkPost(slug: string): Promise<{ plan_id: number; week_start: string } | null> {
    try {
      const res = await api.post(`/community/posts/${slug}/fork`)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.detail ?? 'Fork failed.'
      return null
    }
  }

  async function publishPost(payload: {
    post_type: string
    title: string
    description?: string
    pseudonym_name?: string
    slots?: unknown[]
    recipe_id?: number
    recipe_name?: string
    outcome_notes?: string
  }): Promise<CommunityPost | null> {
    try {
      const res = await api.post('/community/posts', payload)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.detail ?? 'Publish failed.'
      return null
    }
  }

  function setFilter(type: typeof filterPostType.value) {
    filterPostType.value = type
    loadPosts(true)
  }

  function clearError() {
    error.value = null
  }

  return {
    posts, loading, error, page, hasMore, pseudonym,
    filterDietaryTags, filterPostType, isEmpty,
    loadPosts, forkPost, publishPost, setFilter, clearError,
  }
})
