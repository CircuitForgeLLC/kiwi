<!-- frontend/src/components/MealPlanGrid.vue -->
<template>
  <div class="meal-plan-grid">
    <!-- Collapsible header (mobile) -->
    <div class="grid-toggle-row">
      <span class="grid-label">This week</span>
      <button
        class="grid-toggle-btn"
        :aria-expanded="!collapsed"
        :aria-label="collapsed ? 'Show plan' : 'Hide plan'"
        @click="collapsed = !collapsed"
      >{{ collapsed ? 'Show plan' : 'Hide plan' }}</button>
    </div>

    <div v-show="!collapsed" class="grid-body">
      <!-- Day headers -->
      <div class="day-headers">
        <div class="meal-type-col-spacer" />
        <div
          v-for="(day, i) in DAY_LABELS"
          :key="i"
          class="day-header"
          :aria-label="day"
        >{{ day }}</div>
      </div>

      <!-- One row per meal type -->
      <div
        v-for="mealType in activeMealTypes"
        :key="mealType"
        class="meal-row"
      >
        <div class="meal-type-label">{{ mealType }}</div>
        <button
          v-for="dayIndex in 7"
          :key="dayIndex - 1"
          class="slot-btn"
          :class="{ filled: !!getSlot(dayIndex - 1, mealType) }"
          :aria-label="`${DAY_LABELS[dayIndex - 1]} ${mealType}: ${getSlot(dayIndex - 1, mealType)?.recipe_title ?? 'empty'}`"
          @click="$emit('slot-click', { dayOfWeek: dayIndex - 1, mealType })"
        >
          <span v-if="getSlot(dayIndex - 1, mealType)" class="slot-title">
            {{ getSlot(dayIndex - 1, mealType)!.recipe_title ?? getSlot(dayIndex - 1, mealType)!.custom_label ?? '...' }}
          </span>
          <span v-else class="slot-empty" aria-hidden="true">+</span>
        </button>
      </div>

      <!-- Add meal type row (Paid only) -->
      <div v-if="canAddMealType" class="add-meal-type-row">
        <button class="add-meal-type-btn" @click="$emit('add-meal-type')">
          + Add meal type
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMealPlanStore } from '../stores/mealPlan'

defineProps<{
  activeMealTypes: string[]
  canAddMealType: boolean
}>()

defineEmits<{
  (e: 'slot-click', payload: { dayOfWeek: number; mealType: string }): void
  (e: 'add-meal-type'): void
}>()

const store = useMealPlanStore()
const { getSlot } = store

const collapsed = ref(false)

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
</script>

<style scoped>
.meal-plan-grid { display: flex; flex-direction: column; gap: 0.5rem; }

.grid-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.25rem 0;
}
.grid-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.07em; opacity: 0.6; }
.grid-toggle-btn {
  font-size: 0.75rem; background: none; border: none; cursor: pointer;
  color: var(--color-accent); padding: 0.2rem 0.5rem;
}

.grid-body { display: flex; flex-direction: column; gap: 3px; }
.day-headers { display: grid; grid-template-columns: 3rem repeat(7, 1fr); gap: 3px; }
.meal-type-col-spacer { }
.day-header { text-align: center; font-size: 0.7rem; font-weight: 700; padding: 3px; background: var(--color-surface-2); border-radius: 4px; }

.meal-row { display: grid; grid-template-columns: 3rem repeat(7, 1fr); gap: 3px; align-items: start; }
.meal-type-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.55; display: flex; align-items: center; font-weight: 600; }

.slot-btn {
  border: 1px dashed var(--color-border);
  border-radius: 6px;
  min-height: 44px;
  background: var(--color-surface);
  cursor: pointer;
  padding: 4px;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.65rem;
  transition: border-color 0.15s, background 0.15s;
  width: 100%;
}
.slot-btn:hover { border-color: var(--color-accent); }
.slot-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.slot-btn.filled { border-color: var(--color-success); background: var(--color-success-subtle); }
.slot-title { text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; color: var(--color-text); }
.slot-empty { opacity: 0.25; font-size: 1rem; }

.add-meal-type-row { padding: 0.4rem 0 0.2rem; }
.add-meal-type-btn { font-size: 0.75rem; background: none; border: none; cursor: pointer; color: var(--color-accent); padding: 0; }

@media (max-width: 600px) {
  .day-headers, .meal-row { grid-template-columns: 2.5rem repeat(7, 1fr); }
}
</style>
