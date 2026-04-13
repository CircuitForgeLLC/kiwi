<template>
  <article class="community-post-card" :class="`post-type-${post.post_type}`">
    <!-- Header row: type badge + date -->
    <div class="card-header flex-between gap-sm mb-xs">
      <span
        class="post-type-badge status-badge"
        :class="typeBadgeClass"
        :aria-label="`Post type: ${typeLabel}`"
      >{{ typeLabel }}</span>
      <time
        class="post-date text-xs text-muted"
        :datetime="post.published"
        :title="fullDate"
      >{{ shortDate }}</time>
    </div>

    <!-- Title -->
    <h3 class="post-title text-base font-semibold mb-xs">{{ post.title }}</h3>

    <!-- Author -->
    <p class="post-author text-xs text-muted mb-xs">
      by {{ post.pseudonym }}
    </p>

    <!-- Description (if present) -->
    <p v-if="post.description" class="post-description text-sm text-secondary mb-sm">
      {{ post.description }}
    </p>

    <!-- Dietary tag pills -->
    <div
      v-if="post.dietary_tags.length > 0"
      class="tag-row flex flex-wrap gap-xs mb-sm"
      role="list"
      aria-label="Dietary tags"
    >
      <span
        v-for="tag in post.dietary_tags"
        :key="tag"
        class="status-badge status-success tag-pill"
        role="listitem"
      >{{ tag }}</span>
    </div>

    <!-- Fork button (plan posts only) -->
    <div v-if="post.post_type === 'plan'" class="card-actions mt-sm">
      <button
        class="btn btn-primary btn-sm btn-fork"
        :aria-label="`Fork ${post.title} to my meal plan`"
        @click="$emit('fork', post.slug)"
      >
        Fork to my plan
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CommunityPost } from '../stores/community'

const props = defineProps<{
  post: CommunityPost
}>()

defineEmits<{
  fork: [slug: string]
}>()

const typeLabel = computed(() => {
  switch (props.post.post_type) {
    case 'plan':           return 'Meal Plan'
    case 'recipe_success': return 'Success'
    case 'recipe_blooper': return 'Blooper'
    default:               return props.post.post_type
  }
})

const typeBadgeClass = computed(() => {
  switch (props.post.post_type) {
    case 'plan':           return 'status-info'
    case 'recipe_success': return 'status-success'
    case 'recipe_blooper': return 'status-warning'
    default:               return 'status-info'
  }
})

const shortDate = computed(() => {
  try {
    return new Date(props.post.published).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return ''
  }
})

const fullDate = computed(() => {
  try {
    return new Date(props.post.published).toLocaleString()
  } catch {
    return props.post.published
  }
})
</script>

<style scoped>
.community-post-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  transition: box-shadow 0.18s ease;
}

.community-post-card:hover {
  box-shadow: var(--shadow-md);
}

.post-type-plan           { border-left: 3px solid var(--color-info); }
.post-type-recipe_success { border-left: 3px solid var(--color-success); }
.post-type-recipe_blooper { border-left: 3px solid var(--color-warning); }

.card-header {
  align-items: center;
}

.post-type-badge,
.post-date {
  flex-shrink: 0;
}

.post-title {
  margin: 0;
  color: var(--color-text-primary);
  line-height: 1.3;
}

.post-author,
.post-description {
  margin: 0;
}

.post-description {
  line-height: 1.5;
}

.tag-pill {
  text-transform: lowercase;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
}

.btn-fork {
  min-width: 120px;
}

@media (max-width: 480px) {
  .community-post-card {
    padding: var(--spacing-sm);
    border-radius: var(--radius-md);
  }

  .btn-fork {
    width: 100%;
  }
}
</style>
