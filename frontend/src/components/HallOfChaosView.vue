<template>
  <div class="hall-of-chaos-overlay" role="dialog" aria-modal="true" aria-label="Hall of Chaos">

    <!-- Header -->
    <div class="chaos-header">
      <h2 class="chaos-title">HALL OF CHAOS</h2>
      <p class="chaos-subtitle text-sm">
        Chaos Level: <span class="chaos-level">{{ chaosLevel }}</span>
      </p>
      <button
        class="btn btn-secondary chaos-exit-btn"
        aria-label="Exit Hall of Chaos"
        @click="$emit('close')"
      >
        Escape the chaos
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="chaos-loading text-center text-secondary" aria-busy="true">
      Assembling the chaos...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="chaos-empty text-center text-secondary" role="alert">
      The chaos is temporarily indisposed.
    </div>

    <!-- Empty -->
    <div v-else-if="posts.length === 0" class="chaos-empty text-center text-secondary">
      <p>No bloopers yet. Be the first to make a glorious mistake.</p>
    </div>

    <!-- Blooper cards -->
    <div v-else class="chaos-grid" aria-label="Blooper posts">
      <article
        v-for="(post, index) in posts"
        :key="post.slug"
        class="chaos-card"
        :class="`chaos-card--tilt-${(index % 5) + 1}`"
        :style="{ '--chaos-border-color': borderColors[index % borderColors.length] }"
      >
        <p class="chaos-card-author text-xs text-muted">{{ post.pseudonym }}</p>
        <h3 class="chaos-card-title text-base font-semibold">{{ post.title }}</h3>
        <p v-if="post.outcome_notes" class="chaos-card-notes text-sm text-secondary">
          {{ post.outcome_notes }}
        </p>
        <p v-if="post.recipe_name" class="chaos-card-recipe text-xs text-muted mt-xs">
          Recipe: {{ post.recipe_name }}
        </p>
      </article>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../services/api'
import type { CommunityPost } from '../stores/community'

defineEmits<{ close: [] }>()

const posts = ref<CommunityPost[]>([])
const chaosLevel = ref(0)
const loading = ref(true)
const error = ref(false)

// CSS custom property strings -- no hardcoded hex
const borderColors = [
  'var(--color-warning)',
  'var(--color-info)',
  'var(--color-success)',
  'var(--color-error)',
  'var(--color-warning)',
]

onMounted(async () => {
  try {
    const response = await api.get<{ posts: CommunityPost[]; chaos_level: number }>(
      '/community/hall-of-chaos'
    )
    posts.value = response.data.posts
    chaosLevel.value = response.data.chaos_level
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.hall-of-chaos-overlay {
  position: absolute;
  inset: 0;
  z-index: 200;
  background: var(--color-bg-primary);
  overflow-y: auto;
  padding: var(--spacing-md);
  border-radius: var(--radius-lg);
}

.chaos-header {
  text-align: center;
  margin-bottom: var(--spacing-lg);
}

.chaos-title {
  font-size: 2rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  color: var(--color-warning);
  margin: 0 0 var(--spacing-xs);
  text-transform: uppercase;
}

.chaos-subtitle {
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-sm);
}

.chaos-level {
  font-weight: 700;
  color: var(--color-warning);
}

.chaos-exit-btn {
  font-size: var(--font-size-xs);
}

.chaos-loading,
.chaos-empty {
  padding: var(--spacing-xl);
}

.chaos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--spacing-md);
  padding-bottom: var(--spacing-lg);
}

/* Static tilts applied once at render -- not animations, no reduced-motion concern */
.chaos-card {
  background: var(--color-bg-card);
  border: 2px solid var(--chaos-border-color, var(--color-border));
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
}

.chaos-card--tilt-1 { transform: rotate(-3deg); }
.chaos-card--tilt-2 { transform: rotate(2deg); }
.chaos-card--tilt-3 { transform: rotate(-1.5deg); }
.chaos-card--tilt-4 { transform: rotate(4deg); }
.chaos-card--tilt-5 { transform: rotate(-4.5deg); }

.chaos-card-title {
  margin: var(--spacing-xs) 0;
  color: var(--color-text-primary);
}

.chaos-card-author,
.chaos-card-notes,
.chaos-card-recipe {
  margin: 0;
}

@media (max-width: 480px) {
  .chaos-grid {
    grid-template-columns: 1fr;
  }

  .chaos-card--tilt-1,
  .chaos-card--tilt-2,
  .chaos-card--tilt-3,
  .chaos-card--tilt-4,
  .chaos-card--tilt-5 {
    transform: none;
  }
}
</style>
