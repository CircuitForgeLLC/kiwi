<template>
  <div class="recipes-view">
    <!-- Controls Panel -->
    <div class="card mb-controls">
      <h2 class="text-xl font-bold mb-md">Find Recipes</h2>

      <!-- Level Selector -->
      <div class="form-group">
        <label class="form-label">Creativity Level</label>
        <div class="flex flex-wrap gap-sm">
          <button
            v-for="lvl in levels"
            :key="lvl.value"
            :class="['btn', 'btn-secondary', { active: recipesStore.level === lvl.value }]"
            @click="recipesStore.level = lvl.value"
          >
            {{ lvl.label }}
          </button>
        </div>
      </div>

      <!-- Wildcard warning -->
      <div v-if="recipesStore.level === 4" class="status-badge status-warning wildcard-warning">
        Wildcard mode uses LLM to generate creative recipes with whatever you have. Results may be
        unusual.
        <label class="flex-start gap-sm mt-xs">
          <input type="checkbox" v-model="recipesStore.wildcardConfirmed" />
          <span>I understand, go for it</span>
        </label>
      </div>

      <!-- Dietary Constraints Tags -->
      <div class="form-group">
        <label class="form-label">Dietary Constraints</label>
        <div class="tags-wrap flex flex-wrap gap-xs mb-xs">
          <span
            v-for="tag in recipesStore.constraints"
            :key="tag"
            class="tag-chip status-badge status-info"
          >
            {{ tag }}
            <button class="chip-remove" @click="removeConstraint(tag)" aria-label="Remove">×</button>
          </span>
        </div>
        <input
          class="form-input"
          v-model="constraintInput"
          placeholder="e.g. vegetarian, vegan, gluten-free — press Enter or comma"
          @keydown="onConstraintKey"
          @blur="commitConstraintInput"
        />
      </div>

      <!-- Allergies Tags -->
      <div class="form-group">
        <label class="form-label">Allergies (hard exclusions)</label>
        <div class="tags-wrap flex flex-wrap gap-xs mb-xs">
          <span
            v-for="tag in recipesStore.allergies"
            :key="tag"
            class="tag-chip status-badge status-error"
          >
            {{ tag }}
            <button class="chip-remove" @click="removeAllergy(tag)" aria-label="Remove">×</button>
          </span>
        </div>
        <input
          class="form-input"
          v-model="allergyInput"
          placeholder="e.g. peanuts, shellfish, dairy — press Enter or comma"
          @keydown="onAllergyKey"
          @blur="commitAllergyInput"
        />
      </div>

      <!-- Hard Day Mode -->
      <div class="form-group">
        <label class="flex-start gap-sm hard-day-toggle">
          <input type="checkbox" v-model="recipesStore.hardDayMode" />
          <span class="form-label" style="margin-bottom: 0;">Hard Day Mode</span>
        </label>
        <p v-if="recipesStore.hardDayMode" class="text-sm text-secondary mt-xs">
          Only suggests quick, simple recipes based on your saved equipment.
        </p>
      </div>

      <!-- Max Missing -->
      <div class="form-group">
        <label class="form-label">Max Missing Ingredients (optional)</label>
        <input
          type="number"
          class="form-input"
          min="0"
          max="5"
          placeholder="Leave blank for no limit"
          :value="recipesStore.maxMissing ?? ''"
          @input="onMaxMissingInput"
        />
      </div>

      <!-- Suggest Button -->
      <button
        class="btn btn-primary btn-lg w-full"
        :disabled="recipesStore.loading || pantryItems.length === 0 || (recipesStore.level === 4 && !recipesStore.wildcardConfirmed)"
        @click="handleSuggest"
      >
        <span v-if="recipesStore.loading">
          <span class="spinner spinner-sm inline-spinner"></span> Finding recipes…
        </span>
        <span v-else>🍳 Suggest Recipes</span>
      </button>

      <!-- Empty pantry nudge -->
      <p v-if="pantryItems.length === 0 && !recipesStore.loading" class="text-sm text-muted text-center mt-xs">
        Add items to your pantry first, then tap Suggest to find recipes.
      </p>
    </div>

    <!-- Error -->
    <div v-if="recipesStore.error" class="status-badge status-error mb-md">
      {{ recipesStore.error }}
    </div>

    <!-- Results -->
    <div v-if="recipesStore.result" class="results-section fade-in">
      <!-- Rate limit warning -->
      <div
        v-if="recipesStore.result.rate_limited"
        class="status-badge status-warning rate-limit-banner mb-md"
      >
        You've used your {{ recipesStore.result.rate_limit_count }} free suggestions today. Upgrade for
        unlimited.
      </div>

      <!-- Element gaps -->
      <div v-if="recipesStore.result.element_gaps.length > 0" class="card card-warning mb-md">
        <p class="text-sm font-semibold">Your pantry is missing some flavor elements:</p>
        <div class="flex flex-wrap gap-xs mt-xs">
          <span
            v-for="gap in recipesStore.result.element_gaps"
            :key="gap"
            class="status-badge status-warning"
          >{{ gap }}</span>
        </div>
      </div>

      <!-- No suggestions -->
      <div
        v-if="recipesStore.result.suggestions.length === 0"
        class="card text-center text-muted"
      >
        <p>No recipes found for your current pantry and settings. Try lowering the creativity level or adding more items.</p>
      </div>

      <!-- Recipe Cards -->
      <div class="grid-auto mb-md">
        <div
          v-for="recipe in recipesStore.result.suggestions"
          :key="recipe.id"
          class="card slide-up"
        >
          <!-- Header row -->
          <div class="flex-between mb-sm">
            <h3 class="text-lg font-bold recipe-title">{{ recipe.title }}</h3>
            <div class="flex flex-wrap gap-xs">
              <span class="status-badge status-success">{{ recipe.match_count }} matched</span>
              <span class="status-badge status-info">Level {{ recipe.level }}</span>
              <span v-if="recipe.is_wildcard" class="status-badge status-warning">Wildcard 🎲</span>
            </div>
          </div>

          <!-- Notes -->
          <p v-if="recipe.notes" class="text-sm text-secondary mb-sm">{{ recipe.notes }}</p>

          <!-- Missing ingredients -->
          <div v-if="recipe.missing_ingredients.length > 0" class="mb-sm">
            <p class="text-sm font-semibold text-warning">You'd need:</p>
            <div class="flex flex-wrap gap-xs mt-xs">
              <span
                v-for="ing in recipe.missing_ingredients"
                :key="ing"
                class="status-badge status-warning"
              >{{ ing }}</span>
            </div>
          </div>

          <!-- Grocery links for this recipe's missing ingredients -->
          <div v-if="groceryLinksForRecipe(recipe).length > 0" class="mb-sm">
            <p class="text-sm font-semibold">Buy online:</p>
            <div class="flex flex-wrap gap-xs mt-xs">
              <a
                v-for="link in groceryLinksForRecipe(recipe)"
                :key="link.ingredient + link.retailer"
                :href="link.url"
                target="_blank"
                rel="noopener noreferrer"
                class="grocery-link status-badge status-info"
              >
                {{ link.ingredient }} @ {{ link.retailer }} ↗
              </a>
            </div>
          </div>

          <!-- Swap candidates collapsible -->
          <details v-if="recipe.swap_candidates.length > 0" class="collapsible mb-sm">
            <summary class="text-sm font-semibold collapsible-summary">
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

          <!-- Directions collapsible -->
          <details v-if="recipe.directions.length > 0" class="collapsible">
            <summary class="text-sm font-semibold collapsible-summary">
              Directions ({{ recipe.directions.length }} steps)
            </summary>
            <ol class="directions-list mt-xs">
              <li v-for="(step, idx) in recipe.directions" :key="idx" class="text-sm direction-step">
                {{ step }}
              </li>
            </ol>
          </details>
        </div>
      </div>

      <!-- Grocery list summary -->
      <div v-if="recipesStore.result.grocery_list.length > 0" class="card card-info">
        <h3 class="text-lg font-bold mb-sm">Shopping List</h3>
        <ul class="grocery-list">
          <li
            v-for="item in recipesStore.result.grocery_list"
            :key="item"
            class="text-sm grocery-item"
          >
            {{ item }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Empty state when no results yet and pantry has items -->
    <div
      v-if="!recipesStore.result && !recipesStore.loading && pantryItems.length > 0"
      class="card text-center text-muted"
    >
      <p class="text-lg">🍳</p>
      <p class="mt-xs">Tap "Suggest Recipes" to find recipes using your pantry items.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRecipesStore } from '../stores/recipes'
import { useInventoryStore } from '../stores/inventory'
import type { RecipeSuggestion, GroceryLink } from '../services/api'

const recipesStore = useRecipesStore()
const inventoryStore = useInventoryStore()

// Local input state for tags
const constraintInput = ref('')
const allergyInput = ref('')

const levels = [
  { value: 1, label: '1 — From Pantry' },
  { value: 2, label: '2 — Creative Swaps' },
  { value: 3, label: '3 — AI Scaffold' },
  { value: 4, label: '4 — Wildcard 🎲' },
]

// Pantry items sorted expiry-first (available items only)
const pantryItems = computed(() => {
  const sorted = [...inventoryStore.items]
    .filter((item) => item.status === 'available')
    .sort((a, b) => {
      if (!a.expiration_date && !b.expiration_date) return 0
      if (!a.expiration_date) return 1
      if (!b.expiration_date) return -1
      return new Date(a.expiration_date).getTime() - new Date(b.expiration_date).getTime()
    })
  return sorted.map((item) => item.product.name)
})

// Grocery links relevant to a specific recipe's missing ingredients
function groceryLinksForRecipe(recipe: RecipeSuggestion): GroceryLink[] {
  if (!recipesStore.result) return []
  return recipesStore.result.grocery_links.filter((link) =>
    recipe.missing_ingredients.includes(link.ingredient)
  )
}

// Tag input helpers — constraints
function addConstraint(value: string) {
  const tag = value.trim().toLowerCase()
  if (tag && !recipesStore.constraints.includes(tag)) {
    recipesStore.constraints = [...recipesStore.constraints, tag]
  }
  constraintInput.value = ''
}

function removeConstraint(tag: string) {
  recipesStore.constraints = recipesStore.constraints.filter((c) => c !== tag)
}

function onConstraintKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addConstraint(constraintInput.value)
  }
}

function commitConstraintInput() {
  if (constraintInput.value.trim()) {
    addConstraint(constraintInput.value)
  }
}

// Tag input helpers — allergies
function addAllergy(value: string) {
  const tag = value.trim().toLowerCase()
  if (tag && !recipesStore.allergies.includes(tag)) {
    recipesStore.allergies = [...recipesStore.allergies, tag]
  }
  allergyInput.value = ''
}

function removeAllergy(tag: string) {
  recipesStore.allergies = recipesStore.allergies.filter((a) => a !== tag)
}

function onAllergyKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addAllergy(allergyInput.value)
  }
}

function commitAllergyInput() {
  if (allergyInput.value.trim()) {
    addAllergy(allergyInput.value)
  }
}

// Max missing number input
function onMaxMissingInput(e: Event) {
  const target = e.target as HTMLInputElement
  const val = parseInt(target.value)
  recipesStore.maxMissing = isNaN(val) ? null : val
}

// Suggest handler
async function handleSuggest() {
  await recipesStore.suggest(pantryItems.value)
}

onMounted(async () => {
  if (inventoryStore.items.length === 0) {
    await inventoryStore.fetchItems()
  }
})
</script>

<style scoped>
.mb-controls {
  margin-bottom: var(--spacing-md);
}

.mb-md {
  margin-bottom: var(--spacing-md);
}

.mb-sm {
  margin-bottom: var(--spacing-sm);
}

.mt-xs {
  margin-top: var(--spacing-xs);
}

.ml-xs {
  margin-left: var(--spacing-xs);
}

.wildcard-warning {
  display: block;
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
}

.hard-day-toggle {
  cursor: pointer;
  user-select: none;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.chip-remove {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
  line-height: 1;
  color: inherit;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.chip-remove:hover {
  opacity: 1;
  transform: none;
}

.inline-spinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: var(--spacing-xs);
}

.rate-limit-banner {
  display: block;
  padding: var(--spacing-sm) var(--spacing-md);
}

.recipe-title {
  flex: 1;
  margin-right: var(--spacing-sm);
}

.collapsible {
  border-top: 1px solid var(--color-border);
  padding-top: var(--spacing-sm);
}

.collapsible-summary {
  cursor: pointer;
  list-style: none;
  padding: var(--spacing-xs) 0;
  color: var(--color-primary);
}

.collapsible-summary::-webkit-details-marker {
  display: none;
}

.collapsible-summary::before {
  content: '▶ ';
  font-size: 10px;
}

details[open] .collapsible-summary::before {
  content: '▼ ';
}

.swap-row {
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
}

.swap-row:last-child {
  border-bottom: none;
}

.directions-list {
  padding-left: var(--spacing-lg);
}

.direction-step {
  margin-bottom: var(--spacing-xs);
  line-height: 1.5;
}

.grocery-link {
  text-decoration: none;
  cursor: pointer;
  transition: opacity 0.2s;
}

.grocery-link:hover {
  opacity: 0.8;
}

.grocery-list {
  padding-left: var(--spacing-lg);
}

.grocery-item {
  margin-bottom: var(--spacing-xs);
}

.results-section {
  margin-top: var(--spacing-md);
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .flex-between {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-xs);
  }

  .recipe-title {
    margin-right: 0;
  }
}
</style>
