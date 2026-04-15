<template>
  <div class="saved-panel">
    <!-- Empty state -->
    <div v-if="!store.loading && store.saved.length === 0" class="empty-state card text-center">
      <p class="text-secondary">No saved recipes yet.</p>
      <div class="flex gap-sm mt-sm" style="justify-content: center;">
        <button class="btn btn-secondary btn-sm" @click="$emit('go-to-tab', 'find')">
          Find recipes for my pantry
        </button>
        <button class="btn btn-secondary btn-sm" @click="$emit('go-to-tab', 'browse')">
          Browse recipes
        </button>
      </div>
    </div>

    <template v-else>
      <!-- Controls -->
      <div class="saved-controls flex-between flex-wrap gap-sm mb-md">
        <div class="flex gap-sm flex-wrap">
          <!-- Collection filter -->
          <label class="sr-only" for="collection-filter">Filter by collection</label>
          <select id="collection-filter" class="form-input sort-select" v-model="activeCollectionId" @change="reload">
            <option :value="null">All saved</option>
            <option v-for="col in store.collections" :key="col.id" :value="col.id">
              {{ col.name }} ({{ col.member_count }})
            </option>
          </select>

          <!-- Sort -->
          <label class="sr-only" for="sort-order">Sort by</label>
          <select id="sort-order" class="form-input sort-select" v-model="store.sortBy" @change="reload">
            <option value="saved_at">Recently saved</option>
            <option value="rating">Highest rated</option>
            <option value="title">A–Z</option>
          </select>
        </div>

        <button class="btn btn-secondary btn-sm" @click="showNewCollection = true">
          + New collection
        </button>
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="text-secondary text-sm">Loading…</div>

      <!-- Recipe cards -->
      <div class="saved-list flex-col gap-sm">
        <div
          v-for="recipe in store.saved"
          :key="recipe.id"
          class="card-sm saved-card"
          :class="{ 'card-success': recipe.rating !== null && recipe.rating >= 4 }"
        >
          <div class="flex-between gap-sm">
            <button
              class="recipe-title-btn text-left"
              @click="$emit('open-recipe', recipe.recipe_id)"
            >
              {{ recipe.title }}
            </button>

            <!-- Stars display -->
            <div v-if="recipe.rating !== null" class="stars-display flex gap-xs" :aria-label="`Rating: ${recipe.rating} out of 5`">
              <span
                v-for="n in 5"
                :key="n"
                class="star-pip"
                :class="{ filled: n <= recipe.rating }"
              >★</span>
            </div>
          </div>

          <!-- Tags -->
          <div v-if="recipe.style_tags.length > 0" class="flex flex-wrap gap-xs mt-xs">
            <span
              v-for="tag in recipe.style_tags"
              :key="tag"
              class="tag-chip status-badge status-info"
            >{{ tag }}</span>
          </div>

          <!-- Notes preview with expand/collapse -->
          <div v-if="recipe.notes" class="mt-xs">
            <div
              class="notes-preview text-sm text-secondary"
              :class="{ expanded: expandedNotes.has(recipe.id) }"
            >{{ recipe.notes }}</div>
            <button
              v-if="recipe.notes.length > 120"
              class="btn-link text-sm"
              :aria-expanded="expandedNotes.has(recipe.id)"
              @click="toggleNotes(recipe.id)"
            >
              {{ expandedNotes.has(recipe.id) ? 'Show less' : 'Show more' }}
            </button>
          </div>

          <!-- Actions -->
          <div class="flex gap-xs mt-sm">
            <button class="btn btn-secondary btn-xs" @click="editRecipe(recipe)">Edit</button>
            <template v-if="confirmingRemove === recipe.id">
              <button class="btn btn-danger btn-xs" @click="confirmRemove(recipe.id)">Yes, remove</button>
              <button class="btn btn-secondary btn-xs" @click="cancelRemove">Cancel</button>
            </template>
            <button v-else class="btn btn-ghost btn-xs" @click="startRemove(recipe.id)">Remove</button>
          </div>
        </div>
      </div>
    </template>

    <!-- New collection modal -->
    <Teleport to="body" v-if="showNewCollection">
      <div class="modal-overlay" @click.self="showNewCollection = false">
        <div ref="newColDialogRef" class="modal-panel card" role="dialog" aria-modal="true" aria-label="New collection" tabindex="-1">
          <h3 class="section-title mb-md">New collection</h3>
          <div class="form-group">
            <label class="form-label" for="col-name">Name</label>
            <input id="col-name" class="form-input" v-model="newColName" placeholder="e.g. Weeknight meals" />
          </div>
          <div class="form-group">
            <label class="form-label" for="col-desc">Description (optional)</label>
            <input id="col-desc" class="form-input" v-model="newColDesc" placeholder="Optional description" />
          </div>
          <div class="flex gap-sm mt-md">
            <button class="btn btn-primary" :disabled="!newColName.trim() || creatingCol" @click="createCollection">
              {{ creatingCol ? 'Creating…' : 'Create' }}
            </button>
            <button class="btn btn-secondary" @click="showNewCollection = false">Cancel</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Edit modal -->
    <SaveRecipeModal
      v-if="editingRecipe"
      :recipe-id="editingRecipe.recipe_id"
      :recipe-title="editingRecipe.title"
      @close="editingRecipe = null"
      @saved="editingRecipe = null"
      @unsave="doUnsave(editingRecipe!.recipe_id)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useSavedRecipesStore } from '../stores/savedRecipes'
import type { SavedRecipe } from '../services/api'
import SaveRecipeModal from './SaveRecipeModal.vue'

const emit = defineEmits<{
  (e: 'open-recipe', recipeId: number): void
  (e: 'go-to-tab', tab: string): void
}>()

const store = useSavedRecipesStore()
const editingRecipe = ref<SavedRecipe | null>(null)
const showNewCollection = ref(false)

// #44: two-step remove confirmation
const confirmingRemove = ref<number | null>(null)

function startRemove(id: number) {
  confirmingRemove.value = id
}

function cancelRemove() {
  confirmingRemove.value = null
}

function confirmRemove(id: number) {
  const recipe = store.saved.find(r => r.id === id)
  if (recipe) void unsave(recipe)
  confirmingRemove.value = null
}

// #48: notes expand/collapse
const expandedNotes = ref<Set<number>>(new Set())

function toggleNotes(id: number) {
  const next = new Set(expandedNotes.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedNotes.value = next
}
const newColDialogRef = ref<HTMLElement | null>(null)
let newColPreviousFocus: HTMLElement | null = null

function handleNewColKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') showNewCollection.value = false
}

watch(showNewCollection, (open) => {
  if (open) {
    newColPreviousFocus = document.activeElement as HTMLElement
    document.addEventListener('keydown', handleNewColKeydown)
    nextTick(() => {
      const focusable = newColDialogRef.value?.querySelector<HTMLElement>(
        'button:not([disabled]), input'
      )
      ;(focusable ?? newColDialogRef.value)?.focus()
    })
  } else {
    document.removeEventListener('keydown', handleNewColKeydown)
    newColPreviousFocus?.focus()
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleNewColKeydown)
})
const newColName = ref('')
const newColDesc = ref('')
const creatingCol = ref(false)

const activeCollectionId = computed({
  get: () => store.activeCollectionId,
  set: (v) => { store.activeCollectionId = v },
})

onMounted(() => store.load())

function reload() {
  store.load()
}

function editRecipe(recipe: SavedRecipe) {
  editingRecipe.value = recipe
}

async function unsave(recipe: SavedRecipe) {
  await store.unsave(recipe.recipe_id)
}

async function doUnsave(recipeId: number) {
  editingRecipe.value = null
  await store.unsave(recipeId)
}

async function createCollection() {
  if (!newColName.value.trim()) return
  creatingCol.value = true
  try {
    await store.createCollection(newColName.value.trim(), newColDesc.value.trim() || undefined)
    showNewCollection.value = false
    newColName.value = ''
    newColDesc.value = ''
  } finally {
    creatingCol.value = false
  }
}
</script>

<style scoped>
.saved-panel {
  padding: var(--spacing-sm) 0;
}

.sort-select {
  width: auto;
  min-width: 140px;
}

.saved-card {
  transition: box-shadow 0.15s ease;
}

.recipe-title-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-primary);
  padding: 0;
  flex: 1;
}

.recipe-title-btn:hover {
  text-decoration: underline;
}

.stars-display {
  flex-shrink: 0;
}

.star-pip {
  font-size: 1rem;
  color: var(--color-border);
}

.star-pip.filled {
  color: var(--color-warning);
}

.notes-preview {
  overflow: hidden;
  max-height: 3.6em;
  transition: max-height 0.2s ease;
}

.notes-preview.expanded {
  max-height: none;
}

@media (prefers-reduced-motion: reduce) {
  .notes-preview { transition: none; }
}

.btn-link {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary);
  padding: 0;
  text-decoration: underline;
}

.btn-link:hover {
  text-decoration: none;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  font-size: var(--font-size-xs, 0.75rem);
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
}

.btn-xs {
  padding: 2px var(--spacing-xs);
  font-size: var(--font-size-xs, 0.75rem);
}

.empty-state {
  padding: var(--spacing-xl);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: var(--spacing-md);
}

.modal-panel {
  width: 100%;
  max-width: 420px;
}
</style>
