<template>
  <div class="community-feed-panel">

    <!-- Filter tabs: All / Plans / Successes / Bloopers -->
    <div role="tablist" aria-label="Community post filters" class="filter-bar flex gap-xs mb-md">
      <button
        v-for="f in filters"
        :key="f.id"
        role="tab"
        :aria-selected="activeFilter === f.id"
        :tabindex="activeFilter === f.id ? 0 : -1"
        :class="['btn', 'tab-btn', activeFilter === f.id ? 'btn-primary' : 'btn-secondary']"
        @click="setFilter(f.id)"
        @keydown="onFilterKeydown"
        @pointerdown="f.id === 'recipe_blooper' ? onBlooperPointerDown($event) : undefined"
        @pointerup="f.id === 'recipe_blooper' ? onBlooperPointerCancel() : undefined"
        @pointerleave="f.id === 'recipe_blooper' ? onBlooperPointerCancel() : undefined"
      >{{ f.label }}</button>
    </div>

    <!-- Share a plan action row -->
    <div class="action-row flex-between mb-sm">
      <button
        class="btn btn-secondary btn-sm share-plan-btn"
        aria-haspopup="dialog"
        @click="showPublishPlan = true"
      >
        Share a plan
      </button>
    </div>

    <!-- Loading skeletons -->
    <div
      v-if="store.loading"
      class="skeleton-list flex-col gap-sm"
      aria-busy="true"
      aria-label="Loading posts"
    >
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <div class="skeleton-line skeleton-line-short"></div>
        <div class="skeleton-line skeleton-line-long mt-xs"></div>
        <div class="skeleton-line skeleton-line-med mt-xs"></div>
      </div>
    </div>

    <!-- Error state -->
    <div
      v-else-if="store.error"
      class="error-state card"
      role="alert"
    >
      <p class="text-sm text-secondary mb-sm">{{ store.error }}</p>
      <button class="btn btn-secondary btn-sm" @click="retry">
        Try again
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="store.posts.length === 0"
      class="empty-state card text-center"
    >
      <p class="text-secondary mb-xs">No posts yet</p>
      <p class="text-sm text-muted">Be the first to share a meal plan or recipe story.</p>
    </div>

    <!-- Post list -->
    <div v-else class="post-list flex-col gap-sm">
      <CommunityPostCard
        v-for="post in store.posts"
        :key="post.slug"
        :post="post"
        @fork="handleFork"
      />
    </div>

    <!-- Fork success toast -->
    <Transition name="toast-fade">
      <div
        v-if="forkFeedback"
        class="fork-toast status-badge status-success"
        role="status"
        aria-live="polite"
      >
        {{ forkFeedback }}
      </div>
    </Transition>

    <!-- Fork error toast -->
    <Transition name="toast-fade">
      <div
        v-if="forkError"
        class="fork-toast status-badge status-error"
        role="alert"
        aria-live="assertive"
      >
        {{ forkError }}
      </div>
    </Transition>

    <!-- Publish plan modal -->
    <PublishPlanModal
      v-if="showPublishPlan"
      :plan="null"
      @close="showPublishPlan = false"
      @published="onPlanPublished"
    />

    <!-- Hall of Chaos easter egg: hold Bloopers tab for 800ms -->
    <HallOfChaosView
      v-if="showHallOfChaos"
      @close="showHallOfChaos = false"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useCommunityStore } from '../stores/community'
import CommunityPostCard from './CommunityPostCard.vue'
import PublishPlanModal from './PublishPlanModal.vue'
import HallOfChaosView from './HallOfChaosView.vue'

const emit = defineEmits<{
  'plan-forked': [payload: { plan_id: number; week_start: string }]
}>()

const store = useCommunityStore()

const activeFilter = ref('all')
const showPublishPlan = ref(false)
const showHallOfChaos = ref(false)
let blooperHoldTimer: ReturnType<typeof setTimeout> | null = null

function onBlooperPointerDown(_e: PointerEvent) {
  blooperHoldTimer = setTimeout(() => {
    showHallOfChaos.value = true
    blooperHoldTimer = null
  }, 800)
}

function onBlooperPointerCancel() {
  if (blooperHoldTimer !== null) {
    clearTimeout(blooperHoldTimer)
    blooperHoldTimer = null
  }
}

const filters = [
  { id: 'all',            label: 'All' },
  { id: 'plan',           label: 'Plans' },
  { id: 'recipe_success', label: 'Successes' },
  { id: 'recipe_blooper', label: 'Bloopers' },
]

const filterIds = filters.map((f) => f.id)

function onFilterKeydown(e: KeyboardEvent) {
  const current = filterIds.indexOf(activeFilter.value)
  let next = current
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    next = (current + 1) % filterIds.length
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    next = (current - 1 + filterIds.length) % filterIds.length
  } else {
    return
  }
  setFilter(filterIds[next]!)
  // Move DOM focus to the newly active tab per ARIA tablist pattern
  const bar = (e.currentTarget as HTMLElement).closest('[role="tablist"]')
  const buttons = bar?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
  buttons?.[next]?.focus()
}

async function setFilter(filterId: string) {
  activeFilter.value = filterId
  await store.fetchPosts(filterId === 'all' ? undefined : filterId)
}

async function retry() {
  await store.fetchPosts(activeFilter.value === 'all' ? undefined : activeFilter.value)
}

const forkFeedback = ref<string | null>(null)
const forkError = ref<string | null>(null)

function showToast(msg: string, type: 'success' | 'error') {
  if (type === 'success') {
    forkFeedback.value = msg
    setTimeout(() => { forkFeedback.value = null }, 3000)
  } else {
    forkError.value = msg
    setTimeout(() => { forkError.value = null }, 4000)
  }
}

async function handleFork(slug: string) {
  try {
    const result = await store.forkPost(slug)
    showToast('Plan added to your week.', 'success')
    emit('plan-forked', { plan_id: result.plan_id, week_start: result.week_start })
  } catch (err: unknown) {
    showToast(err instanceof Error ? err.message : 'Could not fork this plan.', 'error')
  }
}

function onPlanPublished(_payload: { slug: string }) {
  showPublishPlan.value = false
  store.fetchPosts(activeFilter.value === 'all' ? undefined : activeFilter.value)
}

onMounted(async () => {
  if (store.posts.length === 0) {
    await store.fetchPosts()
  }
})
</script>

<style scoped>
.community-feed-panel {
  position: relative;
}

.filter-bar {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--spacing-sm);
}

.tab-btn {
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  border-bottom: none;
}

.action-row {
  padding: var(--spacing-xs) 0;
}

.share-plan-btn {
  font-size: var(--font-size-xs);
}

/* Loading skeletons */
.skeleton-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  overflow: hidden;
}

.skeleton-line {
  height: 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-elevated);
  animation: shimmer 1.4s ease-in-out infinite;
}

.skeleton-line-short { width: 35%; }
.skeleton-line-med   { width: 60%; }
.skeleton-line-long  { width: 90%; }

@keyframes shimmer {
  0%   { opacity: 0.6; }
  50%  { opacity: 1.0; }
  100% { opacity: 0.6; }
}

/* Empty / error states */
.empty-state {
  padding: var(--spacing-xl) var(--spacing-lg);
}

.error-state {
  padding: var(--spacing-md);
}

/* Post list */
.post-list {
  padding-top: var(--spacing-sm);
}

/* Toast */
.fork-toast {
  position: fixed;
  bottom: calc(72px + var(--spacing-md));
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  white-space: nowrap;
  box-shadow: var(--shadow-lg);
}

@media (min-width: 769px) {
  .fork-toast {
    bottom: var(--spacing-lg);
  }
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-line {
    animation: none;
    opacity: 0.7;
  }

  .toast-fade-enter-active,
  .toast-fade-leave-active {
    transition: none;
  }
}
</style>
