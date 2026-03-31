/**
 * Inventory Store
 *
 * Manages inventory items, products, and related state using Pinia.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { inventoryAPI, type InventoryItem, type InventoryStats, type InventoryItemUpdate } from '../services/api'

export const useInventoryStore = defineStore('inventory', () => {
  // State
  const items = ref<InventoryItem[]>([])
  const stats = ref<InventoryStats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Filter state
  const locationFilter = ref<string>('all')
  const statusFilter = ref<string>('available')

  // Computed
  const filteredItems = computed(() => {
    return items.value.filter((item) => {
      const matchesLocation = locationFilter.value === 'all' || item.location === locationFilter.value
      const matchesStatus = statusFilter.value === 'all' || item.status === statusFilter.value
      return matchesLocation && matchesStatus
    })
  })

  const expiringItems = computed(() => {
    const today = new Date()
    const weekFromNow = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)

    return items.value.filter((item) => {
      if (!item.expiration_date || item.status !== 'available') return false
      const expiryDate = new Date(item.expiration_date)
      return expiryDate >= today && expiryDate <= weekFromNow
    })
  })

  const expiredItems = computed(() => {
    const today = new Date()

    return items.value.filter((item) => {
      if (!item.expiration_date || item.status !== 'available') return false
      const expiryDate = new Date(item.expiration_date)
      return expiryDate < today
    })
  })

  // Actions
  async function fetchItems() {
    loading.value = true
    error.value = null

    try {
      items.value = await inventoryAPI.listItems({
        status: statusFilter.value === 'all' ? undefined : statusFilter.value,
        location: locationFilter.value === 'all' ? undefined : locationFilter.value,
        limit: 1000,
      })
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to fetch inventory items'
      console.error('Error fetching inventory:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      stats.value = await inventoryAPI.getStats()
    } catch (err: any) {
      console.error('Error fetching stats:', err)
    }
  }

  async function updateItem(itemId: string, update: InventoryItemUpdate) {
    loading.value = true
    error.value = null

    try {
      const updatedItem = await inventoryAPI.updateItem(itemId, update)

      // Update in local state
      const index = items.value.findIndex((item) => item.id === itemId)
      if (index !== -1) {
        items.value[index] = updatedItem
      }

      return updatedItem
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to update item'
      console.error('Error updating item:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteItem(itemId: string) {
    loading.value = true
    error.value = null

    try {
      await inventoryAPI.deleteItem(itemId)

      // Remove from local state
      items.value = items.value.filter((item) => item.id !== itemId)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to delete item'
      console.error('Error deleting item:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function scanBarcode(barcode: string, location: string = 'pantry', quantity: number = 1) {
    loading.value = true
    error.value = null

    try {
      const result = await inventoryAPI.scanBarcodeText(barcode, location, quantity, true)

      // Refresh items after successful scan
      if (result.success) {
        await fetchItems()
      }

      return result
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to scan barcode'
      console.error('Error scanning barcode:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  function setLocationFilter(location: string) {
    locationFilter.value = location
  }

  function setStatusFilter(status: string) {
    statusFilter.value = status
  }

  return {
    // State
    items,
    stats,
    loading,
    error,
    locationFilter,
    statusFilter,

    // Computed
    filteredItems,
    expiringItems,
    expiredItems,

    // Actions
    fetchItems,
    fetchStats,
    updateItem,
    deleteItem,
    scanBarcode,
    setLocationFilter,
    setStatusFilter,
  }
})
