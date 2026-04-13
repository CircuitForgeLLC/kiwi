<!-- frontend/src/components/PublishPlanModal.vue -->
<!-- Publish a meal plan to the community feed.
     Pseudonym setup is inline (pre-populated, feels like invitation).
     Focus-trapped per a11y audit. No countdown on delete-undo. -->
<template>
  <div
    class="modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="publish-modal-title"
    @keydown.esc="$emit('close')"
    ref="backdropEl"
    @click.self="$emit('close')"
  >
    <div class="modal-card" ref="cardEl">
      <header class="modal-header">
        <h2 id="publish-modal-title" class="modal-title">Share this week's plan</h2>
        <button class="close-btn" aria-label="Close" @click="$emit('close')">×</button>
      </header>

      <div class="modal-body">
        <div class="field">
          <label for="plan-title" class="field-label">Title</label>
          <input
            id="plan-title"
            v-model="title"
            class="field-input"
            type="text"
            placeholder="e.g. Pasta Week"
            maxlength="120"
            required
            ref="firstFocusEl"
          />
        </div>

        <div class="field">
          <label for="plan-description" class="field-label">Description <span class="optional">(optional)</span></label>
          <textarea
            id="plan-description"
            v-model="description"
            class="field-input field-textarea"
            placeholder="What makes this week special?"
            maxlength="400"
            rows="3"
          />
        </div>

        <div class="field">
          <label for="pseudonym" class="field-label">
            Your community name
            <span class="field-hint">How you appear on posts — not your real name or email</span>
          </label>
          <input
            id="pseudonym"
            v-model="pseudonymName"
            class="field-input"
            type="text"
            placeholder="e.g. PastaWitch"
            maxlength="40"
          />
          <p v-if="pseudonymError" class="field-error" role="alert">{{ pseudonymError }}</p>
        </div>

        <p v-if="error" class="submit-error" role="alert">{{ error }}</p>
      </div>

      <footer class="modal-footer">
        <button class="cancel-btn" @click="$emit('close')">Cancel</button>
        <button
          class="publish-btn"
          :disabled="submitting || !title.trim()"
          :aria-busy="submitting"
          @click="onSubmit"
        >
          {{ submitting ? 'Publishing…' : 'Publish' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useCommunityStore } from '../stores/community'

const props = defineProps<{
  planId?: number | null
}>()

const emit = defineEmits<{
  close: []
  published: []
}>()

const communityStore = useCommunityStore()

const title = ref('')
const description = ref('')
const pseudonymName = ref('')
const pseudonymError = ref('')
const submitting = ref(false)
const error = ref('')

const backdropEl = ref<HTMLElement | null>(null)
const cardEl = ref<HTMLElement | null>(null)
const firstFocusEl = ref<HTMLInputElement | null>(null)

onMounted(() => {
  firstFocusEl.value?.focus()
  document.addEventListener('keydown', trapFocus)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', trapFocus)
})

function trapFocus(e: KeyboardEvent) {
  if (e.key !== 'Tab' || !cardEl.value) return
  const focusables = cardEl.value.querySelectorAll<HTMLElement>(
    'button, input, textarea, [tabindex]:not([tabindex="-1"])'
  )
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus() }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}

async function onSubmit() {
  pseudonymError.value = ''
  error.value = ''

  if (pseudonymName.value && pseudonymName.value.includes('@')) {
    pseudonymError.value = 'Community name must not contain "@" — use a display name, not an email.'
    return
  }

  submitting.value = true
  const result = await communityStore.publishPost({
    post_type: 'plan',
    title: title.value.trim(),
    description: description.value.trim() || undefined,
    pseudonym_name: pseudonymName.value.trim() || undefined,
  })
  submitting.value = false

  if (result) {
    emit('published')
  } else {
    error.value = communityStore.error ?? 'Publish failed. Please try again.'
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 200;
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}

.modal-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0,0,0,0.22);
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 1rem 1.2rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}
.modal-title { margin: 0; font-size: 1rem; font-weight: 600; }
.close-btn {
  background: none; border: none; font-size: 1.4rem; cursor: pointer;
  color: var(--color-text-secondary); line-height: 1; padding: 0 0.2rem;
}
.close-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.modal-body { padding: 1rem 1.2rem; display: flex; flex-direction: column; gap: 0.9rem; }

.field { display: flex; flex-direction: column; gap: 0.3rem; }
.field-label { font-size: 0.82rem; font-weight: 600; color: var(--color-text); }
.optional { font-weight: 400; color: var(--color-text-secondary); }
.field-hint { display: block; font-size: 0.72rem; color: var(--color-text-secondary); font-weight: 400; margin-top: 0.1rem; }
.field-input {
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.88rem;
  width: 100%;
  box-sizing: border-box;
}
.field-input:focus { outline: 2px solid var(--color-accent); border-color: transparent; }
.field-textarea { resize: vertical; font-family: inherit; min-height: 70px; }
.field-error { margin: 0; font-size: 0.78rem; color: #c0392b; }

.submit-error { margin: 0; font-size: 0.82rem; color: #c0392b; }

.modal-footer {
  padding: 0.85rem 1.2rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
}
.cancel-btn {
  padding: 0.4rem 1rem; border-radius: 8px; border: 1px solid var(--color-border);
  background: none; color: var(--color-text-secondary); cursor: pointer; font-size: 0.85rem;
}
.cancel-btn:hover { border-color: var(--color-text-secondary); }
.publish-btn {
  padding: 0.4rem 1.2rem; border-radius: 8px; border: none;
  background: var(--color-accent); color: white; cursor: pointer; font-size: 0.85rem;
  font-weight: 600;
}
.publish-btn:hover:not(:disabled) { opacity: 0.88; }
.publish-btn:disabled { opacity: 0.5; cursor: default; }
.publish-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
</style>
