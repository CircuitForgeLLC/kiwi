<!-- frontend/src/components/CommunityPostCard.vue -->
<template>
  <article class="post-card" :class="`post-type-${post.post_type}`">
    <header class="post-header">
      <span class="post-type-badge" :aria-label="`Post type: ${typeLabel}`">{{ typeLabel }}</span>
      <time class="post-date" :datetime="post.published">{{ formattedDate }}</time>
    </header>

    <h3 class="post-title">{{ post.title }}</h3>

    <p v-if="post.description" class="post-description">{{ post.description }}</p>

    <div v-if="post.dietary_tags.length || post.allergen_flags.length" class="post-tags">
      <span
        v-for="tag in post.dietary_tags"
        :key="tag"
        class="tag tag-dietary"
        :aria-label="`Dietary: ${tag}`"
      >{{ tag }}</span>
      <span
        v-for="flag in post.allergen_flags"
        :key="flag"
        class="tag tag-allergen"
        :aria-label="`Contains: ${flag}`"
      >{{ flag }}</span>
    </div>

    <div v-if="post.post_type === 'plan' && post.slots.length" class="post-slots">
      <span class="slots-summary">
        {{ post.slots.length }} meal{{ post.slots.length !== 1 ? 's' : '' }} planned
      </span>
    </div>

    <div v-if="post.outcome_notes" class="outcome-notes">
      <p class="outcome-label">Notes</p>
      <p class="outcome-text">{{ post.outcome_notes }}</p>
    </div>

    <footer class="post-footer">
      <span class="post-author">by {{ post.pseudonym }}</span>

      <div class="post-actions">
        <button
          v-if="post.post_type === 'plan'"
          class="action-btn fork-btn"
          :disabled="forking"
          :aria-busy="forking"
          @click="$emit('fork', post.slug)"
        >
          {{ forking ? 'Forking…' : 'Fork plan' }}
        </button>
      </div>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CommunityPost } from '../stores/community'

const props = defineProps<{
  post: CommunityPost
  forking?: boolean
}>()

defineEmits<{
  fork: [slug: string]
}>()

const typeLabel = computed(() => ({
  plan: 'Meal Plan',
  recipe_success: 'Recipe Win',
  recipe_blooper: 'Recipe Blooper',
}[props.post.post_type] ?? props.post.post_type))

const formattedDate = computed(() => {
  try {
    return new Date(props.post.published).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  } catch {
    return props.post.published
  }
})
</script>

<style scoped>
.post-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: box-shadow 0.15s;
}
.post-card:hover { box-shadow: 0 2px 8px color-mix(in srgb, var(--color-accent) 12%, transparent); }

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.post-type-badge {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.15rem 0.5rem;
  border-radius: 20px;
  background: var(--color-accent-subtle);
  color: var(--color-accent);
}
.post-type-recipe_blooper .post-type-badge { background: color-mix(in srgb, orange 15%, transparent); color: #b36000; }
.post-type-recipe_success .post-type-badge { background: color-mix(in srgb, green 12%, transparent); color: #2a7a2a; }

.post-date { font-size: 0.75rem; color: var(--color-text-secondary); }

.post-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.3;
}

.post-description { margin: 0; font-size: 0.82rem; color: var(--color-text-secondary); line-height: 1.5; }

.post-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  font-size: 0.68rem;
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}
.tag-dietary { border-color: color-mix(in srgb, green 30%, transparent); color: #2a7a2a; }
.tag-allergen { border-color: color-mix(in srgb, orange 30%, transparent); color: #b36000; }

.slots-summary { font-size: 0.78rem; color: var(--color-text-secondary); }

.outcome-notes { background: var(--color-bg); border-radius: 6px; padding: 0.5rem 0.7rem; }
.outcome-label { margin: 0 0 0.2rem; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: var(--color-text-secondary); }
.outcome-text { margin: 0; font-size: 0.82rem; color: var(--color-text); line-height: 1.5; }

.post-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.25rem;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.post-author { font-size: 0.75rem; color: var(--color-text-secondary); font-style: italic; }

.action-btn {
  font-size: 0.78rem;
  padding: 0.3rem 0.8rem;
  border-radius: 16px;
  border: 1px solid var(--color-accent);
  background: var(--color-accent-subtle);
  color: var(--color-accent);
  cursor: pointer;
  transition: background 0.15s;
}
.action-btn:hover:not(:disabled) { background: var(--color-accent); color: white; }
.action-btn:disabled { opacity: 0.5; cursor: default; }
.action-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
</style>
