<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="$emit('close')">
      <div ref="dialogRef" class="modal-panel card" role="dialog" aria-modal="true" aria-label="Save recipe" tabindex="-1">
        <div class="flex-between mb-md">
          <h3 class="section-title">{{ isEditing ? 'Edit saved recipe' : 'Save recipe' }}</h3>
          <button class="btn-close" @click="$emit('close')" aria-label="Close">✕</button>
        </div>

        <p class="recipe-title-label text-sm text-secondary mb-md">{{ recipeTitle }}</p>

        <!-- Star rating -->
        <div class="form-group">
          <label id="rating-label" class="form-label">Rating</label>
          <div role="group" aria-labelledby="rating-label" class="stars-row flex gap-xs">
            <button
              v-for="n in 5"
              :key="n"
              class="star-btn"
              :class="{ filled: n <= (hoverRating ?? localRating ?? 0) }"
              @mouseenter="hoverRating = n"
              @mouseleave="hoverRating = null"
              @click="toggleRating(n)"
              :aria-label="`${n} star${n !== 1 ? 's' : ''}`"
              :aria-pressed="n <= (localRating ?? 0)"
            >★</button>
            <button
              v-if="localRating !== null"
              class="btn btn-secondary btn-xs ml-xs"
              @click="localRating = null"
            >Clear</button>
          </div>
        </div>

        <!-- Notes -->
        <div class="form-group">
          <label class="form-label" for="save-notes">Notes</label>
          <textarea
            id="save-notes"
            class="form-input"
            v-model="localNotes"
            rows="3"
            placeholder="e.g. loved with extra garlic, halve the salt next time"
          />
        </div>

        <!-- Style tags -->
        <div class="form-group">
          <label class="form-label">Style tags</label>
          <div class="tags-wrap flex flex-wrap gap-xs mb-xs">
            <span
              v-for="tag in localTags"
              :key="tag"
              class="tag-chip status-badge status-info"
            >
              {{ tag }}
              <button class="chip-remove" @click="removeTag(tag)" :aria-label="`Remove tag: ${tag}`">×</button>
            </span>
          </div>
          <input
            class="form-input"
            v-model="tagInput"
            placeholder="e.g. comforting, hands-off, quick — press Enter or comma"
            @keydown="onTagKey"
            @blur="commitTagInput"
          />
          <div class="tag-suggestions flex flex-wrap gap-xs mt-xs">
            <button
              v-for="s in unusedSuggestions"
              :key="s"
              class="btn btn-secondary btn-xs"
              @click="addTag(s)"
            >+ {{ s }}</button>
          </div>
        </div>

        <div class="flex gap-sm mt-md">
          <button class="btn btn-primary" :disabled="saving" @click="submit">
            {{ saving ? 'Saving…' : (isEditing ? 'Update' : 'Save') }}
          </button>
          <button v-if="isEditing" class="btn btn-danger" @click="$emit('unsave')">Remove</button>
          <button class="btn btn-secondary" @click="$emit('close')">Cancel</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useSavedRecipesStore } from '../stores/savedRecipes'

const SUGGESTED_TAGS = [
  'comforting', 'light', 'spicy', 'umami', 'sweet', 'savory', 'rich',
  'crispy', 'creamy', 'hearty', 'quick', 'hands-off', 'meal-prep-friendly',
  'fancy', 'one-pot',
]

const props = defineProps<{
  recipeId: number
  recipeTitle: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
  (e: 'unsave'): void
}>()

const dialogRef = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  previousFocus = document.activeElement as HTMLElement
  document.addEventListener('keydown', handleKeydown)
  nextTick(() => {
    const focusable = dialogRef.value?.querySelector<HTMLElement>(
      'button:not([disabled]), input, textarea'
    )
    ;(focusable ?? dialogRef.value)?.focus()
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  previousFocus?.focus()
})

const store = useSavedRecipesStore()
const existing = computed(() => store.getSaved(props.recipeId))
const isEditing = computed(() => !!existing.value)

const localRating = ref<number | null>(existing.value?.rating ?? null)
const localNotes = ref<string>(existing.value?.notes ?? '')
const localTags = ref<string[]>([...(existing.value?.style_tags ?? [])])
const hoverRating = ref<number | null>(null)
const tagInput = ref('')
const saving = ref(false)

const unusedSuggestions = computed(() =>
  SUGGESTED_TAGS.filter((s) => !localTags.value.includes(s))
)

function toggleRating(n: number) {
  localRating.value = localRating.value === n ? null : n
}

function addTag(tag: string) {
  const clean = tag.trim().toLowerCase()
  if (clean && !localTags.value.includes(clean)) {
    localTags.value = [...localTags.value, clean]
  }
}

function removeTag(tag: string) {
  localTags.value = localTags.value.filter((t) => t !== tag)
}

function commitTagInput() {
  if (tagInput.value.trim()) {
    addTag(tagInput.value)
    tagInput.value = ''
  }
}

function onTagKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    commitTagInput()
  }
}

async function submit() {
  saving.value = true
  try {
    if (isEditing.value) {
      await store.update(props.recipeId, {
        notes: localNotes.value || null,
        rating: localRating.value,
        style_tags: localTags.value,
      })
    } else {
      await store.save(props.recipeId, localNotes.value || undefined, localRating.value ?? undefined)
      if (localTags.value.length > 0 || localNotes.value) {
        await store.update(props.recipeId, {
          notes: localNotes.value || null,
          rating: localRating.value,
          style_tags: localTags.value,
        })
      }
    }
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
  padding: var(--spacing-md);
}

.modal-panel {
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
}

.recipe-title-label {
  font-style: italic;
}

.stars-row {
  align-items: center;
}

.star-btn {
  background: none;
  border: none;
  font-size: 1.6rem;
  color: var(--color-border);
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.1s ease, transform 0.1s ease;
}

.star-btn.filled {
  color: var(--color-warning);
}

.star-btn:hover {
  transform: scale(1.15);
}

.btn-xs {
  padding: 2px var(--spacing-xs);
  font-size: var(--font-size-xs, 0.75rem);
}

.btn-danger {
  background: var(--color-error);
  color: white;
  border-color: var(--color-error);
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.chip-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
  opacity: 0.7;
  padding: 0;
}

.chip-remove:hover {
  opacity: 1;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  padding: var(--spacing-xs);
  line-height: 1;
}

.btn-close:hover {
  color: var(--color-text-primary);
}
</style>
