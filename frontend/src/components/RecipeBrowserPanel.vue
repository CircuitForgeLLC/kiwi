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
      <!-- Corpus unavailable notice — shown when all category counts are 0 -->
      <div v-if="allCountsZero" class="browser-unavailable card p-md text-secondary text-sm">
        Recipe library is not available on this instance yet. Browse categories will appear once the recipe corpus is loaded.
      </div>

      <!-- Category list + Surprise Me -->
      <div v-else class="category-list mb-sm flex flex-wrap gap-xs">
        <button
          :class="['btn', 'btn-secondary', 'cat-btn', { active: activeCategory === '_all' }]"
          @click="selectCategory('_all')"
        >
          All
        </button>
        <button
          v-for="cat in categories"
          :key="cat.category"
          :class="['btn', 'btn-secondary', 'cat-btn', { active: activeCategory === cat.category }]"
          @click="selectCategory(cat.category)"
        >
          {{ cat.category }}
          <span class="cat-count">{{ cat.recipe_count }}</span>
          <span v-if="cat.has_subcategories" class="cat-drill-indicator" title="Has subcategories">›</span>
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

      <!-- Subcategory row — shown when the active category has subcategories -->
      <div
        v-if="activeCategoryHasSubs && (subcategories.length > 0 || loadingSubcategories)"
        class="subcategory-list mb-md flex flex-wrap gap-xs"
      >
        <span v-if="loadingSubcategories" class="text-secondary text-xs">Loading…</span>
        <template v-else>
          <button
            :class="['btn', 'btn-secondary', 'subcat-btn', { active: activeSubcategory === null }]"
            @click="selectSubcategory(null)"
          >
            All {{ activeCategory }}
          </button>
          <button
            v-for="sub in subcategories"
            :key="sub.subcategory"
            :class="['btn', 'btn-secondary', 'subcat-btn', { active: activeSubcategory === sub.subcategory }]"
            @click="selectSubcategory(sub.subcategory)"
          >
            {{ sub.subcategory }}
            <span class="cat-count">{{ sub.recipe_count }}</span>
            <span
              v-if="sub.recipe_count === 0"
              class="tag-cta"
              title="Know a recipe in this category? Tag it!"
              @click.stop="openTagModal(sub.subcategory)"
            >＋</span>
          </button>
        </template>
      </div>

      <!-- Recipe grid -->
      <template v-if="activeCategory">
        <div v-if="loadingRecipes" class="text-secondary text-sm">Loading recipes…</div>

        <template v-else>
          <!-- Search + sort controls -->
          <div class="browser-controls flex gap-sm mb-sm flex-wrap align-center">
            <input
              v-model="searchQuery"
              @input="onSearchInput"
              type="search"
              placeholder="Filter by title…"
              class="browser-search"
            />
            <input
              v-model="requiredIngredient"
              @keyup.enter="onRequiredIngredientCommit"
              @search="onRequiredIngredientCommit"
              type="search"
              placeholder="Must include ingredient… (Enter)"
              class="browser-search"
              title="Type an ingredient and press Enter to filter"
            />
            <div class="sort-btns flex gap-xs">
              <button
                :class="['btn', 'btn-secondary', 'sort-btn', { active: sortOrder === 'default' }]"
                @click="setSort('default')"
                title="Corpus order"
              >Default</button>
              <button
                :class="['btn', 'btn-secondary', 'sort-btn', { active: sortOrder === 'alpha' }]"
                @click="setSort('alpha')"
                title="Alphabetical A→Z"
              >A→Z</button>
              <button
                :class="['btn', 'btn-secondary', 'sort-btn', { active: sortOrder === 'alpha_desc' }]"
                @click="setSort('alpha_desc')"
                title="Alphabetical Z→A"
              >Z→A</button>
              <button
                :class="['btn', 'btn-secondary', 'sort-btn', { active: sortOrder === 'match' }]"
                :disabled="pantryCount === 0"
                @click="setSort('match')"
                :title="pantryCount > 0 ? 'Sort by pantry match %' : 'Add items to pantry to sort by match'"
              >Best match</button>
            </div>
          </div>

          <div class="results-header flex-between mb-sm">
            <span class="text-sm text-secondary">
              {{ total }} recipes
              <span v-if="pantryCount > 0"> — pantry match shown</span>
              <span v-if="requiredIngredient.trim()"> — must include "{{ requiredIngredient.trim() }}"</span>
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

                <!-- Time & effort split pill -->
                <span
                  v-if="recipe.active_min !== null"
                  class="time-split-pill"
                  :title="`~${formatMin(recipe.active_min)} active · ~${formatMin(recipe.passive_min ?? 0)} passive`"
                >
                  <span class="pill-active">🧑‍🍳 ~{{ formatMin(recipe.active_min) }}</span>
                  <span
                    v-if="recipe.passive_min !== null && recipe.passive_min > 0"
                    class="pill-passive"
                  >💤 ~{{ formatMin(recipe.passive_min) }}</span>
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

      <div v-else-if="!allCountsZero" class="text-secondary text-sm">Loading recipes…</div>
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

    <!-- Community tag modal — opened from zero-count subcategory CTA -->
    <div v-if="tagModal.open" class="modal-backdrop" @click.self="tagModal.open = false">
      <div class="modal-box" role="dialog" aria-modal="true" aria-label="Tag a recipe">
        <h3 class="text-md font-semibold mb-sm">Tag a recipe as {{ tagModal.subcategory }}</h3>
        <p class="text-sm text-secondary mb-sm">
          Search for a recipe you know belongs here. Your tag helps other users discover it.
        </p>

        <!-- Recipe search -->
        <input
          class="form-input mb-xs"
          v-model="tagModal.searchQuery"
          placeholder="Search recipe title…"
          @input="onTagSearchInput"
          autocomplete="off"
        />
        <div v-if="tagModal.searching" class="text-sm text-secondary mb-xs">Searching…</div>
        <ul v-else-if="tagModal.results.length > 0" class="tag-search-results mb-sm">
          <li
            v-for="r in tagModal.results"
            :key="r.id"
            :class="['tag-result-row', { selected: tagModal.selectedRecipe?.id === r.id }]"
            @click="tagModal.selectedRecipe = r"
          >
            <span class="tag-result-title">{{ r.title }}</span>
            <span class="tag-result-check" v-if="tagModal.selectedRecipe?.id === r.id">✓</span>
          </li>
        </ul>
        <p v-else-if="tagModal.searchQuery.length > 2" class="text-sm text-secondary mb-sm">
          No results — try a different title.
        </p>

        <!-- Location correction (pre-filled from active browse context) -->
        <div class="form-group mb-xs">
          <label class="form-label text-xs">Domain</label>
          <select class="form-input" v-model="tagModal.domain">
            <option v-for="d in domains" :key="d.id" :value="d.id">{{ d.label }}</option>
          </select>
        </div>
        <div class="form-group mb-xs">
          <label class="form-label text-xs">Category</label>
          <select class="form-input" v-model="tagModal.category">
            <option v-for="c in categories" :key="c.category" :value="c.category">
              {{ c.category }}
            </option>
          </select>
        </div>
        <div class="form-group mb-sm">
          <label class="form-label text-xs">Subcategory (optional)</label>
          <select class="form-input" v-model="tagModal.subcategoryEdit">
            <option value="">— none (category level) —</option>
            <option v-for="s in subcategories" :key="s.subcategory" :value="s.subcategory">
              {{ s.subcategory }}
            </option>
          </select>
        </div>

        <div class="flex gap-sm">
          <button
            class="btn btn-primary btn-sm"
            :disabled="!tagModal.selectedRecipe || tagModal.submitting"
            @click="submitTag"
          >
            <span v-if="tagModal.submitting">Submitting…</span>
            <span v-else>Tag this recipe</span>
          </button>
          <button class="btn btn-secondary btn-sm" @click="tagModal.open = false">Cancel</button>
        </div>
        <p v-if="tagModal.error" class="text-sm status-badge status-error mt-xs">{{ tagModal.error }}</p>
        <p v-if="tagModal.success" class="text-sm status-badge status-ok mt-xs">{{ tagModal.success }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { browserAPI, type BrowserDomain, type BrowserCategory, type BrowserSubcategory, type BrowserRecipe } from '../services/api'
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
const subcategories = ref<BrowserSubcategory[]>([])
const activeSubcategory = ref<string | null>(null)
const loadingSubcategories = ref(false)
const recipes = ref<BrowserRecipe[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loadingDomains = ref(false)
const loadingRecipes = ref(false)
const savingRecipe = ref<BrowserRecipe | null>(null)
const searchQuery = ref('')
const requiredIngredient = ref('')
const sortOrder = ref<'default' | 'alpha' | 'alpha_desc' | 'match'>('default')
let searchDebounce: ReturnType<typeof setTimeout> | null = null
let tagSearchDebounce: ReturnType<typeof setTimeout> | null = null

// ── Tag modal state ────────────────────────────────────────────────────────
const tagModal = ref({
  open: false,
  subcategory: '',       // display label (pre-filled from CTA)
  domain: '',            // editable, pre-filled
  category: '',          // editable, pre-filled
  subcategoryEdit: '',   // editable, pre-filled
  searchQuery: '',
  searching: false,
  results: [] as Array<{ id: number; title: string }>,
  selectedRecipe: null as { id: number; title: string } | null,
  submitting: false,
  error: '',
  success: '',
})


const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const allCountsZero = computed(() =>
  categories.value.length > 0 && categories.value.every(c => c.recipe_count === 0)
)
const activeCategoryHasSubs = computed(() => {
  if (!activeCategory.value || activeCategory.value === '_all') return false
  return categories.value.find(c => c.category === activeCategory.value)?.has_subcategories ?? false
})

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

/**
 * Format minutes as a compact display string.
 * < 60 → "15m"
 * >= 60 → "1h 30m" (omits minutes when zero: "2h")
 */
function formatMin(minutes: number): string {
  if (minutes < 60) return `${minutes}m`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
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

function onSearchInput() {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    page.value = 1
    loadRecipes()
  }, 350)
}

function onRequiredIngredientCommit() {
  page.value = 1
  loadRecipes()
}

// Auto-clear results when the field is emptied via backspace/select-delete
watch(requiredIngredient, (val, prev) => {
  if (val === '' && prev !== '') {
    page.value = 1
    loadRecipes()
  }
})

function setSort(s: 'default' | 'alpha' | 'alpha_desc' | 'match') {
  if (sortOrder.value === s) return
  sortOrder.value = s
  page.value = 1
  loadRecipes()
}

// When pantry items first become available while browsing, auto-engage match sort.
// When pantry empties out mid-session, drop back to default so the button disables cleanly.
watch(pantryCount, (newCount, oldCount) => {
  if (newCount > 0 && oldCount === 0 && activeCategory.value) {
    setSort('match')
  } else if (newCount === 0 && sortOrder.value === 'match') {
    setSort('default')
  }
})

async function selectDomain(domainId: string) {
  activeDomain.value = domainId
  activeCategory.value = null
  recipes.value = []
  total.value = 0
  page.value = 1
  searchQuery.value = ''
  requiredIngredient.value = ''
  sortOrder.value = 'default'
  categories.value = await browserAPI.listCategories(domainId)
  // Auto-select the most-populated category so content appears immediately.
  // Skip when all counts are 0 (corpus not seeded) — no point loading an empty result.
  const hasRecipes = categories.value.some(c => c.recipe_count > 0)
  if (hasRecipes) {
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
  activeSubcategory.value = null
  subcategories.value = []
  page.value = 1
  searchQuery.value = ''
  sortOrder.value = 'default'

  // Fetch subcategories in the background when the category supports them,
  // then immediately start loading recipes at the full-category level.
  const catMeta = categories.value.find(c => c.category === category)
  if (catMeta?.has_subcategories) {
    loadingSubcategories.value = true
    browserAPI.listSubcategories(activeDomain.value!, category)
      .then(subs => { subcategories.value = subs })
      .finally(() => { loadingSubcategories.value = false })
  }

  await loadRecipes()
}

async function selectSubcategory(subcat: string | null) {
  activeSubcategory.value = subcat
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
        subcategory: activeSubcategory.value ?? undefined,
        q: searchQuery.value.trim() || undefined,
        sort: sortOrder.value !== 'default' ? sortOrder.value : undefined,
        required_ingredient: requiredIngredient.value.trim() || undefined,
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

// ── Tag modal ──────────────────────────────────────────────────────────────

function openTagModal(subcategoryName: string) {
  Object.assign(tagModal.value, {
    open: true,
    subcategory: subcategoryName,
    domain: activeDomain.value ?? '',
    category: activeCategory.value ?? '',
    subcategoryEdit: subcategoryName,
    searchQuery: '',
    searching: false,
    results: [],
    selectedRecipe: null,
    submitting: false,
    error: '',
    success: '',
  })
}

function onTagSearchInput() {
  if (tagSearchDebounce) clearTimeout(tagSearchDebounce)
  const q = tagModal.value.searchQuery.trim()
  if (q.length < 3) {
    tagModal.value.results = []
    return
  }
  tagSearchDebounce = setTimeout(async () => {
    tagModal.value.searching = true
    try {
      // Use the first available domain with category=_all to search all recipes by title.
      // Domain must be a real domain slug — '_all' is not valid at the browse endpoint.
      const searchDomain = domains.value[0]?.id ?? 'cuisine'
      const res = await browserAPI.browse(searchDomain, '_all', { page: 1, q })
      tagModal.value.results = (res.recipes ?? []).slice(0, 8).map(
        (r: { id: number; title: string }) => ({ id: r.id, title: r.title })
      )
    } catch {
      tagModal.value.results = []
    } finally {
      tagModal.value.searching = false
    }
  }, 350)
}

async function submitTag() {
  const m = tagModal.value
  if (!m.selectedRecipe) return
  m.submitting = true
  m.error = ''
  m.success = ''
  try {
    await browserAPI.submitRecipeTag({
      recipe_id: m.selectedRecipe.id,
      domain: m.domain,
      category: m.category,
      subcategory: m.subcategoryEdit || null,
      pseudonym: 'anon',  // TODO: wire real pseudonym from community store
    })
    m.success = `Tagged! It will appear here once a second user confirms.`
    setTimeout(() => { m.open = false }, 2500)
  } catch (err: any) {
    m.error = err?.message === '409'
      ? 'You have already tagged this recipe here.'
      : 'Failed to submit — please try again.'
  } finally {
    m.submitting = false
  }
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

.cat-drill-indicator {
  margin-left: var(--spacing-xs);
  opacity: 0.5;
  font-size: var(--font-size-sm);
}

.subcategory-list {
  padding-left: var(--spacing-sm);
  border-left: 2px solid var(--color-border);
  margin-left: var(--spacing-xs);
}

.subcat-btn {
  font-size: var(--font-size-xs, 0.78rem);
  padding: var(--spacing-xs) var(--spacing-sm);
  opacity: 0.9;
}

.subcat-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  opacity: 1;
}

.subcat-btn.active .cat-count {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.browser-controls {
  align-items: center;
}

.browser-search {
  flex: 1;
  min-width: 120px;
  max-width: 260px;
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
}

.browser-search:focus {
  outline: none;
  border-color: var(--color-primary);
}

.sort-btn {
  font-size: var(--font-size-xs, 0.75rem);
  padding: 2px var(--spacing-sm);
}

.sort-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
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

/* ── Time & effort split pill ──────────────────────────────────────────── */
.time-split-pill {
  display: inline-flex;
  align-items: stretch;
  border-radius: var(--radius-pill, 999px);
  overflow: hidden;
  font-size: var(--font-size-xs, 0.72rem);
  white-space: nowrap;
  flex-shrink: 0;
  border: 1px solid transparent;
}

.pill-active {
  padding: 2px 6px;
  background: rgba(232, 168, 32, 0.18);
  color: #f0bc48;
  border-radius: var(--radius-pill, 999px) 0 0 var(--radius-pill, 999px);
}

/* When there is no passive segment, active gets full pill rounding */
.time-split-pill:not(:has(.pill-passive)) .pill-active {
  border-radius: var(--radius-pill, 999px);
}

.pill-passive {
  padding: 2px 6px;
  background: rgba(41, 128, 185, 0.15);
  color: #5dade2;
  border-radius: 0 var(--radius-pill, 999px) var(--radius-pill, 999px) 0;
}

/* ── Community tag CTA ──────────────────────────────────────────────────── */
.tag-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.25rem;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  font-size: 0.75rem;
  background: var(--color-accent, #7c6fcd);
  color: #fff;
  opacity: 0.75;
  cursor: pointer;
  transition: opacity 0.15s;
}
.tag-cta:hover {
  opacity: 1;
}

/* ── Tag modal ──────────────────────────────────────────────────────────── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal-box {
  background: var(--color-surface, #fff);
  border-radius: var(--radius-md, 0.5rem);
  padding: 1.5rem;
  max-width: 28rem;
  width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.tag-search-results {
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: var(--radius-sm, 0.25rem);
  max-height: 12rem;
  overflow-y: auto;
}
.tag-result-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  transition: background 0.1s;
}
.tag-result-row:hover,
.tag-result-row.selected {
  background: var(--color-hover, #f0eeff);
}
.tag-result-title {
  font-size: 0.875rem;
  flex: 1;
}
.tag-result-check {
  color: var(--color-accent, #7c6fcd);
  font-size: 0.875rem;
  margin-left: 0.5rem;
}
</style>
