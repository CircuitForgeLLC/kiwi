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
      plans.value = await mealPlanAPI.list()
    } finally {
      loading.value = false
    }
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
    getSlot, loadPlans, createPlan, setActivePlan,
    upsertSlot, clearSlot, loadShoppingList, loadPrepSession, updatePrepTask,
  }
})
