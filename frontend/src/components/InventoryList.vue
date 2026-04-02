<template>
  <div class="inventory-list">
    <!-- Stats Summary -->
    <div class="card">
      <h2>📊 Inventory Overview</h2>
      <div v-if="stats" class="grid-stats">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_items }}</div>
          <div class="stat-label">Total Items</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.available_items }}</div>
          <div class="stat-label">Available</div>
        </div>
        <div class="stat-card expiry-soon">
          <div class="stat-value">{{ store.expiringItems.length }}</div>
          <div class="stat-label">Expiring Soon</div>
        </div>
        <div class="stat-card expiry-warning">
          <div class="stat-value">{{ store.expiredItems.length }}</div>
          <div class="stat-label">Expired</div>
        </div>
      </div>
    </div>

    <!-- Scanner Gun -->
    <div class="card">
      <h2>🔫 Scanner Gun</h2>
      <p style="color: var(--color-text-secondary); margin-bottom: 15px;">Use your barcode scanner gun below. Scan will auto-submit when Enter is pressed.</p>

      <div class="form-group">
        <label for="scannerGunInput">Scan barcode here:</label>
        <input
          id="scannerGunInput"
          ref="scannerGunInput"
          v-model="scannerBarcode"
          type="text"
          placeholder="Focus here and scan with barcode gun..."
          @keypress.enter="handleScannerGunInput"
          autocomplete="off"
          class="scanner-input"
        />
      </div>

      <div class="form-group">
        <label>Location</label>
        <div class="button-group">
          <button
            v-for="loc in locations"
            :key="loc.value"
            :class="['btn-option', { active: scannerLocation === loc.value }]"
            @click="scannerLocation = loc.value"
            type="button"
          >
            {{ loc.icon }} {{ loc.label }}
          </button>
        </div>
      </div>

      <div class="form-group">
        <label>Quantity</label>
        <div class="quantity-control">
          <button class="btn-qty" @click="scannerQuantity = Math.max(0.1, scannerQuantity - 1)" type="button">−</button>
          <input v-model.number="scannerQuantity" type="number" min="0.1" step="0.1" class="qty-input" />
          <button class="btn-qty" @click="scannerQuantity += 1" type="button">+</button>
        </div>
      </div>

      <div v-if="scannerLoading" class="loading-inline">
        <div class="spinner-small"></div>
        <p>Processing barcode...</p>
      </div>

      <div v-if="scannerResults.length > 0" class="results">
        <div v-for="(result, index) in scannerResults" :key="index" :class="['result-item', `result-${result.type}`]">
          {{ result.message }}
        </div>
      </div>
    </div>

    <!-- Camera/Image Barcode Scan -->
    <div class="card">
      <h2>📷 Scan Barcode (Camera/Image)</h2>
      <div class="upload-area" @click="triggerBarcodeInput">
        <div class="upload-icon">📸</div>
        <div class="upload-text">Click to scan barcode or drag and drop</div>
        <div class="upload-hint">Take a photo of a product barcode (UPC/EAN)</div>
      </div>
      <input
        ref="barcodeFileInput"
        type="file"
        accept="image/*"
        capture="environment"
        style="display: none"
        @change="handleBarcodeImageSelect"
      />

      <div style="margin-top: 20px">
        <div class="form-group">
          <label>Location</label>
          <div class="button-group">
            <button
              v-for="loc in locations"
              :key="loc.value"
              :class="['btn-option', { active: barcodeLocation === loc.value }]"
              @click="barcodeLocation = loc.value"
              type="button"
            >
              {{ loc.icon }} {{ loc.label }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>Quantity</label>
          <div class="quantity-control">
            <button class="btn-qty" @click="barcodeQuantity = Math.max(0.1, barcodeQuantity - 1)" type="button">−</button>
            <input v-model.number="barcodeQuantity" type="number" min="0.1" step="0.1" class="qty-input" />
            <button class="btn-qty" @click="barcodeQuantity += 1" type="button">+</button>
          </div>
        </div>
      </div>

      <div v-if="barcodeLoading" class="loading-inline">
        <div class="spinner-small"></div>
        <p>Scanning barcode...</p>
      </div>

      <div v-if="barcodeResults.length > 0" class="results">
        <div v-for="(result, index) in barcodeResults" :key="index" :class="['result-item', `result-${result.type}`]">
          {{ result.message }}
        </div>
      </div>
    </div>

    <!-- Manual Add -->
    <div class="card">
      <h2>➕ Add Item Manually</h2>
      <div class="form-row">
        <div class="form-group">
          <label>Product Name *</label>
          <input v-model="manualForm.name" type="text" placeholder="e.g., Organic Milk" required />
        </div>
        <div class="form-group">
          <label>Brand</label>
          <input v-model="manualForm.brand" type="text" placeholder="e.g., Horizon" />
        </div>
      </div>

      <div class="form-group">
        <label>Quantity *</label>
        <div class="quantity-control">
          <button class="btn-qty" @click="manualForm.quantity = Math.max(0.1, manualForm.quantity - 1)" type="button">−</button>
          <input v-model.number="manualForm.quantity" type="number" min="0.1" step="0.1" required class="qty-input" />
          <button class="btn-qty" @click="manualForm.quantity += 1" type="button">+</button>
        </div>
      </div>

      <div class="form-group">
        <label>Unit</label>
        <div class="button-group">
          <button
            v-for="unit in units"
            :key="unit.value"
            :class="['btn-option', { active: manualForm.unit === unit.value }]"
            @click="manualForm.unit = unit.value"
            type="button"
          >
            {{ unit.label }}
          </button>
        </div>
      </div>

      <div class="form-group">
        <label>Location *</label>
        <div class="button-group">
          <button
            v-for="loc in locations"
            :key="loc.value"
            :class="['btn-option', { active: manualForm.location === loc.value }]"
            @click="manualForm.location = loc.value"
            type="button"
          >
            {{ loc.icon }} {{ loc.label }}
          </button>
        </div>
      </div>

      <div class="form-group">
        <label>Expiration Date</label>
        <input v-model="manualForm.expirationDate" type="date" />
      </div>

      <button @click="addManualItem" class="button" :disabled="manualLoading">
        {{ manualLoading ? 'Adding...' : 'Add to Inventory' }}
      </button>
    </div>

    <!-- Current Inventory -->
    <div class="card">
      <div class="header">
        <h2>📋 Current Inventory</h2>
      </div>

      <div class="filters-section">
        <div class="form-group">
          <label>Filter by Location</label>
          <div class="button-group">
            <button
              :class="['btn-option', { active: locationFilter === 'all' }]"
              @click="locationFilter = 'all'; onFilterChange()"
              type="button"
            >
              All
            </button>
            <button
              v-for="loc in locations"
              :key="loc.value"
              :class="['btn-option', { active: locationFilter === loc.value }]"
              @click="locationFilter = loc.value; onFilterChange()"
              type="button"
            >
              {{ loc.icon }} {{ loc.label }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>Filter by Status</label>
          <div class="button-group">
            <button
              v-for="status in statuses"
              :key="status.value"
              :class="['btn-option', { active: statusFilter === status.value }]"
              @click="statusFilter = status.value; onFilterChange()"
              type="button"
            >
              {{ status.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="divider"></div>

      <div class="inventory-container">
        <div v-if="loading && items.length === 0" class="loading">
          Loading inventory...
        </div>

        <!-- Empty State -->
        <div v-else-if="!loading && filteredItems.length === 0" class="empty-state">
          <p>No items found.</p>
          <p class="hint">Scan a barcode to add items to your inventory!</p>
        </div>

        <!-- Inventory Items -->
        <div v-else class="grid-auto">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="item-card"
            :class="getItemClass(item)"
          >
            <div class="item-header">
              <h3 class="item-name">{{ item.product_name || 'Unknown Product' }}</h3>
              <span v-if="item.category" class="item-brand">{{ item.category }}</span>
            </div>

            <div class="item-details">
              <div class="detail-row">
                <span class="label">Location:</span>
                <span class="value">{{ item.location }}</span>
              </div>
              <div class="detail-row">
                <span class="label">Quantity:</span>
                <span class="value">{{ item.quantity }} {{ item.unit }}</span>
              </div>
              <div v-if="item.expiration_date" class="detail-row">
                <span class="label">Expires:</span>
                <span class="value" :class="getExpiryClass(item.expiration_date)">
                  {{ formatDate(item.expiration_date) }}
                  <span class="days-left">({{ getDaysUntilExpiry(item.expiration_date) }})</span>
                </span>
              </div>
              <div v-if="item.purchase_date" class="detail-row">
                <span class="label">Purchased:</span>
                <span class="value">{{ formatDate(item.purchase_date) }}</span>
              </div>
              <div v-if="item.notes" class="detail-row notes">
                <span class="label">Notes:</span>
                <span class="value">{{ item.notes }}</span>
              </div>
            </div>

            <div class="item-actions">
              <button @click="editItem(item)" class="btn-edit">
                ✏️ Edit
              </button>
              <button @click="markAsConsumed(item)" class="btn-consumed">
                ✓ Consumed
              </button>
              <button @click="confirmDelete(item)" class="btn-delete">
                🗑️ Delete
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <EditItemModal
      v-if="editingItem"
      :item="editingItem"
      @close="editingItem = null"
      @save="handleSave"
    />

    <!-- Confirm Dialog -->
    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="confirmDialog.onConfirm"
      @cancel="confirmDialog.show = false"
    />

    <!-- Toast Notification -->
    <ToastNotification
      :show="toast.show"
      :message="toast.message"
      :type="toast.type"
      :duration="toast.duration"
      @close="toast.show = false"
    />

    <!-- Export -->
    <div class="card">
      <h2>📥 Export</h2>
      <button @click="exportCSV" class="button">📊 Download CSV</button>
      <button @click="exportExcel" class="button">📈 Download Excel</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { storeToRefs } from 'pinia'
import { useInventoryStore } from '../stores/inventory'
import { inventoryAPI } from '../services/api'
import type { InventoryItem } from '../services/api'
import EditItemModal from './EditItemModal.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import ToastNotification from './ToastNotification.vue'

const store = useInventoryStore()
const { items, stats, loading, locationFilter, statusFilter } = storeToRefs(store)

const filteredItems = computed(() => store.filteredItems)
const editingItem = ref<InventoryItem | null>(null)

// Options for button groups
const locations = [
  { value: 'fridge', label: 'Fridge', icon: '🧊' },
  { value: 'freezer', label: 'Freezer', icon: '❄️' },
  { value: 'garage_freezer', label: 'Garage Freezer', icon: '🏠' },
  { value: 'pantry', label: 'Pantry', icon: '🏪' },
  { value: 'cabinet', label: 'Cabinet', icon: '🗄️' },
]

const units = [
  { value: 'count', label: 'Count' },
  { value: 'kg', label: 'kg' },
  { value: 'lbs', label: 'lbs' },
  { value: 'oz', label: 'oz' },
  { value: 'liters', label: 'L' },
]

const statuses = [
  { value: 'available', label: 'Available' },
  { value: 'consumed', label: 'Consumed' },
  { value: 'expired', label: 'Expired' },
]

// Confirm Dialog
const confirmDialog = reactive({
  show: false,
  title: 'Confirm',
  message: '',
  type: 'primary' as 'primary' | 'danger' | 'warning',
  confirmText: 'Confirm',
  onConfirm: () => {},
})

// Toast Notification
const toast = reactive({
  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  duration: 3000,
})

function showToast(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info', duration = 3000) {
  toast.message = message
  toast.type = type
  toast.duration = duration
  toast.show = true
}

function showConfirm(
  message: string,
  onConfirm: () => void,
  options: {
    title?: string
    type?: 'primary' | 'danger' | 'warning'
    confirmText?: string
  } = {}
) {
  confirmDialog.message = message
  confirmDialog.onConfirm = () => {
    onConfirm()
    confirmDialog.show = false
  }
  confirmDialog.title = options.title || 'Confirm'
  confirmDialog.type = options.type || 'primary'
  confirmDialog.confirmText = options.confirmText || 'Confirm'
  confirmDialog.show = true
}

// Scanner Gun
const scannerGunInput = ref<HTMLInputElement | null>(null)
const scannerBarcode = ref('')
const scannerLocation = ref('pantry')
const scannerQuantity = ref(1)
const scannerLoading = ref(false)
const scannerResults = ref<Array<{ type: string; message: string }>>([])

// Barcode Image
const barcodeFileInput = ref<HTMLInputElement | null>(null)
const barcodeLocation = ref('pantry')
const barcodeQuantity = ref(1)
const barcodeLoading = ref(false)
const barcodeResults = ref<Array<{ type: string; message: string }>>([])

// Manual Form
const manualForm = ref({
  name: '',
  brand: '',
  quantity: 1,
  unit: 'count',
  location: 'pantry',
  expirationDate: '',
})
const manualLoading = ref(false)

onMounted(async () => {
  await store.fetchItems()
  await store.fetchStats()
  // Auto-focus scanner gun input
  setTimeout(() => {
    scannerGunInput.value?.focus()
  }, 100)
})

function onFilterChange() {
  store.fetchItems()
}

async function refreshItems() {
  await store.fetchItems()
  await store.fetchStats()
}

function editItem(item: InventoryItem) {
  editingItem.value = item
}

async function handleSave() {
  editingItem.value = null
  await refreshItems()
}

async function confirmDelete(item: InventoryItem) {
  showConfirm(
    `Are you sure you want to delete ${item.product_name || 'item'}?`,
    async () => {
      try {
        await store.deleteItem(item.id)
        showToast(`${item.product_name || 'item'} deleted successfully`, 'success')
      } catch (err) {
        showToast('Failed to delete item', 'error')
      }
    },
    {
      title: 'Delete Item',
      type: 'danger',
      confirmText: 'Delete',
    }
  )
}

async function markAsConsumed(item: InventoryItem) {
  showConfirm(
    `Mark ${item.product_name || 'item'} as consumed?`,
    async () => {
      try {
        await inventoryAPI.consumeItem(item.id)
        await refreshItems()
        showToast(`${item.product_name || 'item'} marked as consumed`, 'success')
      } catch (err) {
        showToast('Failed to mark item as consumed', 'error')
      }
    },
    {
      title: 'Mark as Consumed',
      type: 'primary',
      confirmText: 'Mark as Consumed',
    }
  )
}

// Scanner Gun Functions
async function handleScannerGunInput() {
  const barcode = scannerBarcode.value.trim()
  if (!barcode) return

  scannerLoading.value = true
  scannerResults.value = []

  try {
    const result = await inventoryAPI.scanBarcodeText(
      barcode,
      scannerLocation.value,
      scannerQuantity.value,
      true
    )

    if (result.success && result.barcodes_found > 0) {
      const item = result.results[0]
      scannerResults.value.push({
        type: 'success',
        message: `✓ Added: ${item.product_name || 'item'}${''} to ${scannerLocation.value}`,
      })
      await refreshItems()
    } else {
      scannerResults.value.push({
        type: 'error',
        message: result.message || 'Barcode not found',
      })
    }
  } catch (error: any) {
    scannerResults.value.push({
      type: 'error',
      message: `Error: ${error.message}`,
    })
  } finally {
    scannerLoading.value = false
    scannerBarcode.value = ''
    scannerGunInput.value?.focus()
  }
}

// Barcode Image Functions
function triggerBarcodeInput() {
  barcodeFileInput.value?.click()
}

async function handleBarcodeImageSelect(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  barcodeLoading.value = true
  barcodeResults.value = []

  try {
    const result = await inventoryAPI.scanBarcodeImage(
      file,
      barcodeLocation.value,
      barcodeQuantity.value,
      true
    )

    if (result.success && result.barcodes_found > 0) {
      const item = result.results[0]
      barcodeResults.value.push({
        type: 'success',
        message: `✓ Found: ${item.product_name || 'item'}${''}`,
      })
      await refreshItems()
    } else {
      barcodeResults.value.push({
        type: 'error',
        message: 'No barcode found in image',
      })
    }
  } catch (error: any) {
    barcodeResults.value.push({
      type: 'error',
      message: `Error: ${error.message}`,
    })
  } finally {
    barcodeLoading.value = false
    if (barcodeFileInput.value) {
      barcodeFileInput.value.value = ''
    }
  }
}

// Manual Add Functions
async function addManualItem() {
  const { name, brand, quantity, unit, location, expirationDate } = manualForm.value

  if (!name || !quantity || !location) {
    showToast('Please fill in required fields', 'warning')
    return
  }

  manualLoading.value = true

  try {
    // Create product first
    const product = await inventoryAPI.createProduct({
      name,
      brand: brand || undefined,
      source: 'manual',
    })

    // Add to inventory
    await inventoryAPI.createItem({
      product_id: product.id,
      quantity,
      unit,
      location,
      expiration_date: expirationDate || undefined,
      source: 'manual',
    })

    showToast(`${name} added to inventory!`, 'success')
    // Clear form
    manualForm.value = {
      name: '',
      brand: '',
      quantity: 1,
      unit: 'count',
      location: 'pantry',
      expirationDate: '',
    }
    await refreshItems()
  } catch (error: any) {
    showToast(`Error: ${error.message}`, 'error')
  } finally {
    manualLoading.value = false
  }
}

// Export Functions
function exportCSV() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  window.open(`${apiUrl}/export/inventory/csv`, '_blank')
}

function exportExcel() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  window.open(`${apiUrl}/export/inventory/excel`, '_blank')
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString()
}

function getDaysUntilExpiry(expiryStr: string): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(expiryStr)
  expiry.setHours(0, 0, 0, 0)

  const diffTime = expiry.getTime() - today.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays < 0) {
    return `${Math.abs(diffDays)} days ago`
  } else if (diffDays === 0) {
    return 'today'
  } else if (diffDays === 1) {
    return 'tomorrow'
  } else {
    return `in ${diffDays} days`
  }
}

function getExpiryClass(expiryStr: string): string {
  const today = new Date()
  const expiry = new Date(expiryStr)
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'expired'
  if (diffDays <= 3) return 'expiring-soon'
  if (diffDays <= 7) return 'expiring-warning'
  return ''
}

function getItemClass(item: InventoryItem): string {
  if (!item.expiration_date) return ''

  const today = new Date()
  const expiry = new Date(item.expiration_date)
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'item-expired'
  if (diffDays <= 3) return 'item-expiring-soon'
  if (diffDays <= 7) return 'item-expiring-warning'
  return ''
}
</script>

<style scoped>
.inventory-list {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 28px;
}

.filters {
  display: flex;
  gap: 10px;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--color-radius-sm);
  font-size: var(--font-size-sm);
}

.btn-refresh {
  padding: 8px 16px;
  background: var(--color-success);
  color: white;
  border: none;
  border-radius: var(--color-radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
}

.btn-refresh:hover {
  background: var(--color-success-dark);
}

.btn-refresh:disabled {
  background: var(--color-text-muted);
  cursor: not-allowed;
}

.stats-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 30px;
}

.stat-card {
  background: var(--color-bg-card);
  padding: 20px;
  border-radius: var(--radius-lg);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.stat-card.warning {
  border-left: 4px solid var(--color-warning);
}

.stat-card.danger {
  border-left: 4px solid var(--color-error);
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: bold;
  color: var(--color-text-primary);
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: 5px;
}

.error-message {
  background: var(--color-error-bg);
  color: var(--color-error-dark);
  padding: 12px;
  border-radius: var(--color-radius-sm);
  margin-bottom: 20px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--color-text-secondary);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--color-text-secondary);
}

.empty-state .hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

/* Using .grid-auto from theme.css */

.item-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.2s;
}

.item-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.item-card.item-expiring-soon {
  border-left: 4px solid var(--color-error);
}

.item-card.item-expiring-warning {
  border-left: 4px solid var(--color-warning);
}

.item-card.item-expired {
  opacity: 0.6;
  border-left: 4px solid #9e9e9e;
}

.item-header {
  margin-bottom: 15px;
}

.item-name {
  margin: 0 0 5px 0;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}

.item-brand {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.item-details {
  margin-bottom: 15px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: var(--font-size-sm);
}

.detail-row.notes {
  flex-direction: column;
  gap: 5px;
}

.detail-row .label {
  font-weight: 600;
  color: var(--color-text-secondary);
}

.detail-row .value {
  color: var(--color-text-primary);
}

.detail-row .value.expired {
  color: var(--color-error);
  font-weight: bold;
}

.detail-row .value.expiring-soon {
  color: var(--color-error);
}

.detail-row .value.expiring-warning {
  color: var(--color-warning);
}

.days-left {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.item-actions {
  display: flex;
  gap: 10px;
  margin-top: 15px;
}

.btn-edit,
.btn-delete {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: var(--color-radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background 0.2s;
}

.btn-edit {
  background: var(--color-info);
  color: white;
}

.btn-edit:hover {
  background: var(--color-info-dark);
}

.btn-delete {
  background: var(--color-error);
  color: white;
}

.btn-delete:hover {
  background: var(--color-error-dark);
}

.btn-consumed {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: var(--color-radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background 0.2s;
  background: var(--color-success);
  color: white;
}

.btn-consumed:hover {
  background: var(--color-success-dark);
}

/* Card containers */
.card {
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
  box-shadow: var(--shadow-xl);
  margin-bottom: var(--spacing-lg);
}

.card h2 {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
}

/* Using .grid-stats from theme.css */

.stat-card {
  background: var(--color-bg-secondary);
  padding: 20px;
  border-radius: var(--radius-lg);
  text-align: center;
}

.stat-card.expiry-soon {
  border-left: 4px solid var(--color-warning);
}

.stat-card.expiry-warning {
  border-left: 4px solid var(--color-error-light);
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: bold;
  color: var(--color-primary);
  margin-bottom: 5px;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* Upload Area */
.upload-area {
  border: 3px dashed var(--color-primary);
  border-radius: var(--radius-lg);
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: var(--color-bg-secondary);
}

.upload-area:hover {
  border-color: var(--color-secondary);
  background: var(--color-bg-elevated);
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 20px;
}

.upload-text {
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
  margin-bottom: 10px;
}

.upload-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* Forms */
.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.scanner-input {
  font-size: var(--font-size-lg);
  font-family: monospace;
  background: var(--color-bg-input);
}

/* Button Groups */
.button-group {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.btn-option {
  padding: var(--spacing-sm) var(--spacing-md);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  flex: 1;
  min-width: 80px;
  white-space: nowrap;
}

.btn-option:hover {
  background: var(--color-bg-primary);
  border-color: var(--color-primary);
  transform: translateY(-1px);
}

.btn-option.active {
  background: var(--gradient-primary);
  color: white;
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

/* Quantity Control */
.quantity-control {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.btn-qty {
  width: 40px;
  height: 40px;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.btn-qty:hover {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  transform: scale(1.05);
}

.btn-qty:active {
  transform: scale(0.95);
}

.qty-input {
  width: 100px;
  text-align: center;
  font-size: var(--font-size-base);
  font-weight: 600;
  padding: var(--spacing-sm);
}

/* Filters Section */
.filters-section {
  margin-bottom: var(--spacing-lg);
}

.filters-section .form-group {
  margin-bottom: var(--spacing-md);
}

.divider {
  height: 1px;
  background: var(--color-border);
  margin: var(--spacing-lg) 0;
}

.inventory-container {
  margin-top: var(--spacing-lg);
}

/* Mobile Responsive - Handled by theme.css grid utilities
   Component-specific overrides only below */

@media (max-width: 480px) {
  /* Item-specific mobile adjustments */
  .item-card {
    padding: 15px;
  }

  .stat-card {
    padding: 15px;
  }

  .button-group {
    flex-direction: column;
    gap: 8px;
  }

  .btn-option {
    width: 100%;
  }

  .item-actions {
    flex-direction: column;
    gap: 8px;
  }

  .btn-edit,
  .btn-delete,
  .btn-consumed {
    width: 100%;
  }
}

/* Loading */
.loading-inline {
  text-align: center;
  padding: 20px;
  margin-top: 15px;
}

.spinner-small {
  border: 3px solid #f3f3f3;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  margin: 0 auto 10px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* Results */
.results {
  margin-top: 20px;
}

.result-item {
  padding: 15px;
  border-radius: var(--radius-md);
  margin-bottom: 10px;
}

.result-success {
  background: var(--color-success-bg);
  color: var(--color-success-dark);
  border: 1px solid var(--color-success-border);
}

.result-error {
  background: var(--color-error-bg);
  color: var(--color-error-dark);
  border: 1px solid var(--color-error-border);
}

.result-info {
  background: var(--color-info-bg);
  color: var(--color-info-dark);
  border: 1px solid var(--color-info-border);
}

/* Button */
.button {
  background: var(--gradient-primary);
  color: white;
  border: none;
  padding: 12px 30px;
  font-size: 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform 0.2s;
  margin-right: 10px;
}

.button:hover {
  transform: translateY(-2px);
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
</style>
