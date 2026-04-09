<template>
  <div class="browser-panel">
    <!-- Domain picker -->
    <div class="domain-picker flex flex-wrap gap-sm mb-md">
      <button
        v-for="domain in domains"
        :key="domain.id"
        :class="['btn', activeDomain === domain.id ? 'btn-primary' : 'btn-secondary']"
        @click="selectDomain(domain.id)"
      >
        {{ domain.label }}
      </button>
    </div>

    <div v-if="loadingDomains" class="text-secondary text-sm">Loading…</div>

    <div v-else-if="activeDomain" class="browser-body">
      <!-- Category list + Surprise Me -->
      <div class="category-list mb-md flex flex-wrap gap-xs">
        <button
          v-for="cat in categories"
          :key="cat.category"
          :class="['btn', 'btn-secondary', 'cat-btn', { active: activeCategory === cat.category }]"
          @click="selectCategory(cat.category)"
        >
          {{ cat.category }}
          <span class="cat-count">{{ cat.recipe_count }}</span>
        </button>
        <button
          v-if="categories.length > 1"
          class="btn btn-secondary cat-btn surprise-btn"
          @click="surpriseMe"
          title="Pick a random category"
        >
          🎲 Surprise me
        </button>
      </div>

      <!-- Recipe grid -->
      <template v-if="activeCategory">
        <div v-if="loadingRecipes" class="text-secondary text-sm">Loading recipes…</div>

        <template v-else>
          <div class="results-header flex-between mb-sm">
            <span class="text-sm text-secondary">
              {{ total }} recipes
              <span v-if="pantryCount > 0"> — pantry match shown</span>
            </span>
            <div class="pagination flex gap-xs">
              <button
                class="btn btn-secondary btn-xs"
                :disabled="page <= 1"
                @click="changePage(page - 1)"
              >‹ Prev</button>
              <span class="text-sm text-secondary page-indicator">{{ page }} / {{ totalPages }}</span>
              <button
                class="btn btn-secondary btn-xs"
                :disabled="page >= totalPages"
                @click="changePage(page + 1)"
              >Next ›</button>
            </div>
          </div>

          <div v-if="recipes.length === 0" class="text-secondary text-sm">No recipes found in this category.</div>

          <div class="recipe-grid">
            <div
              v-for="recipe in recipes"
              :key="recipe.id"
              class="card-sm recipe-row flex-between gap-sm"
            >
              <button
                class="recipe-title-btn text-left"
                @click="$emit('open-recipe', recipe.id)"
              >
                {{ recipe.title }}
              </button>

              <div class="recipe-row-actions flex gap-xs flex-shrink-0">
                <!-- Pantry match badge -->
                <span
                  v-if="recipe.match_pct !== null"
                  class="match-badge status-badge"
                  :class="matchBadgeClass(recipe.match_pct)"
                >
                  {{ Math.round(recipe.match_pct * 100) }}%
                </span>

                <!-- Save toggle -->
                <button
                  class="btn btn-secondary btn-xs"
                  :class="{ 'btn-saved': savedStore.isSaved(recipe.id) }"
                  @click="toggleSave(recipe)"
                  :aria-label="savedStore.isSaved(recipe.id) ? 'Edit saved recipe: ' + recipe.title : 'Save recipe: ' + recipe.title"
                >
                  {{ savedStore.isSaved(recipe.id) ? '★' : '☆' }}
                </button>
              </div>
            </div>
          </div>
        </template>
      </template>

      <div v-else class="text-secondary text-sm">Loading recipes…</div>
    </div>

    <div v-else-if="!loadingDomains" class="text-secondary text-sm">Loading…</div>

    <!-- Save modal -->
    <SaveRecipeModal
      v-if="savingRecipe"
      :recipe-id="savingRecipe.id"
      :recipe-title="savingRecipe.title"
      @close="savingRecipe = null"
      @saved="savingRecipe = null"
      @unsave="savingRecipe && doUnsave(savingRecipe.id)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { browserAPI, type BrowserDomain, type BrowserCategory, type BrowserRecipe } from '../services/api'
import { useSavedRecipesStore } from '../stores/savedRecipes'
import { useInventoryStore } from '../stores/inventory'
import SaveRecipeModal from './SaveRecipeModal.vue'

defineEmits<{
  (e: 'open-recipe', recipeId: number): void
}>()

const savedStore = useSavedRecipesStore()
const inventoryStore = useInventoryStore()

const domains = ref<BrowserDomain[]>([])
const activeDomain = ref<string | null>(null)
const categories = ref<BrowserCategory[]>([])
const activeCategory = ref<string | null>(null)
const recipes = ref<BrowserRecipe[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loadingDomains = ref(false)
const loadingRecipes = ref(false)
const savingRecipe = ref<BrowserRecipe | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const pantryItems = computed(() =>
  inventoryStore.items
    .filter((i) => i.status === 'available' && i.product_name)
    .map((i) => i.product_name as string)
)
const pantryCount = computed(() => pantryItems.value.length)

function matchBadgeClass(pct: number): string {
  if (pct >= 0.8) return 'status-success'
  if (pct >= 0.5) return 'status-warning'
  return 'status-secondary'
}

onMounted(async () => {
  loadingDomains.value = true
  try {
    domains.value = await browserAPI.listDomains()
    if (domains.value.length > 0) selectDomain(domains.value[0]!.id)
  } finally {
    loadingDomains.value = false
  }
  // Ensure pantry is loaded for match badges
  if (inventoryStore.items.length === 0) inventoryStore.fetchItems()
  if (!savedStore.savedIds.size) savedStore.load()
})

async function selectDomain(domainId: string) {
  activeDomain.value = domainId
  activeCategory.value = null
  recipes.value = []
  total.value = 0
  page.value = 1
  categories.value = await browserAPI.listCategories(domainId)
  // Auto-select the most-populated category so content appears immediately
  if (categories.value.length > 0) {
    const top = categories.value.reduce((best, c) =>
      c.recipe_count > best.recipe_count ? c : best, categories.value[0]!)
    selectCategory(top.category)
  }
}

function surpriseMe() {
  if (categories.value.length === 0) return
  const pick = categories.value[Math.floor(Math.random() * categories.value.length)]!
  selectCategory(pick.category)
}

async function selectCategory(category: string) {
  activeCategory.value = category
  page.value = 1
  await loadRecipes()
}

async function changePage(newPage: number) {
  page.value = newPage
  await loadRecipes()
}

async function loadRecipes() {
  if (!activeDomain.value || !activeCategory.value) return
  loadingRecipes.value = true
  try {
    const result = await browserAPI.browse(
      activeDomain.value,
      activeCategory.value,
      {
        page: page.value,
        page_size: pageSize,
        pantry_items: pantryItems.value.length > 0
          ? pantryItems.value.join(',')
          : undefined,
      }
    )
    recipes.value = result.recipes
    total.value = result.total
  } finally {
    loadingRecipes.value = false
  }
}

function toggleSave(recipe: BrowserRecipe) {
  if (savedStore.isSaved(recipe.id)) {
    savingRecipe.value = recipe  // open edit modal
  } else {
    savingRecipe.value = recipe  // open save modal
  }
}

async function doUnsave(recipeId: number) {
  savingRecipe.value = null
  await savedStore.unsave(recipeId)
}
</script>

<style scoped>
.browser-panel {
  padding: var(--spacing-sm) 0;
}

.cat-btn {
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
}

.cat-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.cat-count {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  padding: 0 5px;
  font-size: var(--font-size-xs, 0.72rem);
  color: var(--color-text-secondary);
  margin-left: var(--spacing-xs);
}

.cat-btn.active .cat-count {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.surprise-btn {
  opacity: 0.75;
  font-style: italic;
}

.surprise-btn:hover {
  opacity: 1;
}

.recipe-grid {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.recipe-row {
  align-items: center;
}

.recipe-title-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-primary);
  padding: 0;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recipe-title-btn:hover {
  text-decoration: underline;
}

.match-badge {
  font-size: var(--font-size-xs, 0.72rem);
  white-space: nowrap;
}

.status-secondary {
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.btn-saved {
  color: var(--color-warning);
  border-color: var(--color-warning);
}

.btn-xs {
  padding: 2px var(--spacing-xs);
  font-size: var(--font-size-xs, 0.75rem);
}

.page-indicator {
  align-self: center;
}

.flex-shrink-0 {
  flex-shrink: 0;
}
</style>
