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
      <button class="new-plan-btn" @click="onNewPlan">+ New week</button>
    </div>

    <template v-if="activePlan">
      <!-- Compact expandable week grid (always visible) -->
      <MealPlanGrid
        :active-meal-types="activePlan.meal_types"
        :can-add-meal-type="canAddMealType"
        @slot-click="onSlotClick"
        @add-meal-type="onAddMealType"
      />

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
      <button class="new-plan-btn" @click="onNewPlan">Start planning</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMealPlanStore } from '../stores/mealPlan'
import MealPlanGrid from './MealPlanGrid.vue'
import ShoppingListPanel from './ShoppingListPanel.vue'
import PrepSessionView from './PrepSessionView.vue'

const TABS = [
  { id: 'shopping', label: 'Shopping List' },
  { id: 'prep',     label: 'Prep Schedule' },
] as const

type TabId = typeof TABS[number]['id']

const store = useMealPlanStore()
const { plans, activePlan, loading } = storeToRefs(store)

const activeTab = ref<TabId>('shopping')

// canAddMealType is a UI hint — backend enforces the paid gate authoritatively
const canAddMealType = computed(() =>
  (activePlan.value?.meal_types.length ?? 0) < 4
)

onMounted(() => store.loadPlans())

async function onNewPlan() {
  const today = new Date()
  const day = today.getDay()
  // Compute Monday of current week (getDay: 0=Sun, 1=Mon...)
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((day + 6) % 7))
  const weekStart = monday.toISOString().split('T')[0]
  await store.createPlan(weekStart, ['dinner'])
}

async function onSelectPlan(planId: number) {
  if (planId) await store.setActivePlan(planId)
}

function onSlotClick({ dayOfWeek, mealType }: { dayOfWeek: number; mealType: string }) {
  // Recipe picker integration filed as follow-up
  console.log('[MealPlan] slot-click', { dayOfWeek, mealType })
}

function onAddMealType() {
  // Add meal type picker — Paid gate enforced by backend
  console.log('[MealPlan] add-meal-type')
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
</style>
