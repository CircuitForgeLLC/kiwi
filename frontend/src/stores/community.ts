/**
 * Community Store
 *
 * Manages community post feed state and fork actions using Pinia.
 * Follows the composition store pattern established in recipes.ts.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

// ========== Types ==========

export interface CommunityPostSlot {
  day: string
  meal_type: string
  recipe_id: number
}

export interface ElementProfiles {
  seasoning_score: number | null
  richness_score: number | null
  brightness_score: number | null
  depth_score: number | null
  aroma_score: number | null
  structure_score: number | null
  texture_profile: string | null
}

export interface CommunityPost {
  slug: string
  pseudonym: string
  post_type: 'plan' | 'recipe_success' | 'recipe_blooper'
  published: string
  title: string
  description: string | null
  photo_url: string | null
  slots: CommunityPostSlot[]
  recipe_id: number | null
  recipe_name: string | null
  level: number | null
  outcome_notes: string | null
  element_profiles: ElementProfiles
  dietary_tags: string[]
  allergen_flags: string[]
  flavor_molecules: string[]
  fat_pct: number | null
  protein_pct: number | null
  moisture_pct: number | null
}

export interface ForkResult {
  plan_id: number
  week_start: string
  forked_from: string
}

// ========== Store ==========

export const useCommunityStore = defineStore('community', () => {
  const posts = ref<CommunityPost[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentFilter = ref<string | null>(null)

  async function fetchPosts(postType?: string) {
    loading.value = true
    error.value = null
    currentFilter.value = postType ?? null

    try {
      const params: Record<string, string | number> = { page: 1, page_size: 40 }
      if (postType) {
        params.post_type = postType
      }
      const response = await api.get<{ posts: CommunityPost[] }>('/community/posts', { params })
      posts.value = response.data.posts
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Could not load community posts.'
    } finally {
      loading.value = false
    }
  }

  async function forkPost(slug: string): Promise<ForkResult> {
    const response = await api.post<ForkResult>(`/community/posts/${slug}/fork`)
    return response.data
  }

  return {
    posts,
    loading,
    error,
    currentFilter,
    fetchPosts,
    forkPost,
  }
})
