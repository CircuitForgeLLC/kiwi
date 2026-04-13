<!-- frontend/src/components/CommunityFeedPanel.vue -->
<template>
  <div class="community-feed-panel">
    <!-- Filter bar -->
    <div class="filter-bar" role="toolbar" aria-label="Filter community posts">
      <button
        v-for="f in FILTERS"
        :key="f.value ?? 'all'"
        class="filter-btn"
        :class="{ active: activeFilter === f.value }"
        :aria-pressed="activeFilter === f.value"
        @click="setFilter(f.value)"
      >{{ f.label }}</button>
    </div>

    <!-- Results count (aria-live so screen readers announce changes) -->
    <p
      class="results-summary"
      aria-live="polite"
      aria-atomic="true"
    >
      <template v-if="!loading">
        {{ posts.length }} post{{ posts.length !== 1 ? 's' : '' }}
        <template v-if="activeFilter"> · {{ activeFilterLabel }}</template>
      </template>
    </p>

    <!-- Publish button (visible when plan is active) -->
    <div class="publish-row" v-if="activePlanId">
      <button class="publish-btn" @click="showPublish = true">
        Share this week's plan
      </button>
    </div>

    <!-- Error state -->
    <div v-if="error" class="feed-error" role="alert">
      <p>{{ error }}</p>
      <button class="retry-btn" @click="communityStore.clearError(); communityStore.loadPosts(true)">
        Try again
      </button>
    </div>

    <!-- Feed -->
    <div v-else-if="posts.length" class="feed-list">
      <CommunityPostCard
        v-for="post in posts"
        :key="post.slug"
        :post="post"
        :forking="forkingSlug === post.slug"
        @fork="onFork"
      />

      <button
        v-if="hasMore && !loading"
        class="load-more-btn"
        @click="communityStore.loadPosts()"
      >
        Load more
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-else-if="loading" class="feed-loading" aria-busy="true" aria-label="Loading posts">
      <div v-for="i in 3" :key="i" class="skeleton-card"></div>
    </div>

    <!-- Empty state -->
    <div v-else-if="isEmpty" class="feed-empty">
      <p>No community posts yet.</p>
      <p class="feed-empty-hint">Be the first to share a meal plan!</p>
    </div>

    <!-- Fork success toast -->
    <div
      v-if="forkSuccess"
      class="fork-toast"
      role="status"
      aria-live="polite"
    >
      Plan forked into your week starting {{ forkSuccess.week_start }}
    </div>

    <!-- Publish modal -->
    <PublishPlanModal
      v-if="showPublish"
      :plan-id="activePlanId"
      @close="showPublish = false"
      @published="onPublished"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useCommunityStore } from '../stores/community'
import CommunityPostCard from './CommunityPostCard.vue'
import PublishPlanModal from './PublishPlanModal.vue'

const props = defineProps<{
  activePlanId?: number | null
}>()

const communityStore = useCommunityStore()
const { posts, loading, error, hasMore, isEmpty } = storeToRefs(communityStore)

const activeFilter = ref<'plan' | 'recipe_success' | 'recipe_blooper' | null>(null)
const showPublish = ref(false)
const forkingSlug = ref<string | null>(null)
const forkSuccess = ref<{ plan_id: number; week_start: string } | null>(null)

const FILTERS = [
  { label: 'All',      value: null },
  { label: 'Plans',    value: 'plan' as const },
  { label: 'Wins',     value: 'recipe_success' as const },
  { label: 'Bloopers', value: 'recipe_blooper' as const },
] as const

const activeFilterLabel = computed(
  () => FILTERS.find(f => f.value === activeFilter.value)?.label ?? ''
)

onMounted(() => communityStore.loadPosts(true))

function setFilter(value: typeof activeFilter.value) {
  activeFilter.value = value
  communityStore.setFilter(value)
}

async function onFork(slug: string) {
  forkingSlug.value = slug
  forkSuccess.value = null
  const result = await communityStore.forkPost(slug)
  forkingSlug.value = null
  if (result) {
    forkSuccess.value = result
    setTimeout(() => { forkSuccess.value = null }, 4000)
  }
}

function onPublished() {
  showPublish.value = false
  communityStore.loadPosts(true)
}
</script>

<style scoped>
.community-feed-panel { display: flex; flex-direction: column; gap: 0.75rem; }

.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-btn {
  font-size: 0.78rem;
  padding: 0.25rem 0.75rem;
  border-radius: 16px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.filter-btn.active, .filter-btn:hover {
  background: var(--color-accent-subtle);
  color: var(--color-accent);
  border-color: var(--color-accent);
}
.filter-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.results-summary { font-size: 0.75rem; color: var(--color-text-secondary); min-height: 1.1em; margin: 0; }

.publish-row { display: flex; }
.publish-btn {
  font-size: 0.82rem;
  padding: 0.4rem 1.1rem;
  border-radius: 20px;
  background: var(--color-accent);
  color: white;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s;
}
.publish-btn:hover { opacity: 0.88; }
.publish-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.feed-list { display: flex; flex-direction: column; gap: 0.75rem; }

.load-more-btn {
  align-self: center;
  font-size: 0.8rem;
  padding: 0.4rem 1.2rem;
  border-radius: 16px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
}
.load-more-btn:hover { border-color: var(--color-accent); color: var(--color-accent); }

.feed-loading { display: flex; flex-direction: column; gap: 0.75rem; }
.skeleton-card {
  height: 110px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--color-surface) 25%, var(--color-border) 50%, var(--color-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@media (prefers-reduced-motion: reduce) { .skeleton-card { animation: none; background: var(--color-surface); } }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

.feed-empty { text-align: center; padding: 2rem 0; color: var(--color-text-secondary); }
.feed-empty p { margin: 0.25rem 0; }
.feed-empty-hint { font-size: 0.82rem; opacity: 0.7; }

.feed-error { padding: 0.75rem 1rem; border-radius: 8px; background: color-mix(in srgb, red 8%, transparent); border: 1px solid color-mix(in srgb, red 20%, transparent); }
.feed-error p { margin: 0 0 0.5rem; font-size: 0.85rem; color: var(--color-text); }
.retry-btn { font-size: 0.78rem; padding: 0.3rem 0.8rem; border-radius: 14px; border: 1px solid currentColor; background: none; cursor: pointer; color: var(--color-accent); }

.fork-toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-accent);
  color: white;
  padding: 0.6rem 1.2rem;
  border-radius: 20px;
  font-size: 0.85rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  z-index: 100;
  pointer-events: none;
}
</style>
