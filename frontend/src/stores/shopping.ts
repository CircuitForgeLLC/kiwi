import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { shoppingAPI, type ShoppingItem, type ShoppingItemCreate, type ShoppingItemUpdate } from '@/services/api'

export const useShoppingStore = defineStore('shopping', () => {
  const items = ref<ShoppingItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const uncheckedItems = computed(() => items.value.filter(i => !i.checked))
  const checkedItems = computed(() => items.value.filter(i => i.checked))
  const totalCount = computed(() => items.value.length)
  const checkedCount = computed(() => checkedItems.value.length)

  async function fetchItems(includeChecked = true) {
    loading.value = true
    error.value = null
    try {
      items.value = await shoppingAPI.list(includeChecked)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load shopping list'
    } finally {
      loading.value = false
    }
  }

  async function addItem(item: ShoppingItemCreate) {
    const created = await shoppingAPI.add(item)
    items.value = [...items.value, created]
    return created
  }

  async function addFromRecipe(recipeId: number, includeCovered = false) {
    const added = await shoppingAPI.addFromRecipe(recipeId, includeCovered)
    items.value = [...items.value, ...added]
    return added
  }

  async function toggleChecked(id: number) {
    const item = items.value.find(i => i.id === id)
    if (!item) return
    const updated = await shoppingAPI.update(id, { checked: !item.checked })
    items.value = items.value.map(i => i.id === id ? updated : i)
    return updated
  }

  async function updateItem(id: number, update: ShoppingItemUpdate) {
    const updated = await shoppingAPI.update(id, update)
    items.value = items.value.map(i => i.id === id ? updated : i)
    return updated
  }

  async function removeItem(id: number) {
    await shoppingAPI.remove(id)
    items.value = items.value.filter(i => i.id !== id)
  }

  async function clearChecked() {
    await shoppingAPI.clearChecked()
    items.value = items.value.filter(i => !i.checked)
  }

  async function clearAll() {
    await shoppingAPI.clearAll()
    items.value = []
  }

  async function confirmPurchase(id: number, location = 'pantry', quantity?: number, unit?: string) {
    const inventoryItem = await shoppingAPI.confirmPurchase(id, location, quantity, unit)
    // Mark checked in local state (server also marks it)
    items.value = items.value.map(i => i.id === id ? { ...i, checked: true } : i)
    return inventoryItem
  }

  return {
    items, loading, error,
    uncheckedItems, checkedItems, totalCount, checkedCount,
    fetchItems, addItem, addFromRecipe,
    toggleChecked, updateItem, removeItem,
    clearChecked, clearAll, confirmPurchase,
  }
})
