// frontend/src/stores/mealPlan.ts
/**
 * Meal Plan Store
 *
 * Manages the active week plan, shopping list, and prep session.
 * Uses immutable update patterns — never mutates store state in place.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  mealPlanAPI,
  type MealPlan,
  type MealPlanSlot,
  type ShoppingList,
  type PrepSession,
  type PrepTask,
} from '../services/api'

export const useMealPlanStore = defineStore('mealPlan', () => {
  const plans = ref<MealPlan[]>([])
  const activePlan = ref<MealPlan | null>(null)
  const shoppingList = ref<ShoppingList | null>(null)
  const prepSession = ref<PrepSession | null>(null)
  const loading = ref(false)
  const shoppingListLoading = ref(false)
  const prepLoading = ref(false)

  const slots = computed<MealPlanSlot[]>(() => activePlan.value?.slots ?? [])

  function getSlot(dayOfWeek: number, mealType: string): MealPlanSlot | undefined {
    return slots.value.find(s => s.day_of_week === dayOfWeek && s.meal_type === mealType)
  }

  async function loadPlans() {
    loading.value = true
    try {
      const result = await mealPlanAPI.list()
      plans.value = Array.isArray(result) ? result : []
    } finally {
      loading.value = false
    }
  }

  /**
   * Auto-select the best available plan without a round-trip.
   * Prefers the plan whose week_start matches preferredWeekStart (current week's Monday).
   * Falls back to the first plan in the list (most recent, since list is DESC).
   * No-ops if a plan is already active or no plans exist.
   */
  function autoSelectPlan(preferredWeekStart?: string) {
    if (activePlan.value || plans.value.length === 0) return
    const match = preferredWeekStart
      ? (plans.value.find(p => p.week_start === preferredWeekStart) ?? plans.value[0])
      : plans.value[0]
    if (match) activePlan.value = match ?? null
  }

  async function createPlan(weekStart: string, mealTypes: string[]): Promise<MealPlan> {
    const plan = await mealPlanAPI.create(weekStart, mealTypes)
    plans.value = [plan, ...plans.value]
    activePlan.value = plan
    shoppingList.value = null
    prepSession.value = null
    return plan
  }

  async function setActivePlan(planId: number) {
    loading.value = true
    try {
      activePlan.value = await mealPlanAPI.get(planId)
      shoppingList.value = null
      prepSession.value = null
    } finally {
      loading.value = false
    }
  }

  async function upsertSlot(dayOfWeek: number, mealType: string, data: { recipe_id?: number | null; servings?: number; custom_label?: string | null }): Promise<void> {
    if (!activePlan.value) return
    const slot = await mealPlanAPI.upsertSlot(activePlan.value.id, dayOfWeek, mealType, data)
    const current = activePlan.value
    const idx = current.slots.findIndex(
      s => s.day_of_week === dayOfWeek && s.meal_type === mealType
    )
    activePlan.value = {
      ...current,
      slots: idx >= 0
        ? [...current.slots.slice(0, idx), slot, ...current.slots.slice(idx + 1)]
        : [...current.slots, slot],
    }
    shoppingList.value = null
    prepSession.value = null
  }

  async function clearSlot(dayOfWeek: number, mealType: string): Promise<void> {
    if (!activePlan.value) return
    const slot = getSlot(dayOfWeek, mealType)
    if (!slot) return
    await mealPlanAPI.deleteSlot(activePlan.value.id, slot.id)
    activePlan.value = {
      ...activePlan.value,
      slots: activePlan.value.slots.filter(s => s.id !== slot.id),
    }
    shoppingList.value = null
    prepSession.value = null
  }

  async function loadShoppingList(): Promise<void> {
    if (!activePlan.value) return
    shoppingListLoading.value = true
    try {
      shoppingList.value = await mealPlanAPI.getShoppingList(activePlan.value.id)
    } finally {
      shoppingListLoading.value = false
    }
  }

  async function loadPrepSession(): Promise<void> {
    if (!activePlan.value) return
    prepLoading.value = true
    try {
      prepSession.value = await mealPlanAPI.getPrepSession(activePlan.value.id)
    } finally {
      prepLoading.value = false
    }
  }

  async function addMealType(mealType: string): Promise<void> {
    if (!activePlan.value) return
    const current = activePlan.value.meal_types
    if (current.includes(mealType)) return
    const updated = await mealPlanAPI.updateMealTypes(activePlan.value.id, [...current, mealType])
    activePlan.value = updated
  }

  async function removeMealType(mealType: string): Promise<void> {
    if (!activePlan.value) return
    const next = activePlan.value.meal_types.filter(t => t !== mealType)
    if (next.length === 0) return // always keep at least one
    const updated = await mealPlanAPI.updateMealTypes(activePlan.value.id, next)
    activePlan.value = updated
  }

  async function reorderMealTypes(newOrder: string[]): Promise<void> {
    if (!activePlan.value) return
    const updated = await mealPlanAPI.updateMealTypes(activePlan.value.id, newOrder)
    activePlan.value = updated
  }

  async function updatePrepTask(taskId: number, data: Partial<Pick<PrepTask, 'duration_minutes' | 'sequence_order' | 'notes' | 'equipment'>>): Promise<void> {
    if (!activePlan.value || !prepSession.value) return
    const updated = await mealPlanAPI.updatePrepTask(activePlan.value.id, taskId, data)
    const idx = prepSession.value.tasks.findIndex(t => t.id === taskId)
    if (idx >= 0) {
      prepSession.value = {
        ...prepSession.value,
        tasks: [
          ...prepSession.value.tasks.slice(0, idx),
          updated,
          ...prepSession.value.tasks.slice(idx + 1),
        ],
      }
    }
  }

  return {
    plans, activePlan, shoppingList, prepSession,
    loading, shoppingListLoading, prepLoading, slots,
    getSlot, loadPlans, autoSelectPlan, createPlan, setActivePlan,
    addMealType, removeMealType, reorderMealTypes,
    upsertSlot, clearSlot, loadShoppingList, loadPrepSession, updatePrepTask,
  }
})
