<template>
  <Teleport to="body">
  <!-- Backdrop — click outside to close -->
  <div class="detail-overlay" @click.self="$emit('close')">
    <div ref="dialogRef" class="detail-panel" role="dialog" aria-modal="true" :aria-label="recipe.title" tabindex="-1">

      <!-- Sticky header -->
      <div class="detail-header">
        <div class="header-badges">
          <span class="status-badge status-success">{{ recipe.match_count }} matched</span>
          <span class="status-badge status-info">Level {{ recipe.level }}</span>
          <span v-if="recipe.is_wildcard" class="status-badge status-warning">Wildcard</span>
        </div>
        <div class="header-row">
          <h2 class="detail-title">{{ recipe.title }}</h2>
          <div class="header-actions flex gap-sm">
            <button
              class="btn btn-secondary btn-save"
              :class="{ 'btn-saved': isSaved }"
              @click="showSaveModal = true"
              :aria-label="isSaved ? 'Edit saved recipe' : 'Save recipe'"
            >{{ isSaved ? '★ Saved' : '☆ Save' }}</button>
            <!-- Cook mode toggle -->
          <button
            v-if="recipe.directions.length > 0"
            class="btn btn-cook"
            :class="{ 'btn-cook--active': cookModeActive }"
            @click="cookModeActive ? exitCookMode() : enterCookMode()"
            :aria-label="cookModeActive ? 'Exit cook mode' : 'Enter cook mode'"
            :aria-pressed="cookModeActive"
          >{{ cookModeActive ? '✕ Exit' : 'Cook' }}</button>

          <button class="btn-close" @click="$emit('close')" aria-label="Close panel">✕</button>
          </div>
        </div>
        <p v-if="recipe.notes" class="detail-notes">{{ recipe.notes }}</p>
        <a
          v-if="recipe.source_url"
          :href="recipe.source_url"
          target="_blank"
          rel="noopener noreferrer"
          class="source-link"
        >View original ↗</a>
      </div>

      <!-- Cook mode bar: progress + step counter -->
      <div v-if="cookModeActive" class="cook-mode-bar" role="status" :aria-label="`Step ${cookStep + 1} of ${cookStepCount}`">
        <div class="cook-progress-track">
          <div
            class="cook-progress-fill"
            :style="{ width: `${cookProgress * 100}%` }"
          ></div>
        </div>
        <span class="cook-step-counter">Step {{ cookStep + 1 }} of {{ cookStepCount }}</span>
      </div>

      <!-- Normal scrollable body -->
      <div v-if="!cookModeActive" class="detail-body">

        <!-- Serving multiplier -->
        <div class="serving-scale-row">
          <span class="serving-scale-label text-sm text-muted">Scale:</span>
          <div class="serving-scale-btns" role="group" aria-label="Serving multiplier">
            <button
              v-for="n in [1, 2, 3, 4]"
              :key="n"
              :class="['scale-btn', { active: servingScale === n }]"
              :aria-pressed="servingScale === n"
              @click="servingScale = n"
            >{{ n }}×</button>
          </div>
        </div>

        <!-- Ingredients: have vs. need in a two-column layout -->
        <details open class="ingredients-collapsible">
          <summary class="ingredients-collapsible-summary">
            Ingredients
            <span class="ingr-summary-counts">
              <span v-if="recipe.matched_ingredients?.length" class="ingr-count ingr-count-have">{{ recipe.matched_ingredients.length }} ✓</span>
              <span v-if="recipe.missing_ingredients?.length" class="ingr-count ingr-count-need">{{ recipe.missing_ingredients.length }} needed</span>
            </span>
          </summary>
          <div class="ingredients-grid">
          <div v-if="recipe.matched_ingredients?.length > 0" class="ingredient-col ingredient-col-have">
            <h3 class="col-label col-label-have">From your pantry</h3>
            <ul class="ingredient-list">
              <li v-for="ing in recipe.matched_ingredients" :key="ing" class="ing-row">
                <span class="ing-icon ing-icon-have">✓</span>
                <span>{{ scaleIngredient(ing, servingScale) }}</span>
              </li>
            </ul>
          </div>

          <div v-if="recipe.missing_ingredients?.length > 0" class="ingredient-col ingredient-col-need">
            <div class="col-header-row">
              <h3 class="col-label col-label-need">Still needed</h3>
              <div class="col-header-actions">
                <button class="share-btn" @click="shareList" :title="shareCopied ? 'Copied!' : 'Copy / share list'">
                  {{ shareCopied ? '✓ Copied' : 'Share' }}
                </button>
              </div>
            </div>
            <ul class="ingredient-list">
              <li v-for="ing in recipe.missing_ingredients" :key="ing" class="ing-row">
                <label class="ing-check-label">
                  <input
                    type="checkbox"
                    class="ing-check"
                    :checked="checkedIngredients.has(ing)"
                    @change="toggleIngredient(ing)"
                  />
                  <span class="ing-name">{{ scaleIngredient(ing, servingScale) }}</span>
                </label>
                <a
                  v-if="groceryLinkFor(ing)"
                  :href="groceryLinkFor(ing)!.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="buy-link"
                >Buy ↗</a>
              </li>
            </ul>
            <button
              v-if="recipe.missing_ingredients.length > 1"
              class="select-all-btn"
              @click="toggleSelectAll"
            >{{ checkedIngredients.size === recipe.missing_ingredients.length ? 'Deselect all' : 'Select all' }}</button>
          </div>
          </div>
        </details>

        <!-- Time & effort summary cards -->
        <div v-if="recipe.time_effort" class="effort-summary">
          <div class="effort-card effort-card-active">
            <span class="effort-label">Active</span>
            <span class="effort-value">{{ formatDetailMin(recipe.time_effort.active_min) }}</span>
          </div>
          <div v-if="recipe.time_effort.passive_min > 0" class="effort-card effort-card-passive">
            <span class="effort-label">Hands-off</span>
            <span class="effort-value">{{ formatDetailMin(recipe.time_effort.passive_min) }}</span>
          </div>
          <div class="effort-card effort-card-total">
            <span class="effort-label">Total</span>
            <span class="effort-value">{{ formatDetailMin(recipe.time_effort.total_min) }}</span>
          </div>
          <div class="effort-level-badge" :class="'effort-' + recipe.time_effort.effort_label">
            {{ recipe.time_effort.effort_label }}
          </div>
        </div>

        <!-- Equipment chips -->
        <div v-if="recipe.time_effort?.equipment?.length" class="equipment-chips">
          <span
            v-for="eq in recipe.time_effort.equipment"
            :key="eq"
            class="equipment-chip"
          >{{ EQUIPMENT_ICONS[eq] ?? '🍴' }} {{ eq }}</span>
        </div>

        <!-- Swap candidates -->
        <details v-if="recipe.swap_candidates.length > 0" class="detail-collapsible">
          <summary class="detail-collapsible-summary">
            Possible swaps ({{ recipe.swap_candidates.length }})
          </summary>
          <div class="card-secondary mt-xs">
            <div
              v-for="swap in recipe.swap_candidates"
              :key="swap.original_name + swap.substitute_name"
              class="swap-row text-sm"
            >
              <span class="font-semibold">{{ swap.original_name }}</span>
              <span class="text-muted"> → </span>
              <span class="font-semibold">{{ swap.substitute_name }}</span>
              <span v-if="swap.constraint_label" class="status-badge status-info ml-xs">{{ swap.constraint_label }}</span>
              <p v-if="swap.explanation" class="text-muted mt-xs">{{ swap.explanation }}</p>
            </div>
          </div>
        </details>

        <!-- Nutrition panel -->
        <div v-if="recipe.nutrition" class="detail-section">
          <h3 class="section-label">Nutrition</h3>
          <div class="nutrition-chips">
            <span v-if="recipe.nutrition.calories != null" class="nutrition-chip">🔥 {{ Math.round(recipe.nutrition.calories) }} kcal</span>
            <span v-if="recipe.nutrition.fat_g != null" class="nutrition-chip">🧈 {{ recipe.nutrition.fat_g.toFixed(1) }}g fat</span>
            <span v-if="recipe.nutrition.protein_g != null" class="nutrition-chip">💪 {{ recipe.nutrition.protein_g.toFixed(1) }}g protein</span>
            <span v-if="recipe.nutrition.carbs_g != null" class="nutrition-chip">🌾 {{ recipe.nutrition.carbs_g.toFixed(1) }}g carbs</span>
            <span v-if="recipe.nutrition.fiber_g != null" class="nutrition-chip">🌿 {{ recipe.nutrition.fiber_g.toFixed(1) }}g fiber</span>
            <span v-if="recipe.nutrition.sugar_g != null" class="nutrition-chip nutrition-chip-sugar">🍬 {{ recipe.nutrition.sugar_g.toFixed(1) }}g sugar</span>
            <span v-if="recipe.nutrition.sodium_mg != null" class="nutrition-chip">🧂 {{ Math.round(recipe.nutrition.sodium_mg) }}mg sodium</span>
            <span v-if="recipe.nutrition.servings != null" class="nutrition-chip nutrition-chip-servings">
              🍽️ {{ recipe.nutrition.servings }} serving{{ recipe.nutrition.servings !== 1 ? 's' : '' }}
            </span>
            <span v-if="recipe.nutrition.estimated" class="nutrition-chip nutrition-chip-estimated" title="Estimated from ingredient profiles">~ estimated</span>
          </div>
        </div>

        <!-- Prep notes -->
        <div v-if="recipe.prep_notes.length > 0" class="detail-section">
          <h3 class="section-label">Before you start</h3>
          <ul class="prep-list">
            <li v-for="note in recipe.prep_notes" :key="note" class="text-sm prep-item">{{ note }}</li>
          </ul>
        </div>

        <!-- Directions (annotated) -->
        <details open v-if="recipe.directions.length > 0" class="steps-collapsible">
          <summary class="steps-collapsible-summary">
            Steps <span class="steps-count">({{ recipe.directions.length }})</span>
          </summary>
          <ol class="directions-list directions-list-annotated">
            <li
              v-for="(step, i) in recipe.directions"
              :key="i"
              class="text-sm direction-step direction-step-annotated"
              :class="{ 'step-passive': stepAnalysis(i)?.is_passive }"
            >
              <div class="step-badge-row">
                <span v-if="stepAnalysis(i)?.is_passive" class="step-type-badge step-type-wait">Wait</span>
                <span v-else-if="stepAnalysis(i)" class="step-type-badge step-type-active">Active</span>
              </div>
              <p class="step-text">{{ step }}</p>
              <p v-if="passiveHint(stepAnalysis(i))" class="step-passive-hint">{{ passiveHint(stepAnalysis(i)) }}</p>
            </li>
          </ol>
        </details>

        <!-- Bottom padding so last step isn't hidden behind sticky footer -->
        <div style="height: var(--spacing-xl)" />
      </div>

      <!-- Cook mode: single-step view -->
      <div
        v-else
        class="detail-body cook-step-view"
        @touchstart.passive="onTouchStart"
        @touchend.passive="onTouchEnd"
      >
        <div class="cook-step-label">STEP {{ cookStep + 1 }}</div>

        <div v-if="currentStepAnalysis" class="cook-step-badge-row">
          <span
            class="cook-step-badge"
            :class="currentStepAnalysis.is_passive ? 'cook-badge--wait' : 'cook-badge--active'"
          >{{ currentStepAnalysis.is_passive ? 'Wait' : 'Active' }}</span>
        </div>

        <p class="cook-step-text">{{ recipe.directions[cookStep] }}</p>

        <p
          v-if="currentStepAnalysis?.detected_minutes != null"
          class="cook-step-hint"
        >~{{ currentStepAnalysis.detected_minutes }} min hands-off</p>

        <div class="cook-nav">
          <button
            class="btn cook-nav-prev"
            :class="{ 'cook-nav--disabled': cookStep === 0 }"
            :disabled="cookStep === 0"
            :aria-label="cookStep === 0 ? 'No previous step' : 'Previous step'"
            @click="prevStep"
          >← Prev</button>

          <button
            class="btn cook-nav-next"
            :class="{ 'cook-nav--done': isLastStep }"
            :aria-label="isLastStep ? 'Done cooking' : 'Next step'"
            @click="nextStep"
          >{{ isLastStep ? 'Done ✓' : 'Next →' }}</button>
        </div>
      </div>

      <!-- Sticky footer -->
      <div class="detail-footer">
        <div v-if="cookDone" class="cook-success">
          <span class="cook-success-icon">✓</span>
          Enjoy your meal! Recipe dismissed from suggestions.
          <button class="btn btn-secondary btn-sm mt-xs" @click="$emit('close')">Close</button>
        </div>
        <template v-else>
          <button class="btn btn-secondary" @click="$emit('close')">Back</button>
          <button
            :class="['btn-bookmark-panel', { active: recipesStore.isBookmarked(recipe.id) }]"
            @click="recipesStore.toggleBookmark(recipe)"
            :aria-label="recipesStore.isBookmarked(recipe.id) ? `Remove bookmark: ${recipe.title}` : `Bookmark: ${recipe.title}`"
          >{{ recipesStore.isBookmarked(recipe.id) ? '★' : '☆' }}</button>
          <template v-if="checkedCount > 0">
            <div class="add-pantry-col">
              <p v-if="addError" role="alert" aria-live="assertive" class="add-error text-xs">{{ addError }}</p>
              <p v-if="addedToPantry" role="status" aria-live="polite" class="add-success text-xs">✓ Added to pantry!</p>
              <div class="grocery-actions">
                <button
                  class="btn btn-primary flex-1"
                  @click="copyGroceryList"
                >{{ groceryCopied ? '✓ Copied!' : `📋 Grocery list (${checkedCount})` }}</button>
                <button
                  class="btn btn-secondary"
                  :disabled="addingToPantry"
                  @click="addToPantry"
                  :title="`Add ${checkedCount} item${checkedCount !== 1 ? 's' : ''} to your pantry`"
                >
                  <span v-if="addingToPantry">Adding…</span>
                  <span v-else>+ Pantry</span>
                </button>
              </div>
            </div>
          </template>
          <button v-else class="btn btn-primary flex-1" @click="handleCook">
            ✓ I cooked this
          </button>
        </template>
      </div>

    </div>
  </div>
  </Teleport>

  <SaveRecipeModal
    v-if="showSaveModal"
    :recipe-id="recipe.id"
    :recipe-title="recipe.title"
    @close="showSaveModal = false"
    @saved="showSaveModal = false"
    @unsave="savedStore.unsave(recipe.id); showSaveModal = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRecipesStore } from '../stores/recipes'
import { useSavedRecipesStore } from '../stores/savedRecipes'
import { inventoryAPI } from '../services/api'
import type { RecipeSuggestion, GroceryLink, StepAnalysis, TimeEffortProfile } from '../services/api'
import SaveRecipeModal from './SaveRecipeModal.vue'

const dialogRef = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  if (cookModeActive.value) {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      nextStep()
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      prevStep()
    }
  }
}

onMounted(() => {
  previousFocus = document.activeElement as HTMLElement
  document.addEventListener('keydown', handleKeydown)
  nextTick(() => {
    const focusable = dialogRef.value?.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input'
    )
    ;(focusable ?? dialogRef.value)?.focus()
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  previousFocus?.focus()
})

const recipesStore = useRecipesStore()
const savedStore = useSavedRecipesStore()

const props = defineProps<{
  recipe: RecipeSuggestion
  groceryLinks: GroceryLink[]
}>()

const emit = defineEmits<{
  close: []
  cooked: [recipe: RecipeSuggestion]
}>()

const showSaveModal = ref(false)
const isSaved = computed(() => savedStore.isSaved(props.recipe.id))

const cookDone = ref(false)

// ── Cook mode ─────────────────────────────────────────────
const cookModeActive = ref(false)
const cookStep = ref(0) // 0-indexed

function enterCookMode() {
  cookModeActive.value = true
  cookStep.value = 0
}

function exitCookMode() {
  cookModeActive.value = false
  cookStep.value = 0
}

function nextStep() {
  const lastIdx = props.recipe.directions.length - 1
  if (cookStep.value < lastIdx) {
    cookStep.value++
  } else {
    handleCook()
    exitCookMode()
  }
}

function prevStep() {
  if (cookStep.value > 0) cookStep.value--
}

// Reads step_analyses from kiwi#50 time_effort — null-safe
const currentStepAnalysis = computed(() => {
  return props.recipe.time_effort?.step_analyses?.[cookStep.value] ?? null
})

const cookStepCount = computed(() => props.recipe.directions.length)
const isLastStep = computed(() => cookStep.value === cookStepCount.value - 1)
const cookProgress = computed(() =>
  cookStepCount.value > 1 ? cookStep.value / (cookStepCount.value - 1) : 1
)

// Touch state for swipe navigation
const touchStartX = ref(0)
const touchStartY = ref(0)

function onTouchStart(e: TouchEvent) {
  touchStartX.value = e.changedTouches[0]!.clientX
  touchStartY.value = e.changedTouches[0]!.clientY
}

function onTouchEnd(e: TouchEvent) {
  const dx = e.changedTouches[0]!.clientX - touchStartX.value
  const dy = e.changedTouches[0]!.clientY - touchStartY.value
  // Require predominantly horizontal gesture
  if (Math.abs(dx) >= 40 && Math.abs(dy) < 80) {
    if (dx < 0) {
      nextStep()    // swipe left → next
    } else {
      prevStep()    // swipe right → prev
    }
  }
}
const shareCopied = ref(false)

// Serving scale multiplier: 1×, 2×, 3×, 4×
const servingScale = ref(1)

/**
 * Scale a freeform ingredient string by a multiplier.
 * Handles integers, decimals, and simple fractions (1/2, 1/4, 3/4, etc.).
 * Ranges like "2-3" are scaled on both ends.
 * Returns the original string unchanged if no leading number is found.
 */
function scaleIngredient(ing: string, scale: number): string {
  if (scale === 1) return ing

  // Match an optional leading fraction OR decimal OR integer,
  // optionally followed by a space and another fraction (mixed number like "1 1/2")
  const numPat = String.raw`(\d+\s+\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?)`
  const rangePat = new RegExp(`^${numPat}(?:\\s*-\\s*${numPat})?`)

  const m = ing.match(rangePat)
  if (!m) return ing

  function parseFrac(s: string): number {
    const mixed = s.match(/^(\d+)\s+(\d+)\/(\d+)$/)
    if (mixed) return parseInt(mixed[1]!) + parseInt(mixed[2]!) / parseInt(mixed[3]!)
    const frac = s.match(/^(\d+)\/(\d+)$/)
    if (frac) return parseInt(frac[1]!) / parseInt(frac[2]!)
    return parseFloat(s)
  }

  function fmtNum(n: number): string {
    // Try to express as a simple fraction for common baking values
    const fracs: [number, string][] = [
      [0.125, '1/8'], [0.25, '1/4'], [0.333, '1/3'], [0.5, '1/2'],
      [0.667, '2/3'], [0.75, '3/4'],
    ]
    for (const [val, str] of fracs) {
      if (Math.abs(n - Math.round(n / val) * val) < 0.01 && n < 1) return str
    }
    // Mixed numbers
    const whole = Math.floor(n)
    const remainder = n - whole
    if (whole > 0 && remainder > 0.05) {
      for (const [val, str] of fracs) {
        if (Math.abs(remainder - val) < 0.05) return `${whole} ${str}`
      }
    }
    // Round to reasonable precision
    return whole > 0 && remainder < 0.05 ? `${whole}` : n.toFixed(1).replace(/\.0$/, '')
  }

  const low = parseFrac(m[1]!)
  const scaledLow = fmtNum(low * scale)

  let scaled: string
  if (m[2] !== undefined) {
    const high = parseFrac(m[2])
    scaled = `${scaledLow}-${fmtNum(high * scale)}`
  } else {
    scaled = scaledLow
  }

  return scaled + ing.slice(m[0].length)
}

// Time & effort helpers
function formatDetailMin(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h} hr` : `${h} hr ${m} min`
}

const EQUIPMENT_ICONS: Record<string, string> = {
  oven: '♨',
  stovetop: '🔥',
  blender: '⚡',
  'food processor': '⚡',
  microwave: '📡',
  grill: '🔥',
  'slow cooker': '⏲',
  'instant pot': '⏲',
  mixer: '🌀',
  skillet: '🍳',
  'cast iron': '🍳',
  wok: '🍳',
}

function stepAnalysis(i: number): StepAnalysis | null {
  return props.recipe.time_effort?.step_analyses?.[i] ?? null
}

function passiveHint(analysis: StepAnalysis | null): string {
  if (!analysis?.is_passive) return ''
  if (analysis.detected_minutes) return `~${analysis.detected_minutes} min hands-off`
  return 'Hands-off time'
}

// Shopping: add purchased ingredients to pantry
const checkedIngredients = ref<Set<string>>(new Set())
const addingToPantry = ref(false)
const addedToPantry = ref(false)
const addError = ref<string | null>(null)
const groceryCopied = ref(false)

const checkedCount = computed(() => checkedIngredients.value.size)

function toggleIngredient(name: string) {
  const next = new Set(checkedIngredients.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  checkedIngredients.value = next
}

function toggleSelectAll() {
  if (checkedIngredients.value.size === props.recipe.missing_ingredients.length) {
    checkedIngredients.value = new Set()
  } else {
    checkedIngredients.value = new Set(props.recipe.missing_ingredients)
  }
}

async function addToPantry() {
  if (!checkedIngredients.value.size || addingToPantry.value) return
  addingToPantry.value = true
  addError.value = null
  try {
    const items = [...checkedIngredients.value].map((name) => ({ name, location: 'pantry' }))
    const result = await inventoryAPI.bulkAddByName(items)
    if (result.failed > 0 && result.added === 0) {
      addError.value = 'Failed to add items. Please try again.'
    } else {
      addedToPantry.value = true
      checkedIngredients.value = new Set()
    }
  } catch {
    addError.value = 'Could not reach the pantry. Please try again.'
  } finally {
    addingToPantry.value = false
  }
}

async function shareList() {
  const items = props.recipe.missing_ingredients
  if (!items?.length) return
  const text = `Shopping list for ${props.recipe.title}:\n${items.map((i) => `• ${i}`).join('\n')}`
  if (navigator.share) {
    await navigator.share({ title: `Shopping list: ${props.recipe.title}`, text })
  } else {
    await navigator.clipboard.writeText(text)
    shareCopied.value = true
    setTimeout(() => { shareCopied.value = false }, 2000)
  }
}

async function copyGroceryList() {
  const items = [...checkedIngredients.value]
  if (!items.length) return
  const text = `Shopping list for ${props.recipe.title}:\n${items.map((i) => `• ${i}`).join('\n')}`
  if (navigator.share) {
    await navigator.share({ title: `Shopping list: ${props.recipe.title}`, text })
  } else {
    await navigator.clipboard.writeText(text)
    groceryCopied.value = true
    setTimeout(() => { groceryCopied.value = false }, 2000)
  }
}

function groceryLinkFor(ingredient: string): GroceryLink | undefined {
  const needle = ingredient.toLowerCase()
  return props.groceryLinks.find((l) => l.ingredient.toLowerCase() === needle)
}

function handleCook() {
  recipesStore.logCook(props.recipe.id, props.recipe.title)
  cookDone.value = true
  emit('cooked', props.recipe)
}
</script>

<style scoped>
/* ── Overlay / bottom-sheet shell ──────────────────────── */
.detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 400; /* above bottom-nav (200) and app-header (100) */
  display: flex;
  align-items: flex-end;
}

.detail-panel {
  width: 100%;
  max-height: 92dvh;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg, 12px) var(--radius-lg, 12px) 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.2);
}

/* Centered modal on wider screens */
@media (min-width: 640px) {
  .detail-overlay {
    align-items: center;
    justify-content: center;
    padding: var(--spacing-md);
  }

  .detail-panel {
    max-width: 680px;
    max-height: 85dvh;
    border-radius: var(--radius-lg, 12px);
  }
}

/* ── Header ─────────────────────────────────────────────── */
.detail-header {
  padding: var(--spacing-md) var(--spacing-md) var(--spacing-sm);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.header-badges {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-xs);
}

.header-row {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.detail-title {
  font-size: var(--font-size-lg);
  font-weight: 700;
  flex: 1;
  line-height: 1.3;
  color: var(--color-text-primary);
}

.header-actions {
  align-items: center;
  flex-shrink: 0;
}

.btn-save {
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
}

.btn-saved {
  color: var(--color-warning);
  border-color: var(--color-warning);
}

/* ── Cook mode button ───────────────────────────────────── */
.btn-cook {
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(232, 168, 32, 0.15);
  border: 1px solid rgba(232, 168, 32, 0.3);
  color: #f0bc48;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s;
}

.btn-cook:hover {
  background: rgba(232, 168, 32, 0.25);
  border-color: rgba(232, 168, 32, 0.5);
}

.btn-cook--active {
  background: rgba(232, 168, 32, 0.22);
  border-color: rgba(232, 168, 32, 0.5);
}

@media (max-width: 380px) {
  .btn-cook {
    padding: 2px 8px;
    font-size: var(--font-size-xs);
  }
}

.btn-close {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  font-size: 16px;
  color: var(--color-text-muted);
  border-radius: var(--radius-sm, 4px);
  flex-shrink: 0;
  line-height: 1;
  transition: color 0.15s, background 0.15s;
}

.btn-close:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-secondary);
}

.detail-notes {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--spacing-xs);
  line-height: 1.5;
}

/* ── Scrollable body ────────────────────────────────────── */
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  -webkit-overflow-scrolling: touch;
}

/* ── Serving scale row ──────────────────────────────────── */
.serving-scale-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.serving-scale-label {
  white-space: nowrap;
}

.serving-scale-btns {
  display: flex;
  gap: var(--spacing-xs);
}

.scale-btn {
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.scale-btn.active {
  background: var(--color-primary);
  color: var(--color-on-primary, #fff);
  border-color: var(--color-primary);
}

/* ── Ingredients grid ───────────────────────────────────── */
.ingredients-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

/* Stack single column if only have or only need */
.ingredients-grid:has(.ingredient-col:only-child) {
  grid-template-columns: 1fr;
}

@media (max-width: 420px) {
  .ingredients-grid {
    grid-template-columns: 1fr;
  }
}

.ingredient-col {
  padding: var(--spacing-sm);
  border-radius: var(--radius-md, 8px);
}

.ingredient-col-have {
  background: var(--color-success-bg, #dcfce7);
}

.ingredient-col-need {
  background: var(--color-warning-bg, #fef9c3);
}

.col-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: var(--spacing-xs);
}

.col-label-have {
  color: var(--color-success, #16a34a);
}

.col-label-need {
  color: var(--color-warning, #ca8a04);
}

.ingredient-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ing-row {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-xs);
  font-size: var(--font-size-sm);
  line-height: 1.4;
}

.ing-icon {
  font-size: 11px;
  flex-shrink: 0;
  font-weight: 700;
}

.ing-icon-have {
  color: var(--color-success, #16a34a);
}

.ing-icon-need {
  color: var(--color-warning, #ca8a04);
}

.ing-name {
  flex: 1;
}

.source-link {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-decoration: none;
  margin-top: var(--spacing-xs);
}

.source-link:hover {
  color: var(--color-primary);
  text-decoration: underline;
}

.col-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-xs);
}

.col-header-row .col-label {
  margin-bottom: 0;
}

.col-header-actions {
  display: flex;
  gap: var(--spacing-xs);
  align-items: center;
}

/* Ingredient checkboxes */
.ing-check-label {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  cursor: pointer;
}

.ing-check {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--color-warning, #ca8a04);
}

.select-all-btn {
  background: transparent;
  border: none;
  color: var(--color-warning, #ca8a04);
  font-size: var(--font-size-xs);
  cursor: pointer;
  padding: var(--spacing-xs) 0;
  text-decoration: underline;
  display: block;
  margin-top: var(--spacing-xs);
}

.select-all-btn:hover {
  opacity: 0.8;
  transform: none;
}

/* Add to pantry footer state */
.add-pantry-col {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 2px;
}

.grocery-actions {
  display: flex;
  gap: var(--spacing-xs);
  align-items: stretch;
}

.add-error {
  color: var(--color-error, #dc2626);
}

.add-success {
  color: var(--color-success, #16a34a);
  font-weight: 600;
}

.btn-accent {
  background: var(--color-success, #16a34a);
  color: #fff;
  border: none;
  border-radius: var(--radius-md, 8px);
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-accent:hover {
  opacity: 0.9;
  transform: none;
}

.btn-accent:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.share-btn {
  background: transparent;
  border: 1px solid var(--color-warning, #ca8a04);
  color: var(--color-warning, #ca8a04);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.share-btn:hover {
  background: var(--color-warning-bg);
}

.buy-link {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
}

.buy-link:hover {
  text-decoration: underline;
}

/* ── Generic detail sections ────────────────────────────── */
.detail-section {
  margin-bottom: var(--spacing-md);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-xs);
}

/* ── Collapsible swaps ──────────────────────────────────── */
.detail-collapsible {
  border-top: 1px solid var(--color-border);
  padding: var(--spacing-sm) 0;
  margin-bottom: var(--spacing-md);
}

.detail-collapsible-summary {
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  list-style: none;
  color: var(--color-primary);
}

.detail-collapsible-summary::-webkit-details-marker {
  display: none;
}

.swap-row {
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
}

.swap-row:last-child {
  border-bottom: none;
}

/* ── Nutrition ──────────────────────────────────────────── */
.nutrition-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.nutrition-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: var(--font-size-xs);
  background: var(--color-bg-secondary, #f5f5f5);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.nutrition-chip-sugar {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.nutrition-chip-servings {
  background: var(--color-info-bg);
  color: var(--color-info-light);
}

.nutrition-chip-estimated {
  font-style: italic;
  opacity: 0.7;
}

/* ── Prep + Directions ──────────────────────────────────── */
.prep-list {
  padding-left: var(--spacing-lg);
  list-style-type: disc;
}

.prep-item {
  margin-bottom: var(--spacing-xs);
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.directions-list {
  padding-left: var(--spacing-lg);
}

.direction-step {
  margin-bottom: var(--spacing-sm);
  line-height: 1.6;
}

/* ── Ingredients collapsible ────────────────────────────── */
.ingredients-collapsible {
  margin-bottom: var(--spacing-md);
}

.ingredients-collapsible-summary {
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
  color: var(--color-text-primary);
}

.ingredients-collapsible-summary::-webkit-details-marker {
  display: none;
}

.ingredients-collapsible-summary::before {
  content: '\25B6';
  font-size: 10px;
  color: var(--color-text-muted);
  transition: transform 0.15s;
  display: inline-block;
}

details[open].ingredients-collapsible .ingredients-collapsible-summary::before {
  transform: rotate(90deg);
}

.ingr-summary-counts {
  display: flex;
  gap: var(--spacing-xs);
  margin-left: auto;
}

.ingr-count {
  font-size: var(--font-size-xs);
  padding: 1px 6px;
  border-radius: var(--radius-pill);
}

.ingr-count-have {
  background: var(--color-success-bg, #dcfce7);
  color: var(--color-success, #16a34a);
}

.ingr-count-need {
  background: var(--color-warning-bg, #fef9c3);
  color: var(--color-warning, #ca8a04);
}

/* ── Effort summary cards ───────────────────────────────── */
.effort-summary {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.effort-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-md, 8px);
  min-width: 64px;
}

.effort-card-active {
  background: var(--color-success-bg, #dcfce7);
}

.effort-card-passive {
  background: var(--color-info-bg, #dbeafe);
}

.effort-card-total {
  background: var(--color-bg-secondary, #f5f5f5);
}

.effort-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.effort-value {
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--color-text-primary);
}

.effort-level-badge {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: capitalize;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  margin-left: auto;
}

.effort-quick {
  background: var(--color-success-bg, #dcfce7);
  color: var(--color-success, #16a34a);
}

.effort-moderate {
  background: var(--color-info-bg, #dbeafe);
  color: var(--color-info-light, #2563eb);
}

.effort-involved {
  background: var(--color-warning-bg, #fef9c3);
  color: var(--color-warning, #ca8a04);
}

/* ── Equipment chips ────────────────────────────────────── */
.equipment-chips {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-md);
}

.equipment-chip {
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--color-bg-secondary, #f5f5f5);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

/* ── Steps collapsible ──────────────────────────────────── */
.steps-collapsible {
  margin-bottom: var(--spacing-md);
}

.steps-collapsible-summary {
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  list-style: none;
  padding: var(--spacing-xs) 0;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.steps-collapsible-summary::-webkit-details-marker {
  display: none;
}

.steps-collapsible-summary::before {
  content: '\25B6';
  font-size: 10px;
  color: var(--color-text-muted);
  transition: transform 0.15s;
  display: inline-block;
}

details[open].steps-collapsible .steps-collapsible-summary::before {
  transform: rotate(90deg);
}

.steps-count {
  color: var(--color-text-muted);
  font-weight: 400;
}

.directions-list-annotated {
  padding-left: var(--spacing-md);
}

.direction-step-annotated {
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm, 4px);
  border-left: 3px solid var(--color-border);
}

.step-passive {
  border-left-color: var(--color-info-light, #60a5fa);
  background: var(--color-info-bg, #dbeafe);
}

.step-badge-row {
  margin-bottom: 4px;
}

.step-type-badge {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
}

.step-type-active {
  background: var(--color-success-bg, #dcfce7);
  color: var(--color-success, #16a34a);
}

.step-type-wait {
  background: var(--color-info-bg, #dbeafe);
  color: var(--color-info-light, #2563eb);
}

.step-text {
  margin: 0;
  line-height: 1.6;
}

.step-passive-hint {
  margin: 4px 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-info-light, #2563eb);
  font-style: italic;
}

/* ── Cook mode bar ──────────────────────────────────────── */
.cook-mode-bar {
  flex-shrink: 0;
  padding: var(--spacing-sm) var(--spacing-md) var(--spacing-xs);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cook-progress-track {
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.cook-progress-fill {
  height: 100%;
  border-radius: 2px;
  background: #f0bc48;
  transition: width 0.25s ease;
}

.cook-step-counter {
  font-size: 11px;
  color: rgba(255, 248, 235, 0.38);
  letter-spacing: 0.02em;
}

/* ── Cook mode step view ────────────────────────────────── */
.cook-step-view {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: var(--spacing-lg) var(--spacing-md) var(--spacing-md);
  gap: var(--spacing-sm);
}

.cook-step-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(255, 248, 235, 0.35);
}

.cook-step-badge-row {
  display: flex;
  gap: var(--spacing-xs);
}

.cook-step-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--font-size-xs);
  font-weight: 600;
  letter-spacing: 0.03em;
}

.cook-badge--active {
  background: rgba(232, 168, 32, 0.18);
  color: #f0bc48;
  border: 1px solid rgba(232, 168, 32, 0.35);
}

.cook-badge--wait {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
  border: 1px solid rgba(96, 165, 250, 0.3);
}

.cook-step-text {
  font-size: 15px;
  font-weight: 500;
  color: rgba(255, 248, 235, 0.92);
  line-height: 1.5;
  margin: 0;
}

.cook-step-hint {
  font-size: 11px;
  color: rgba(255, 248, 235, 0.38);
  margin: 0;
}

/* ── Cook mode navigation ───────────────────────────────── */
.cook-nav {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: auto;
  padding-top: var(--spacing-md);
}

.cook-nav-prev {
  flex: 1;
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  border-radius: var(--radius-md, 8px);
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.cook-nav--disabled {
  opacity: 0.35;
  pointer-events: none;
  cursor: default;
}

.cook-nav-next {
  flex: 2;
  background: rgba(232, 168, 32, 0.18);
  border: 1px solid rgba(232, 168, 32, 0.4);
  color: #f0bc48;
  border-radius: var(--radius-md, 8px);
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.cook-nav-next:hover {
  background: rgba(232, 168, 32, 0.28);
}

.cook-nav--done {
  background: rgba(127, 192, 115, 0.18);
  border-color: rgba(127, 192, 115, 0.4);
  color: #7fc073;
}

.cook-nav--done:hover {
  background: rgba(127, 192, 115, 0.28);
}

/* ── Sticky footer ──────────────────────────────────────── */
.detail-footer {
  padding: var(--spacing-md);
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
  background: var(--color-bg-card);
  flex-shrink: 0;
}

.btn-bookmark-panel {
  background: var(--color-bg-secondary, #f5f5f5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  padding: 6px 12px;
  font-size: 16px;
  line-height: 1;
  color: var(--color-text-muted);
  flex-shrink: 0;
  transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.btn-bookmark-panel:hover,
.btn-bookmark-panel.active {
  color: var(--color-warning, #ca8a04);
  background: var(--color-warning-bg, #fef9c3);
  border-color: var(--color-warning, #ca8a04);
  transform: none;
}

.cook-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  text-align: center;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-success, #16a34a);
  gap: var(--spacing-xs);
}

.cook-success-icon {
  font-size: 24px;
  display: block;
}

.inline-spinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: var(--spacing-xs);
}

.mt-xs {
  margin-top: var(--spacing-xs);
}

.ml-xs {
  margin-left: var(--spacing-xs);
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
}
</style>
