<template>
  <div class="byo-tab">

    <!-- ── Step 0: Template grid ─────────────────────────────────── -->
    <div v-if="phase === 'select'" class="byo-section">
      <h2 class="section-title text-xl mb-sm">Build Your Own Recipe</h2>
      <p class="text-sm text-secondary mb-md">
        Choose a style, then pick your ingredients one step at a time.
      </p>

      <div v-if="templatesLoading" class="text-secondary text-sm">Loading templates…</div>
      <div v-else-if="templatesError" role="alert" class="status-badge status-error mb-md">
        {{ templatesError }}
      </div>
      <div v-else class="template-grid" role="list">
        <button
          v-for="tmpl in templates"
          :key="tmpl.id"
          class="template-card card"
          role="listitem"
          :aria-label="tmpl.title + ': ' + tmpl.descriptor"
          @click="selectTemplate(tmpl)"
        >
          <span class="tmpl-icon" aria-hidden="true">{{ tmpl.icon }}</span>
          <span class="tmpl-title">{{ tmpl.title }}</span>
          <span class="tmpl-descriptor text-sm text-secondary">{{ tmpl.descriptor }}</span>
        </button>
      </div>
    </div>

    <!-- ── Step 1+: Ingredient wizard ───────────────────────────── -->
    <div v-else-if="phase === 'wizard'" class="byo-section">
      <!-- Back + step counter -->
      <div class="byo-nav mb-sm">
        <button class="btn btn-sm btn-secondary" @click="goBack">← Back</button>
        <span class="text-sm text-secondary step-counter">Step {{ wizardStep + 1 }} of {{ totalSteps }}</span>
      </div>

      <h2 class="section-title text-xl mb-xs">What's your {{ currentRole?.display }}?</h2>
      <p v-if="currentRole?.hint" class="text-sm text-secondary mb-md">{{ currentRole.hint }}</p>

      <!-- Missing ingredient mode toggle -->
      <div class="mode-toggle mb-sm" role="radiogroup" aria-label="Missing ingredients">
        <button
          v-for="mode in missingModes"
          :key="mode.value"
          :class="['btn', 'btn-sm', recipesStore.missingIngredientMode === mode.value ? 'btn-primary' : 'btn-secondary']"
          :aria-checked="recipesStore.missingIngredientMode === mode.value"
          role="radio"
          @click="recipesStore.missingIngredientMode = mode.value as any"
        >{{ mode.label }}</button>
      </div>

      <!-- Filter row: text search or tag cloud -->
      <div class="filter-row mb-sm">
        <input
          v-if="recipesStore.builderFilterMode === 'text'"
          v-model="filterText"
          class="form-input filter-input"
          :placeholder="'Search ' + (currentRole?.display ?? 'ingredients') + '…'"
          aria-label="Search ingredients"
        />
        <div
          v-else
          class="tag-cloud"
          role="group"
          aria-label="Filter by tag"
        >
          <button
            v-for="tag in candidates?.available_tags ?? []"
            :key="tag"
            :class="['btn', 'btn-sm', 'tag-chip', selectedTags.has(tag) ? 'tag-active' : '']"
            :aria-pressed="selectedTags.has(tag)"
            @click="toggleTag(tag)"
          >{{ tag }}</button>
          <span v-if="(candidates?.available_tags ?? []).length === 0" class="text-secondary text-sm">
            No tags available for this ingredient set.
          </span>
        </div>
        <button
          class="btn btn-sm btn-secondary filter-mode-btn"
          :aria-pressed="recipesStore.builderFilterMode === 'tags'"
          :aria-label="recipesStore.builderFilterMode === 'text' ? 'Switch to tag filter' : 'Switch to text search'"
          @click="recipesStore.builderFilterMode = recipesStore.builderFilterMode === 'text' ? 'tags' : 'text'"
        >{{ recipesStore.builderFilterMode === 'text' ? '🏷️' : '🔍' }}</button>
      </div>

      <!-- Candidates loading / error -->
      <div v-if="candidatesLoading" class="text-secondary text-sm mb-sm">Loading options…</div>
      <div v-else-if="candidatesError" role="alert" class="status-badge status-error mb-sm">
        {{ candidatesError }}
      </div>

      <!-- Compatible candidates -->
      <div v-if="filteredCompatible.length > 0" class="candidates-section mb-sm">
        <p class="text-xs font-semibold text-secondary mb-xs" aria-hidden="true">Available</p>
        <div class="ingredient-grid">
          <button
            v-for="item in filteredCompatible"
            :key="item.name"
            :class="['ingredient-card', 'btn', selectedInRole.has(item.name) ? 'ingredient-active' : '']"
            :aria-pressed="selectedInRole.has(item.name)"
            :aria-label="item.name + (item.in_pantry ? '' : ' — not in pantry')"
            @click="toggleIngredient(item.name)"
          >
            <span class="ingredient-name">{{ item.name }}</span>
            <span v-if="!item.in_pantry && recipesStore.missingIngredientMode === 'add-to-cart'"
                  class="cart-icon" aria-hidden="true">🛒</span>
          </button>
        </div>
      </div>

      <!-- Other candidates (greyed or add-to-cart mode only) -->
      <template v-if="recipesStore.missingIngredientMode !== 'hidden' && filteredOther.length > 0">
        <div class="candidates-separator text-xs text-secondary mb-xs">also works</div>
        <div class="ingredient-grid ingredient-grid-other mb-sm">
          <button
            v-for="item in filteredOther"
            :key="item.name"
            :class="['ingredient-card', 'btn',
                     item.in_pantry ? '' : 'ingredient-missing',
                     selectedInRole.has(item.name) ? 'ingredient-active' : '']"
            :aria-pressed="selectedInRole.has(item.name)"
            :aria-label="item.name + (item.in_pantry ? '' : ' — not in pantry')"
            :disabled="!item.in_pantry && recipesStore.missingIngredientMode === 'greyed'"
            @click="item.in_pantry || recipesStore.missingIngredientMode !== 'greyed' ? toggleIngredient(item.name) : undefined"
          >
            <span class="ingredient-name">{{ item.name }}</span>
            <span v-if="!item.in_pantry && recipesStore.missingIngredientMode === 'add-to-cart'"
                  class="cart-icon" aria-hidden="true">🛒</span>
          </button>
        </div>
      </template>

      <!-- No-match state: nothing compatible AND nothing visible in other section.
           filteredOther items are hidden when mode is 'hidden', so check visibility too. -->
      <template v-if="!candidatesLoading && !candidatesError && filteredCompatible.length === 0 && (filteredOther.length === 0 || recipesStore.missingIngredientMode === 'hidden')">
        <!-- Custom freeform input: text filter with no matches → offer "use anyway" -->
        <div v-if="recipesStore.builderFilterMode === 'text' && filterText.trim().length > 0" class="custom-ingredient-prompt mb-sm">
          <p class="text-sm text-secondary mb-xs">
            No match for "{{ filterText.trim() }}" in your pantry.
          </p>
          <button class="btn btn-secondary" @click="useCustomIngredient">
            Use "{{ filterText.trim() }}" anyway
          </button>
        </div>
        <!-- No pantry items at all for this role -->
        <p v-else class="text-sm text-secondary mb-sm">
          Nothing in your pantry fits this role yet. You can skip it or
          <button class="btn-link" @click="recipesStore.missingIngredientMode = 'greyed'">show options to add.</button>
        </p>
      </template>

      <!-- Skip / Next -->
      <div class="byo-actions">
        <button
          v-if="!currentRole?.required"
          class="btn btn-secondary"
          @click="advanceStep"
        >Skip (optional)</button>
        <button
          v-else-if="currentRole?.required && selectedInRole.size === 0"
          class="btn btn-secondary"
          @click="advanceStep"
        >I'll add this later</button>
        <button
          class="btn btn-primary"
          :disabled="buildLoading"
          @click="wizardStep < totalSteps - 1 ? advanceStep() : buildRecipe()"
        >
          {{ wizardStep < totalSteps - 1 ? 'Next →' : 'Build this recipe' }}
        </button>
      </div>
    </div>

    <!-- ── Result ─────────────────────────────────────────────────── -->
    <div v-else-if="phase === 'result'" class="byo-section">
      <div v-if="buildLoading" class="text-secondary text-sm mb-md">Building your recipe…</div>
      <div v-else-if="buildError" role="alert" class="status-badge status-error mb-md">
        {{ buildError }}
      </div>
      <template v-else-if="builtRecipe">
        <RecipeDetailPanel
          :recipe="builtRecipe"
          :grocery-links="[]"
          @close="phase = 'select'"
          @cooked="phase = 'select'"
        />
        <!-- Shopping list: items the user chose that aren't in their pantry -->
        <div v-if="(builtRecipe.missing_ingredients ?? []).length > 0" class="cart-list card mb-sm">
          <h3 class="text-sm font-semibold mb-xs">🛒 You'll need to pick up</h3>
          <ul class="cart-items">
            <li v-for="item in builtRecipe.missing_ingredients" :key="item" class="cart-item text-sm">{{ item }}</li>
          </ul>
        </div>
        <div class="byo-actions mt-sm">
          <button class="btn btn-secondary" @click="resetToTemplate">Try a different build</button>
          <button class="btn btn-secondary" @click="phase = 'wizard'">Adjust ingredients</button>
        </div>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRecipesStore } from '../stores/recipes'
import RecipeDetailPanel from './RecipeDetailPanel.vue'
import { recipesAPI, type AssemblyTemplateOut, type RoleCandidatesResponse, type RecipeSuggestion } from '../services/api'

const recipesStore = useRecipesStore()

type Phase = 'select' | 'wizard' | 'result'
const phase = ref<Phase>('select')

// Template grid state
const templates = ref<AssemblyTemplateOut[]>([])
const templatesLoading = ref(false)
const templatesError = ref<string | null>(null)

// Wizard state
const selectedTemplate = ref<AssemblyTemplateOut | null>(null)
const wizardStep = ref(0)
const roleOverrides = ref<Record<string, string[]>>({})

// Candidates for current step
const candidates = ref<RoleCandidatesResponse | null>(null)
const candidatesLoading = ref(false)
const candidatesError = ref<string | null>(null)

// Filter state (reset on step advance)
const filterText = ref('')
const selectedTags = ref<Set<string>>(new Set())

// Result state
const builtRecipe = ref<RecipeSuggestion | null>(null)
const buildLoading = ref(false)
const buildError = ref<string | null>(null)

// Shopping list is derived from builtRecipe.missing_ingredients (computed by backend)

const missingModes = [
  { label: 'Available only', value: 'hidden' },
  { label: 'Show missing',   value: 'greyed' },
  { label: 'Add to cart',    value: 'add-to-cart' },
]

const totalSteps = computed(() => selectedTemplate.value?.role_sequence.length ?? 0)
const currentRole = computed(() => selectedTemplate.value?.role_sequence[wizardStep.value] ?? null)

const selectedInRole = computed<Set<string>>(() => {
  const role = currentRole.value?.display
  if (!role) return new Set()
  return new Set(roleOverrides.value[role] ?? [])
})

const priorPicks = computed<string[]>(() => {
  if (!selectedTemplate.value) return []
  return selectedTemplate.value.role_sequence
    .slice(0, wizardStep.value)
    .flatMap((r) => roleOverrides.value[r.display] ?? [])
})

const filteredCompatible = computed(() => applyFilter(candidates.value?.compatible ?? []))
const filteredOther = computed(() => applyFilter(candidates.value?.other ?? []))

function applyFilter(items: RoleCandidatesResponse['compatible']) {
  if (recipesStore.builderFilterMode === 'text') {
    const q = filterText.value.trim().toLowerCase()
    if (!q) return items
    return items.filter((i) => i.name.toLowerCase().includes(q))
  } else {
    if (selectedTags.value.size === 0) return items
    return items.filter((i) =>
      [...selectedTags.value].every((tag) => i.tags.includes(tag))
    )
  }
}

function toggleTag(tag: string) {
  const next = new Set(selectedTags.value)
  next.has(tag) ? next.delete(tag) : next.add(tag)
  selectedTags.value = next
}

function toggleIngredient(name: string) {
  const role = currentRole.value?.display
  if (!role) return
  const current = new Set(roleOverrides.value[role] ?? [])
  current.has(name) ? current.delete(name) : current.add(name)
  roleOverrides.value = { ...roleOverrides.value, [role]: [...current] }

}

function useCustomIngredient() {
  const name = filterText.value.trim()
  if (!name) return
  const role = currentRole.value?.display
  if (!role) return

  // Add to role overrides so it's included in the build request
  const current = new Set(roleOverrides.value[role] ?? [])
  current.add(name)
  roleOverrides.value = { ...roleOverrides.value, [role]: [...current] }

  // Inject into the local candidates list so it renders as a selected card.
  // Mark in_pantry: true so it stays visible regardless of missing-ingredient mode.
  if (candidates.value) {
    const knownNames = new Set([
      ...(candidates.value.compatible ?? []).map((i) => i.name.toLowerCase()),
      ...(candidates.value.other ?? []).map((i) => i.name.toLowerCase()),
    ])
    if (!knownNames.has(name.toLowerCase())) {
      candidates.value = {
        ...candidates.value,
        compatible: [{ name, in_pantry: true, tags: [] }, ...(candidates.value.compatible ?? [])],
      }
    }
  }

  filterText.value = ''
}

async function selectTemplate(tmpl: AssemblyTemplateOut) {
  selectedTemplate.value = tmpl
  wizardStep.value = 0
  roleOverrides.value = {}
  phase.value = 'wizard'
  await loadCandidates()
}

async function loadCandidates() {
  if (!selectedTemplate.value || !currentRole.value) return
  candidatesLoading.value = true
  candidatesError.value = null
  filterText.value = ''
  selectedTags.value = new Set()
  try {
    candidates.value = await recipesAPI.getRoleCandidates(
      selectedTemplate.value.id,
      currentRole.value.display,
      priorPicks.value,
    )
  } catch {
    candidatesError.value = 'Could not load ingredient options. Please try again.'
  } finally {
    candidatesLoading.value = false
  }
}

async function advanceStep() {
  if (!selectedTemplate.value) return
  if (wizardStep.value < totalSteps.value - 1) {
    wizardStep.value++
    await loadCandidates()
  }
}

function goBack() {
  if (phase.value === 'result') {
    phase.value = 'wizard'
    return
  }
  if (wizardStep.value > 0) {
    wizardStep.value--
    loadCandidates()
  } else {
    phase.value = 'select'
    selectedTemplate.value = null
  }
}

async function buildRecipe() {
  if (!selectedTemplate.value) return
  buildLoading.value = true
  buildError.value = null
  phase.value = 'result'

  const overrides: Record<string, string> = {}
  for (const [role, picks] of Object.entries(roleOverrides.value)) {
    if (picks.length > 0) overrides[role] = picks[0]!
  }

  try {
    builtRecipe.value = await recipesAPI.buildRecipe({
      template_id: selectedTemplate.value.id,
      role_overrides: overrides,
    })
  } catch {
    buildError.value = 'Could not build recipe. Try adjusting your ingredients.'
  } finally {
    buildLoading.value = false
  }
}

function resetToTemplate() {
  phase.value = 'select'
  selectedTemplate.value = null
  wizardStep.value = 0
  roleOverrides.value = {}
  builtRecipe.value = null
  buildError.value = null
}

onMounted(async () => {
  templatesLoading.value = true
  try {
    templates.value = await recipesAPI.getTemplates()
  } catch {
    templatesError.value = 'Could not load templates. Please refresh.'
  } finally {
    templatesLoading.value = false
  }
})
</script>

<style scoped>
.byo-tab {
  padding: var(--spacing-sm) 0;
}

.byo-section {
  max-width: 640px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
}

@media (min-width: 640px) {
  .template-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.template-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--spacing-xs);
  padding: var(--spacing-md);
  text-align: left;
  cursor: pointer;
}

.tmpl-icon {
  font-size: 1.5rem;
}

.tmpl-title {
  font-weight: 600;
  font-size: 0.95rem;
}

.tmpl-descriptor {
  line-height: 1.35;
}

.byo-nav {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.step-counter {
  margin-left: auto;
}

.mode-toggle {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.filter-row {
  display: flex;
  gap: var(--spacing-xs);
  align-items: flex-start;
}

.filter-input {
  flex: 1;
}

.filter-mode-btn {
  flex-shrink: 0;
  min-width: 36px;
}

.tag-cloud {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.tag-active {
  background: var(--color-primary);
  color: var(--color-bg-primary);
}

.ingredient-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-xs);
}

@media (min-width: 640px) {
  .ingredient-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.ingredient-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
  min-height: 44px;
  cursor: pointer;
}

.ingredient-active {
  border: 2px solid var(--color-primary);
  background: var(--color-primary-light);
  color: var(--color-bg-primary);
}

.ingredient-missing {
  opacity: 0.55;
}

.ingredient-name {
  flex: 1;
  font-size: 0.9rem;
}

.cart-icon {
  font-size: 0.85rem;
  margin-left: var(--spacing-xs);
}

.candidates-separator {
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-xs);
  border-top: 1px solid var(--color-border);
}

.byo-actions {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.btn-link {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.cart-list {
  padding: var(--spacing-sm) var(--spacing-md);
}

.cart-items {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}

.cart-item {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 2px var(--spacing-sm);
}
</style>
