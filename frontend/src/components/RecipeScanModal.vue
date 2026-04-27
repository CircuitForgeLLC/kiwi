<template>
  <div class="modal-overlay" @click.self="close" role="dialog" aria-modal="true" :aria-labelledby="titleId">
    <div class="modal-panel scan-modal">

      <!-- Header -->
      <div class="modal-header">
        <h2 :id="titleId" class="modal-title">
          <span v-if="phase === 'upload'">Scan a Recipe</span>
          <span v-else-if="phase === 'processing'">Scanning...</span>
          <span v-else>Review Recipe</span>
        </h2>
        <button class="btn-icon close-btn" @click="close" aria-label="Close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- ── Upload phase ── -->
      <div v-if="phase === 'upload'" class="modal-body">
        <p class="hint-text">
          Photograph a recipe card, cookbook page, or handwritten note.
          For multi-page recipes (ingredients on one page, directions on another)
          select both photos together — up to 4 images.
        </p>

        <!-- Drop zone -->
        <div
          class="drop-zone"
          :class="{ 'drop-zone-active': isDragging, 'has-files': selectedFiles.length > 0 }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
          role="button"
          tabindex="0"
          @keydown.enter.space="fileInput?.click()"
          aria-label="Click or drop photos here"
        >
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp,image/heic,image/heif"
            multiple
            class="hidden-input"
            @change="onFileChange"
          />

          <div v-if="selectedFiles.length === 0" class="drop-zone-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="camera-icon">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
            <p class="drop-zone-label">Tap or drop photos here</p>
            <p class="drop-zone-sub">JPEG, PNG, WebP, HEIC — up to 4 photos</p>
          </div>

          <div v-else class="file-preview-grid">
            <div
              v-for="(_file, i) in selectedFiles"
              :key="i"
              class="file-preview-item"
            >
              <img :src="previewUrls[i]" :alt="`Photo ${i + 1}`" class="preview-img" />
              <button
                class="remove-file-btn"
                @click.stop="removeFile(i)"
                :aria-label="`Remove photo ${i + 1}`"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
              <p class="preview-label">Page {{ i + 1 }}</p>
            </div>
            <div
              v-if="selectedFiles.length < 4"
              class="file-preview-add"
              @click.stop="fileInput?.click()"
              role="button"
              tabindex="0"
              @keydown.enter.space.stop="fileInput?.click()"
              aria-label="Add another photo"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </div>
          </div>
        </div>

        <div v-if="uploadError" class="status-badge status-error mt-sm" role="alert">
          {{ uploadError }}
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="close">Cancel</button>
          <button
            class="btn btn-primary"
            :disabled="selectedFiles.length === 0"
            @click="startScan"
          >
            Scan Recipe
          </button>
        </div>
      </div>

      <!-- ── Processing phase ── -->
      <div v-else-if="phase === 'processing'" class="modal-body processing-body">
        <div class="scan-spinner" aria-live="polite" aria-label="Scanning recipe">
          <svg class="spin-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
            <circle cx="12" cy="13" r="4"/>
          </svg>
          <p class="processing-label">Extracting recipe from {{ selectedFiles.length > 1 ? selectedFiles.length + ' photos' : 'photo' }}...</p>
          <p class="processing-sub">This can take 10-30 seconds.</p>
        </div>
      </div>

      <!-- ── Review phase ── -->
      <div v-else-if="phase === 'review' && extracted" class="modal-body review-body">

        <!-- Confidence banner -->
        <div
          v-if="extracted.confidence !== 'high' || extracted.warnings.length > 0"
          :class="['status-badge', extracted.confidence === 'low' ? 'status-warning' : 'status-info', 'mb-sm']"
          role="status"
        >
          <span v-if="extracted.confidence === 'low'">Low confidence scan — handwritten or degraded text. Please review carefully.</span>
          <span v-else>Medium confidence. Check the fields below.</span>
          <ul v-if="extracted.warnings.length > 0" class="warning-list">
            <li v-for="w in extracted.warnings" :key="w">{{ w }}</li>
          </ul>
        </div>

        <!-- Pantry match badge -->
        <div v-if="extracted.ingredients.length > 0" class="pantry-match-row mb-sm">
          <span class="pantry-badge" :class="pantryMatchClass">
            {{ extracted.pantry_match_pct }}% pantry match
            ({{ pantryCount }} of {{ extracted.ingredients.length }} ingredients on hand)
          </span>
        </div>

        <!-- Editable fields -->
        <div class="review-form">

          <div class="form-group">
            <label class="form-label" for="scan-title">Recipe name</label>
            <input
              id="scan-title"
              v-model="editTitle"
              class="form-input"
              type="text"
              placeholder="Recipe name"
              required
            />
          </div>

          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label" for="scan-servings">Servings</label>
              <input id="scan-servings" v-model="editServings" class="form-input" type="text" placeholder="e.g. 2" />
            </div>
            <div class="form-group">
              <label class="form-label" for="scan-cooktime">Cook time</label>
              <input id="scan-cooktime" v-model="editCookTime" class="form-input" type="text" placeholder="e.g. 25 min" />
            </div>
          </div>

          <!-- Ingredients -->
          <div class="form-group">
            <label class="form-label">Ingredients</label>
            <div class="ingredient-list">
              <div
                v-for="(ingr, i) in editIngredients"
                :key="i"
                :class="['ingredient-row', ingr.in_pantry ? 'in-pantry' : '']"
              >
                <span v-if="ingr.in_pantry" class="pantry-dot" title="In your pantry" aria-label="In pantry"></span>
                <input
                  v-model="ingr.qty"
                  class="form-input ingr-qty"
                  type="text"
                  placeholder="qty"
                  :aria-label="`Ingredient ${i + 1} quantity`"
                />
                <input
                  v-model="ingr.unit"
                  class="form-input ingr-unit"
                  type="text"
                  placeholder="unit"
                  :aria-label="`Ingredient ${i + 1} unit`"
                />
                <input
                  v-model="ingr.name"
                  class="form-input ingr-name"
                  type="text"
                  placeholder="ingredient"
                  :aria-label="`Ingredient ${i + 1} name`"
                />
                <button
                  class="btn-icon remove-ingr-btn"
                  @click="removeIngredient(i)"
                  :aria-label="`Remove ingredient ${i + 1}`"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm mt-xs" @click="addIngredient">+ Add ingredient</button>
          </div>

          <!-- Steps -->
          <div class="form-group">
            <label class="form-label">Steps</label>
            <div class="step-list">
              <div v-for="(_step, i) in editSteps" :key="i" class="step-row">
                <span class="step-num">{{ i + 1 }}</span>
                <textarea
                  v-model="editSteps[i]"
                  class="form-input step-textarea"
                  rows="2"
                  :aria-label="`Step ${i + 1}`"
                ></textarea>
                <button
                  class="btn-icon remove-step-btn"
                  @click="removeStep(i)"
                  :aria-label="`Remove step ${i + 1}`"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm mt-xs" @click="addStep">+ Add step</button>
          </div>

          <!-- Notes (optional) -->
          <div class="form-group">
            <label class="form-label" for="scan-notes">Notes <span class="optional-label">(optional)</span></label>
            <textarea id="scan-notes" v-model="editNotes" class="form-input" rows="2" placeholder="Tips, variations, storage..."></textarea>
          </div>

          <!-- Source attribution -->
          <div v-if="extracted.source_note" class="source-note">
            Source: {{ extracted.source_note }}
          </div>

        </div>

        <div v-if="saveError" class="status-badge status-error mt-sm" role="alert">
          {{ saveError }}
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="phase = 'upload'">Re-scan</button>
          <button
            class="btn btn-primary"
            :disabled="!editTitle.trim() || saving"
            @click="save"
          >
            {{ saving ? 'Saving...' : 'Save Recipe' }}
          </button>
        </div>

      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { type ScannedRecipe, type ScannedIngredient, recipeScanAPI } from '@/services/api'

type Phase = 'upload' | 'processing' | 'review'

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', recipe: { id: number; title: string }): void
}>()

const titleId = 'scan-modal-title'

// ── Upload state ──────────────────────────────────────────────────────────────
const phase = ref<Phase>('upload')
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFiles = ref<File[]>([])
const previewUrls = ref<string[]>([])
const isDragging = ref(false)
const uploadError = ref('')

function onDrop(e: DragEvent) {
  isDragging.value = false
  const dt = e.dataTransfer
  if (!dt) return
  addFiles(Array.from(dt.files))
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  addFiles(Array.from(input.files))
  // Reset so the same file can be re-selected after removal
  input.value = ''
}

function addFiles(incoming: File[]) {
  uploadError.value = ''
  const combined = [...selectedFiles.value, ...incoming]
  if (combined.length > 4) {
    uploadError.value = 'Maximum 4 photos per scan.'
    return
  }
  // Revoke old preview URLs before replacing
  previewUrls.value.forEach((url) => URL.revokeObjectURL(url))
  selectedFiles.value = combined
  previewUrls.value = combined.map((f) => URL.createObjectURL(f))
}

function removeFile(index: number) {
  URL.revokeObjectURL(previewUrls.value[index] ?? '')
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== index)
  previewUrls.value = previewUrls.value.filter((_, i) => i !== index)
}

// ── Scan ──────────────────────────────────────────────────────────────────────
const extracted = ref<ScannedRecipe | null>(null)

async function startScan() {
  if (selectedFiles.value.length === 0) return
  uploadError.value = ''
  phase.value = 'processing'
  try {
    const result = await recipeScanAPI.scan(selectedFiles.value)
    extracted.value = result
    initEditState(result)
    phase.value = 'review'
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    uploadError.value = msg.includes('not appear to contain a recipe')
      ? 'This photo does not look like a recipe. Please try a different photo.'
      : msg.includes('No vision backend')
      ? 'Recipe scanning is not available right now. Check your BYOK settings.'
      : `Scan failed: ${msg}`
    phase.value = 'upload'
  }
}

// ── Review/edit state ─────────────────────────────────────────────────────────
const editTitle = ref('')
const editServings = ref('')
const editCookTime = ref('')
const editIngredients = ref<ScannedIngredient[]>([])
const editSteps = ref<string[]>([])
const editNotes = ref('')

function initEditState(r: ScannedRecipe) {
  editTitle.value = r.title ?? ''
  editServings.value = r.servings ?? ''
  editCookTime.value = r.cook_time ?? ''
  editIngredients.value = r.ingredients.map((i) => ({ ...i }))
  editSteps.value = [...r.steps]
  editNotes.value = r.notes ?? ''
}

function removeIngredient(i: number) {
  editIngredients.value = editIngredients.value.filter((_, idx) => idx !== i)
}

function addIngredient() {
  editIngredients.value = [...editIngredients.value, { name: '', qty: null, unit: null, raw: null, in_pantry: false }]
}

function removeStep(i: number) {
  editSteps.value = editSteps.value.filter((_, idx) => idx !== i)
}

function addStep() {
  editSteps.value = [...editSteps.value, '']
}

// ── Pantry match display ──────────────────────────────────────────────────────
const pantryCount = computed(() =>
  editIngredients.value.filter((i) => i.in_pantry).length
)

const pantryMatchClass = computed(() => {
  const pct = extracted.value?.pantry_match_pct ?? 0
  if (pct >= 80) return 'pantry-high'
  if (pct >= 50) return 'pantry-mid'
  return 'pantry-low'
})

// ── Save ──────────────────────────────────────────────────────────────────────
const saving = ref(false)
const saveError = ref('')

async function save() {
  if (!editTitle.value.trim()) return
  saving.value = true
  saveError.value = ''
  try {
    const payload = {
      title: editTitle.value.trim(),
      subtitle: extracted.value?.subtitle ?? null,
      servings: editServings.value || null,
      cook_time: editCookTime.value || null,
      source_note: extracted.value?.source_note ?? null,
      ingredients: editIngredients.value.filter((i) => i.name.trim()),
      steps: editSteps.value.filter((s) => s.trim()),
      notes: editNotes.value.trim() || null,
      tags: extracted.value?.tags ?? [],
      source: 'scan' as const,
    }
    const saved = await recipeScanAPI.saveScanned(payload)
    emit('saved', { id: saved.id, title: saved.title })
    close()
  } catch (err: unknown) {
    saveError.value = err instanceof Error ? err.message : 'Failed to save recipe.'
  } finally {
    saving.value = false
  }
}

// ── Cleanup ───────────────────────────────────────────────────────────────────
function close() {
  previewUrls.value.forEach((url) => URL.revokeObjectURL(url))
  emit('close')
}

onBeforeUnmount(() => {
  previewUrls.value.forEach((url) => URL.revokeObjectURL(url))
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal, 1000);
  padding: var(--spacing-md);
}

.modal-panel {
  background: var(--bg-card, #fff);
  border-radius: var(--radius-lg, 12px);
  box-shadow: var(--shadow-xl, 0 20px 60px rgba(0,0,0,0.2));
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  flex-shrink: 0;
}

.modal-title {
  font-size: var(--font-lg, 1.125rem);
  font-weight: 600;
  color: var(--text-primary, #111);
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: var(--text-secondary, #6b7280);
  border-radius: var(--radius-sm, 4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-hover, #f3f4f6);
  color: var(--text-primary, #111);
}

.modal-body {
  padding: var(--spacing-lg);
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color, #e5e7eb);
  margin-top: var(--spacing-md);
}

/* ── Upload ── */
.hint-text {
  color: var(--text-secondary, #6b7280);
  font-size: var(--font-sm, 0.875rem);
  margin-bottom: var(--spacing-md);
  line-height: 1.5;
}

.drop-zone {
  border: 2px dashed var(--border-color, #d1d5db);
  border-radius: var(--radius-md, 8px);
  padding: var(--spacing-xl);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-zone:hover,
.drop-zone-active {
  border-color: var(--color-primary, #4f46e5);
  background: var(--bg-hover, #f5f3ff);
}

.drop-zone.has-files {
  border-style: solid;
  border-color: var(--color-primary, #4f46e5);
  padding: var(--spacing-md);
}

.hidden-input {
  display: none;
}

.drop-zone-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.camera-icon {
  color: var(--text-secondary, #9ca3af);
  margin-bottom: var(--spacing-xs);
}

.drop-zone-label {
  font-weight: 600;
  color: var(--text-primary, #111);
  margin: 0;
}

.drop-zone-sub {
  color: var(--text-secondary, #6b7280);
  font-size: var(--font-sm, 0.875rem);
  margin: 0;
}

.file-preview-grid {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  align-items: center;
  width: 100%;
}

.file-preview-item {
  position: relative;
  width: 100px;
}

.preview-img {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--border-color, #e5e7eb);
}

.remove-file-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  background: var(--color-danger, #ef4444);
  color: white;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.preview-label {
  text-align: center;
  font-size: var(--font-xs, 0.75rem);
  color: var(--text-secondary, #6b7280);
  margin: 4px 0 0;
}

.file-preview-add {
  width: 100px;
  height: 100px;
  border: 2px dashed var(--border-color, #d1d5db);
  border-radius: var(--radius-sm, 6px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary, #9ca3af);
  transition: border-color 0.15s;
}

.file-preview-add:hover {
  border-color: var(--color-primary, #4f46e5);
  color: var(--color-primary, #4f46e5);
}

/* ── Processing ── */
.processing-body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.scan-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
}

.spin-icon {
  color: var(--color-primary, #4f46e5);
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.processing-label {
  font-weight: 600;
  color: var(--text-primary, #111);
  margin: 0;
}

.processing-sub {
  color: var(--text-secondary, #6b7280);
  font-size: var(--font-sm, 0.875rem);
  margin: 0;
}

/* ── Review ── */
.review-body {
  padding-bottom: var(--spacing-sm);
}

.pantry-match-row {
  display: flex;
  align-items: center;
}

.pantry-badge {
  display: inline-block;
  font-size: var(--font-sm, 0.875rem);
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}

.pantry-high { background: var(--color-success-bg, #d1fae5); color: var(--color-success, #065f46); }
.pantry-mid  { background: var(--color-info-bg, #dbeafe);    color: var(--color-info, #1e40af); }
.pantry-low  { background: var(--bg-secondary, #f3f4f6);     color: var(--text-secondary, #374151); }

.review-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
}

/* Ingredients */
.ingredient-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ingredient-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pantry-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success, #10b981);
  flex-shrink: 0;
}

.in-pantry {
  background: var(--color-success-bg-faint, #f0fdf4);
  border-radius: var(--radius-sm, 4px);
  padding: 2px 4px;
}

.ingr-qty   { width: 60px; flex-shrink: 0; }
.ingr-unit  { width: 70px; flex-shrink: 0; }
.ingr-name  { flex: 1; }

.remove-ingr-btn,
.remove-step-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: var(--text-secondary, #9ca3af);
  border-radius: var(--radius-sm, 4px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.remove-ingr-btn:hover,
.remove-step-btn:hover {
  background: var(--color-danger-bg, #fee2e2);
  color: var(--color-danger, #ef4444);
}

/* Steps */
.step-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-secondary, #f3f4f6);
  color: var(--text-secondary, #374151);
  font-size: var(--font-xs, 0.75rem);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 8px;
}

.step-textarea {
  flex: 1;
  resize: vertical;
  min-height: 60px;
}

/* Source */
.source-note {
  font-size: var(--font-xs, 0.75rem);
  color: var(--text-secondary, #9ca3af);
  text-align: right;
  font-style: italic;
}

.optional-label {
  color: var(--text-secondary, #9ca3af);
  font-weight: normal;
  font-size: var(--font-xs, 0.75rem);
}

.warning-list {
  margin: 4px 0 0;
  padding-left: 16px;
  font-size: var(--font-sm, 0.875rem);
}

.btn-ghost {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary, #4f46e5);
  padding: 4px 8px;
  font-size: var(--font-sm, 0.875rem);
  border-radius: var(--radius-sm, 4px);
}

.btn-ghost:hover {
  background: var(--bg-hover, #f5f3ff);
}

.btn-sm {
  padding: 4px 10px;
  font-size: var(--font-sm, 0.875rem);
}

.mt-xs { margin-top: var(--spacing-xs, 4px); }
.mt-sm { margin-top: var(--spacing-sm, 8px); }
.mb-sm { margin-bottom: var(--spacing-sm, 8px); }

@media (max-width: 480px) {
  .form-row-2 {
    grid-template-columns: 1fr;
  }
  .modal-panel {
    border-radius: var(--radius-md, 8px);
    max-height: 95vh;
  }
}
</style>
