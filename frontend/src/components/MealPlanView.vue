<!-- frontend/src/components/MealPlanView.vue -->
<template>
  <div class="meal-plan-view">
    <!-- Week picker + new plan button -->
    <div class="plan-controls">
      <select
        class="week-select"
        :value="activePlan?.id ?? ''"
        aria-label="Select week"
        @change="onSelectPlan(Number(($event.target as HTMLSelectElement).value))"
      >
        <option value="" disabled>Select a week...</option>
        <option v-for="p in plans" :key="p.id" :value="p.id">
          Week of {{ p.week_start }}
        </option>
      </select>
      <button class="new-plan-btn" @click="onNewPlan" :disabled="planCreating">
        {{ planCreating ? 'Creating…' : '+ New week' }}
      </button>
    </div>
    <p v-if="planError" class="plan-error">{{ planError }}</p>

    <template v-if="activePlan">
      <!-- Compact expandable week grid (always visible) -->
      <MealPlanGrid
        :active-meal-types="activePlan.meal_types"
        :can-add-meal-type="canAddMealType"
        :meal-type-changing="mealTypeAdding"
        @slot-click="onSlotClick"
        @add-meal-type="onAddMealType"
        @remove-meal-type="onRemoveMealType"
        @reorder-meal-types="onReorderMealTypes"
      />

      <!-- Slot editor panel -->
      <div v-if="slotEditing" class="slot-editor card">
        <div class="slot-editor-header">
          <span class="slot-editor-title">
            {{ DAY_LABELS[slotEditing.dayOfWeek] }} · {{ slotEditing.mealType }}
          </span>
          <button class="close-btn" @click="slotEditing = null" aria-label="Close">✕</button>
        </div>

        <!-- Custom label -->
        <div class="form-group">
          <label class="form-label">Custom label</label>
          <input
            v-model="slotCustomLabel"
            class="form-input"
            type="text"
            placeholder="e.g. Taco night, Leftovers…"
            maxlength="80"
          />
        </div>

        <!-- Pick from saved recipes -->
        <div v-if="savedStore.saved.length" class="form-group">
          <label class="form-label">Or pick a saved recipe</label>
          <select class="week-select" v-model="slotRecipeId">
            <option :value="null">— None —</option>
            <option v-for="r in savedStore.saved" :key="r.recipe_id" :value="r.recipe_id">
              {{ r.title }}
            </option>
          </select>
        </div>
        <p v-else class="slot-hint">Save recipes from the Recipes tab to pick them here.</p>

        <div class="slot-editor-actions">
          <button class="btn-secondary" @click="slotEditing = null">Cancel</button>
          <button
            v-if="currentSlot"
            class="btn-danger-subtle"
            @click="onClearSlot"
            :disabled="slotSaving"
          >Clear slot</button>
          <button
            class="btn-primary"
            @click="onSaveSlot"
            :disabled="slotSaving"
          >{{ slotSaving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>

      <!-- Meal type picker -->
      <div v-if="addingMealType" class="meal-type-picker card">
        <span class="slot-editor-title">Add meal type</span>
        <div class="chip-row">
          <button
            v-for="t in availableMealTypes"
            :key="t"
            class="btn-chip"
            :disabled="mealTypeAdding"
            @click="onPickMealType(t)"
          >{{ t }}</button>
        </div>
        <button class="close-link" @click="addingMealType = false">Cancel</button>
      </div>

      <!-- Panel tabs: Shopping List | Prep Schedule -->
      <div class="panel-tabs" role="tablist" aria-label="Plan outputs">
        <button
          v-for="tab in TABS"
          :key="tab.id"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :aria-controls="`tabpanel-${tab.id}`"
          :id="`tab-${tab.id}`"
          class="panel-tab"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </div>

      <div
        v-show="activeTab === 'shopping'"
        id="tabpanel-shopping"
        role="tabpanel"
        aria-labelledby="tab-shopping"
        class="tab-panel"
      >
        <ShoppingListPanel @load="store.loadShoppingList()" />
      </div>

      <div
        v-show="activeTab === 'prep'"
        id="tabpanel-prep"
        role="tabpanel"
        aria-labelledby="tab-prep"
        class="tab-panel"
      >
        <PrepSessionView @load="store.loadPrepSession()" />
      </div>
    </template>

    <div v-else-if="!loading" class="empty-plan-state">
      <p>No meal plan yet for this week.</p>
      <button class="new-plan-btn" @click="onNewPlan" :disabled="planCreating">
        {{ planCreating ? 'Creating…' : 'Start planning' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMealPlanStore } from '../stores/mealPlan'
import { useSavedRecipesStore } from '../stores/savedRecipes'
import MealPlanGrid from './MealPlanGrid.vue'
import ShoppingListPanel from './ShoppingListPanel.vue'
import PrepSessionView from './PrepSessionView.vue'
import type { MealPlanSlot } from '../services/api'

const TABS = [
  { id: 'shopping', label: 'Shopping List' },
  { id: 'prep',     label: 'Prep Schedule' },
] as const

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const ALL_MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack']

type TabId = typeof TABS[number]['id']

const store = useMealPlanStore()
const savedStore = useSavedRecipesStore()
const { plans, activePlan, loading } = storeToRefs(store)

const activeTab = ref<TabId>('shopping')
const planError = ref<string | null>(null)
const planCreating = ref(false)

// ── slot editor ───────────────────────────────────────────────────────────────
const slotEditing = ref<{ dayOfWeek: number; mealType: string } | null>(null)
const slotCustomLabel = ref('')
const slotRecipeId = ref<number | null>(null)
const slotSaving = ref(false)

const currentSlot = computed((): MealPlanSlot | undefined => {
  if (!slotEditing.value) return undefined
  return store.getSlot(slotEditing.value.dayOfWeek, slotEditing.value.mealType)
})

// ── meal type picker ──────────────────────────────────────────────────────────
const addingMealType = ref(false)
const mealTypeAdding = ref(false)

const availableMealTypes = computed(() =>
  ALL_MEAL_TYPES.filter(t => !activePlan.value?.meal_types.includes(t))
)

// canAddMealType is a UI hint — backend enforces the paid gate authoritatively
const canAddMealType = computed(() =>
  (activePlan.value?.meal_types.length ?? 0) < 4
)

onMounted(async () => {
  await Promise.all([store.loadPlans(), savedStore.load()])
  store.autoSelectPlan(mondayOfCurrentWeek())
})

function mondayOfCurrentWeek(): string {
  const today = new Date()
  const day = today.getDay() // 0=Sun, 1=Mon...
  // Build date string from local parts to avoid UTC-offset day drift
  const d = new Date(today)
  d.setDate(today.getDate() - ((day + 6) % 7))
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function onNewPlan() {
  planError.value = null
  planCreating.value = true
  const weekStart = mondayOfCurrentWeek()
  try {
    await store.createPlan(weekStart, ['dinner'])
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    if (msg.includes('409') || msg.toLowerCase().includes('already exists')) {
      const existing = plans.value.find(p => p.week_start === weekStart)
      if (existing) await store.setActivePlan(existing.id)
    } else {
      planError.value = `Couldn't create plan: ${msg}`
    }
  } finally {
    planCreating.value = false
  }
}

async function onSelectPlan(planId: number) {
  if (planId) await store.setActivePlan(planId)
}

function onSlotClick(payload: { dayOfWeek: number; mealType: string }) {
  slotEditing.value = payload
  const existing = store.getSlot(payload.dayOfWeek, payload.mealType)
  slotCustomLabel.value = existing?.custom_label ?? ''
  slotRecipeId.value = existing?.recipe_id ?? null
}

async function onSaveSlot() {
  if (!slotEditing.value) return
  slotSaving.value = true
  try {
    await store.upsertSlot(slotEditing.value.dayOfWeek, slotEditing.value.mealType, {
      recipe_id: slotRecipeId.value,
      custom_label: slotCustomLabel.value.trim() || null,
    })
    slotEditing.value = null
  } finally {
    slotSaving.value = false
  }
}

async function onClearSlot() {
  if (!slotEditing.value) return
  slotSaving.value = true
  try {
    await store.clearSlot(slotEditing.value.dayOfWeek, slotEditing.value.mealType)
    slotEditing.value = null
  } finally {
    slotSaving.value = false
  }
}

function onAddMealType() {
  addingMealType.value = true
}

async function onPickMealType(mealType: string) {
  mealTypeAdding.value = true
  try {
    await store.addMealType(mealType)
    addingMealType.value = false
  } finally {
    mealTypeAdding.value = false
  }
}

async function onRemoveMealType(mealType: string) {
  mealTypeAdding.value = true
  try {
    await store.removeMealType(mealType)
  } finally {
    mealTypeAdding.value = false
  }
}

async function onReorderMealTypes(newOrder: string[]) {
  mealTypeAdding.value = true
  try {
    await store.reorderMealTypes(newOrder)
  } finally {
    mealTypeAdding.value = false
  }
}
</script>

<style scoped>
.meal-plan-view { display: flex; flex-direction: column; gap: 1rem; }

.plan-controls { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.week-select {
  flex: 1; padding: 0.4rem 0.6rem; border-radius: 6px;
  border: 1px solid var(--color-border); background: var(--color-surface);
  color: var(--color-text); font-size: 0.85rem;
}
.new-plan-btn {
  padding: 0.4rem 1rem; border-radius: 20px; font-size: 0.82rem;
  background: var(--color-accent-subtle); color: var(--color-accent);
  border: 1px solid var(--color-accent); cursor: pointer; white-space: nowrap;
}
.new-plan-btn:hover { background: var(--color-accent); color: white; }

/* Slot editor */
.slot-editor, .meal-type-picker {
  padding: 1rem; border-radius: 8px;
  border: 1px solid var(--color-border); background: var(--color-surface);
  display: flex; flex-direction: column; gap: 0.75rem;
}
.slot-editor-header { display: flex; align-items: center; justify-content: space-between; }
.slot-editor-title { font-size: 0.85rem; font-weight: 600; }
.close-btn {
  background: none; border: none; cursor: pointer; font-size: 0.9rem;
  color: var(--color-text-secondary); padding: 0.1rem 0.3rem; border-radius: 4px;
}
.close-btn:hover { background: var(--color-surface-2); }
.slot-hint { font-size: 0.8rem; opacity: 0.55; margin: 0; }
.slot-editor-actions { display: flex; gap: 0.5rem; justify-content: flex-end; flex-wrap: wrap; }

.chip-row { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.close-link {
  background: none; border: none; cursor: pointer; font-size: 0.8rem;
  color: var(--color-text-secondary); align-self: flex-start; padding: 0;
}
.close-link:hover { text-decoration: underline; }

.panel-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--color-border); padding-bottom: 0; }
.panel-tab {
  font-size: 0.82rem; padding: 0.4rem 1rem; border-radius: 6px 6px 0 0;
  background: none; border: 1px solid transparent; border-bottom: none; cursor: pointer;
  color: var(--color-text-secondary); transition: color 0.15s, background 0.15s;
}
.panel-tab.active {
  color: var(--color-accent); background: var(--color-accent-subtle);
  border-color: var(--color-border); border-bottom-color: transparent;
}
.panel-tab:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.tab-panel { padding-top: 0.75rem; }

.empty-plan-state { text-align: center; padding: 2rem 0; opacity: 0.6; font-size: 0.9rem; }

.plan-error {
  font-size: 0.82rem; color: var(--color-error, #e05252);
  background: var(--color-error-subtle, #fef2f2);
  border: 1px solid var(--color-error, #e05252); border-radius: 6px;
  padding: 0.4rem 0.75rem; margin: 0;
}
</style>
