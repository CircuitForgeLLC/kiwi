<template>
  <Teleport to="body">
    <div
      class="modal-overlay"
      @click.self="$emit('close')"
    >
      <div
        ref="dialogRef"
        class="modal-panel card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="publish-outcome-title"
        tabindex="-1"
      >
        <!-- Header -->
        <div class="flex-between mb-md">
          <h2 id="publish-outcome-title" class="section-title">
            Share a recipe story
            <span v-if="recipeName" class="recipe-name-hint text-sm text-muted">
              -- {{ recipeName }}
            </span>
          </h2>
          <button
            class="btn-close"
            aria-label="Close"
            @click="$emit('close')"
          >&#x2715;</button>
        </div>

        <!-- Post type selector -->
        <div class="form-group">
          <fieldset class="type-fieldset">
            <legend class="form-label">What kind of story is this?</legend>
            <div class="type-toggle flex gap-sm">
              <button
                ref="firstFocusRef"
                :class="['btn', 'type-btn', postType === 'recipe_success' ? 'type-btn-active' : 'btn-secondary']"
                :aria-pressed="postType === 'recipe_success'"
                @click="postType = 'recipe_success'"
              >
                Success
              </button>
              <button
                :class="['btn', 'type-btn', postType === 'recipe_blooper' ? 'type-btn-active type-btn-blooper' : 'btn-secondary']"
                :aria-pressed="postType === 'recipe_blooper'"
                @click="postType = 'recipe_blooper'"
              >
                Blooper
              </button>
            </div>
          </fieldset>
        </div>

        <!-- Title field -->
        <div class="form-group">
          <label class="form-label" for="outcome-title">
            Title <span class="required-mark" aria-hidden="true">*</span>
          </label>
          <input
            id="outcome-title"
            v-model="title"
            class="form-input"
            type="text"
            maxlength="200"
            placeholder="e.g. Perfect crust on the first try"
            autocomplete="off"
            required
          />
          <span class="form-hint char-counter" aria-live="polite" aria-atomic="true">
            {{ title.length }}/200
          </span>
        </div>

        <!-- Outcome notes field -->
        <div class="form-group">
          <label class="form-label" for="outcome-notes">
            What happened? <span class="optional-mark">(optional)</span>
          </label>
          <textarea
            id="outcome-notes"
            v-model="outcomeNotes"
            class="form-input form-textarea"
            maxlength="2000"
            rows="4"
            placeholder="Describe what you tried, what worked, or what went sideways."
          />
          <span class="form-hint char-counter" aria-live="polite" aria-atomic="true">
            {{ outcomeNotes.length }}/2000
          </span>
        </div>

        <!-- Pseudonym field -->
        <div class="form-group">
          <label class="form-label" for="outcome-pseudonym">
            Community name <span class="optional-mark">(optional)</span>
          </label>
          <input
            id="outcome-pseudonym"
            v-model="pseudonymName"
            class="form-input"
            type="text"
            maxlength="40"
            placeholder="Leave blank to use your existing handle"
            autocomplete="nickname"
          />
          <span class="form-hint">How you appear on posts -- not your real name or email.</span>
        </div>

        <!-- Submission feedback (aria-live region, always rendered) -->
        <div
          class="feedback-region"
          aria-live="polite"
          aria-atomic="true"
        >
          <p v-if="submitError" class="feedback-error text-sm" role="alert">{{ submitError }}</p>
          <p v-if="submitSuccess" class="feedback-success text-sm">{{ submitSuccess }}</p>
        </div>

        <!-- Footer actions -->
        <div class="modal-footer flex gap-sm">
          <button
            class="btn btn-primary"
            :disabled="submitting || !title.trim()"
            :aria-busy="submitting"
            @click="onSubmit"
          >
            <span v-if="submitting" class="spinner spinner-sm" aria-hidden="true"></span>
            {{ submitting ? 'Publishing...' : 'Publish' }}
          </button>
          <button class="btn btn-secondary" @click="$emit('close')">
            Cancel
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useCommunityStore } from '../stores/community'
import type { PublishPayload } from '../stores/community'

const props = defineProps<{
  recipeId: number | null
  recipeName: string | null
  visible?: boolean
}>()

const emit = defineEmits<{
  close: []
  published: [payload: { slug: string }]
}>()

const store = useCommunityStore()

const postType = ref<'recipe_success' | 'recipe_blooper'>('recipe_success')
const title = ref('')
const outcomeNotes = ref('')
const pseudonymName = ref('')
const submitting = ref(false)
const submitError = ref<string | null>(null)
const submitSuccess = ref<string | null>(null)

const dialogRef = ref<HTMLElement | null>(null)
const firstFocusRef = ref<HTMLButtonElement | null>(null)
let previousFocus: HTMLElement | null = null

function getFocusables(): HTMLElement[] {
  if (!dialogRef.value) return []
  return Array.from(
    dialogRef.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  )
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  if (e.key !== 'Tab') return
  // Only intercept Tab when focus is inside this dialog
  if (!dialogRef.value?.contains(document.activeElement)) return

  const focusables = getFocusables()
  if (focusables.length === 0) return
  const first = focusables[0]!
  const last = focusables[focusables.length - 1]!

  if (e.shiftKey) {
    if (document.activeElement === first) {
      e.preventDefault()
      last.focus()
    }
  } else {
    if (document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
}

onMounted(() => {
  previousFocus = document.activeElement as HTMLElement
  document.addEventListener('keydown', handleKeydown)
  nextTick(() => {
    (firstFocusRef.value ?? dialogRef.value)?.focus()
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  previousFocus?.focus()
})

async function onSubmit() {
  submitError.value = null
  submitSuccess.value = null

  if (!title.value.trim()) return

  const payload: PublishPayload = {
    post_type: postType.value,
    title: title.value.trim(),
  }
  if (outcomeNotes.value.trim()) payload.outcome_notes = outcomeNotes.value.trim()
  if (pseudonymName.value.trim()) payload.pseudonym_name = pseudonymName.value.trim()
  if (props.recipeId != null) payload.recipe_id = props.recipeId

  submitting.value = true
  try {
    const result = await store.publishPost(payload)
    submitSuccess.value = 'Your story has been posted.'
    nextTick(() => {
      emit('published', { slug: result.slug })
    })
  } catch (err: unknown) {
    submitError.value = err instanceof Error ? err.message : 'Could not publish. Please try again.'
  } finally {
    submitting.value = false
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
  z-index: 400;
  padding: var(--spacing-md);
}

.modal-panel {
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  padding: var(--spacing-xs);
  line-height: 1;
  border-radius: var(--radius-sm);
}

.btn-close:hover {
  color: var(--color-text-primary);
}

.recipe-name-hint {
  font-style: italic;
}

.required-mark {
  color: var(--color-error);
  margin-left: 2px;
}

.optional-mark {
  font-weight: 400;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.type-fieldset {
  border: none;
  padding: 0;
  margin: 0;
}

.type-toggle {
  flex-wrap: wrap;
}

.type-btn {
  min-width: 100px;
}

.type-btn-active {
  background: var(--color-success);
  color: white;
  border-color: var(--color-success);
  font-weight: 700;
}

.type-btn-active.type-btn-blooper {
  background: var(--color-warning);
  border-color: var(--color-warning);
  color: var(--color-text-primary);
}

.char-counter {
  text-align: right;
  display: block;
  margin-top: var(--spacing-xs);
}

.feedback-region {
  min-height: 1.4rem;
  margin-bottom: var(--spacing-xs);
}

.feedback-error {
  color: var(--color-error);
  margin: 0;
}

.feedback-success {
  color: var(--color-success);
  margin: 0;
}

.modal-footer {
  justify-content: flex-start;
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border);
  margin-top: var(--spacing-md);
  flex-wrap: wrap;
}

@media (max-width: 480px) {
  .modal-panel {
    max-height: 95vh;
  }

  .modal-footer {
    flex-direction: column-reverse;
  }

  .modal-footer .btn {
    width: 100%;
  }
}
</style>
