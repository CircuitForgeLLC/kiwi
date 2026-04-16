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
      <div class="day-headers" :class="{ 'headers-editing': editing }">
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
        v-for="(mealType, idx) in activeMealTypes"
        :key="mealType"
        class="meal-row"
        :class="{ 'row-editing': editing }"
      >
        <div class="meal-type-label" :class="{ 'label-editing': editing }">
          <template v-if="editing">
            <button
              class="reorder-btn"
              :disabled="idx === 0 || mealTypeChanging"
              aria-label="Move up"
              @click="onMoveUp(idx)"
            >↑</button>
            <button
              class="reorder-btn"
              :disabled="idx === activeMealTypes.length - 1 || mealTypeChanging"
              aria-label="Move down"
              @click="onMoveDown(idx)"
            >↓</button>
            <span class="label-text">{{ mealType }}</span>
            <button
              class="remove-btn"
              :disabled="activeMealTypes.length <= 1 || mealTypeChanging"
              :aria-label="`Remove ${mealType}`"
              @click="$emit('remove-meal-type', mealType)"
            >✕</button>
          </template>
          <template v-else>{{ mealType }}</template>
        </div>
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

      <!-- Add / edit meal type controls (Paid only) -->
      <div v-if="canAddMealType || activeMealTypes.length > 1" class="add-meal-type-row">
        <button v-if="canAddMealType && !editing" class="add-meal-type-btn" @click="$emit('add-meal-type')">
          + Add meal type
        </button>
        <button
          v-if="activeMealTypes.length > 1"
          class="edit-types-btn"
          :class="{ active: editing }"
          @click="editing = !editing"
        >{{ editing ? 'Done' : 'Edit types' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMealPlanStore } from '../stores/mealPlan'

const props = defineProps<{
  activeMealTypes: string[]
  canAddMealType: boolean
  mealTypeChanging?: boolean
}>()

const emit = defineEmits<{
  (e: 'slot-click', payload: { dayOfWeek: number; mealType: string }): void
  (e: 'add-meal-type'): void
  (e: 'remove-meal-type', mealType: string): void
  (e: 'reorder-meal-types', newOrder: string[]): void
}>()

const store = useMealPlanStore()
const { getSlot } = store

const collapsed = ref(false)
const editing = ref(false)

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function onMoveUp(idx: number) {
  if (idx === 0) return
  const arr = [...props.activeMealTypes]
  const tmp = arr[idx - 1]!
  arr[idx - 1] = arr[idx]!
  arr[idx] = tmp
  emit('reorder-meal-types', arr)
}

function onMoveDown(idx: number) {
  if (idx === props.activeMealTypes.length - 1) return
  const arr = [...props.activeMealTypes]
  const tmp = arr[idx]!
  arr[idx] = arr[idx + 1]!
  arr[idx + 1] = tmp
  emit('reorder-meal-types', arr)
}
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

.add-meal-type-row { padding: 0.4rem 0 0.2rem; display: flex; gap: 0.75rem; align-items: center; }
.add-meal-type-btn { font-size: 0.75rem; background: none; border: none; cursor: pointer; color: var(--color-accent); padding: 0; }
.edit-types-btn {
  font-size: 0.75rem; background: none; border: none; cursor: pointer;
  color: var(--color-text-secondary); padding: 0;
}
.edit-types-btn:hover { color: var(--color-text); }
.edit-types-btn.active { color: var(--color-accent); font-weight: 600; }

/* Edit mode — expand label column to fit controls */
.row-editing, .headers-editing { grid-template-columns: auto repeat(7, 1fr); }
.label-editing {
  flex-direction: row; align-items: center; gap: 2px;
  opacity: 1; white-space: nowrap;
}
.label-text { flex: 1; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.7; font-weight: 600; padding: 0 2px; }
.reorder-btn {
  background: none; border: 1px solid var(--color-border); border-radius: 3px;
  cursor: pointer; font-size: 0.6rem; padding: 1px 3px; line-height: 1;
  color: var(--color-text-secondary); min-width: 16px;
}
.reorder-btn:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-accent); }
.reorder-btn:disabled { opacity: 0.25; cursor: default; }
.remove-btn {
  background: none; border: none; cursor: pointer; font-size: 0.65rem;
  color: var(--color-text-secondary); padding: 1px 3px; border-radius: 3px; line-height: 1;
}
.remove-btn:hover:not(:disabled) { color: var(--color-error, #e05252); background: var(--color-error-subtle, #fef2f2); }
.remove-btn:disabled { opacity: 0.25; cursor: default; }

@media (max-width: 600px) {
  .day-headers, .meal-row { grid-template-columns: 2.5rem repeat(7, 1fr); }
  .row-editing, .headers-editing { grid-template-columns: auto repeat(7, 1fr); }
}
</style>
