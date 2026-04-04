<template>
  <div class="inventory-list">

    <!-- Stats Strip -->
    <div v-if="stats" class="stats-strip">
      <div class="stat-strip-item">
        <div class="stat-num">{{ stats.total_items }}</div>
        <div class="stat-lbl">Total</div>
      </div>
      <div class="stat-strip-item">
        <div class="stat-num text-amber">{{ stats.available_items }}</div>
        <div class="stat-lbl">Available</div>
      </div>
      <div class="stat-strip-item">
        <div class="stat-num text-warning">{{ store.expiringItems.length }}</div>
        <div class="stat-lbl">Expiring</div>
      </div>
      <div class="stat-strip-item">
        <div class="stat-num text-error">{{ store.expiredItems.length }}</div>
        <div class="stat-lbl">Expired</div>
      </div>
    </div>

    <!-- Scan Card — collapsible with Gun / Camera toggle -->
    <div class="card scan-card">
      <div class="scan-card-header">
        <h2 class="section-title">Add Item</h2>
        <div class="scan-mode-toggle">
          <button
            :class="['scan-mode-btn', { active: scanMode === 'gun' }]"
            @click="scanMode = 'gun'"
            type="button"
            aria-label="Scanner gun mode"
          >
            <!-- barcode icon -->
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
              <rect x="2" y="4" width="2" height="16" rx="0.5"/>
              <rect x="6" y="4" width="1" height="16" rx="0.5"/>
              <rect x="9" y="4" width="2" height="16" rx="0.5"/>
              <rect x="13" y="4" width="1" height="16" rx="0.5"/>
              <rect x="16" y="4" width="2" height="16" rx="0.5"/>
              <rect x="20" y="4" width="2" height="16" rx="0.5"/>
            </svg>
            <span>Gun</span>
          </button>
          <button
            :class="['scan-mode-btn', { active: scanMode === 'camera' }]"
            @click="scanMode = 'camera'"
            type="button"
            aria-label="Camera scan mode"
          >
            <!-- camera icon -->
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
            <span>Camera</span>
          </button>
          <button
            :class="['scan-mode-btn', { active: scanMode === 'manual' }]"
            @click="scanMode = 'manual'"
            type="button"
            aria-label="Manual entry mode"
          >
            <!-- pencil icon -->
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            <span>Manual</span>
          </button>
        </div>
      </div>

      <!-- Scanner Gun Panel -->
      <div v-if="scanMode === 'gun'" class="scan-panel">
        <div class="form-group">
          <label class="form-label">Barcode input</label>
          <input
            id="scannerGunInput"
            ref="scannerGunInput"
            v-model="scannerBarcode"
            type="text"
            placeholder="Focus here and scan with barcode gun…"
            @keypress.enter="handleScannerGunInput"
            autocomplete="off"
            class="form-input scanner-input"
          />
        </div>

        <div class="scan-meta-row">
          <div class="form-group scan-location-group">
            <label class="form-label">Location</label>
            <div class="filter-chip-row">
              <button
                v-for="loc in locations"
                :key="loc.value"
                :class="['btn-chip', { active: scannerLocation === loc.value }]"
                @click="scannerLocation = loc.value"
                type="button"
              >{{ loc.label }}</button>
            </div>
          </div>

          <div class="form-group scan-qty-group">
            <label class="form-label">Qty</label>
            <div class="quantity-control">
              <button class="btn-qty" @click="scannerQuantity = Math.max(0.1, scannerQuantity - 1)" type="button">−</button>
              <input v-model.number="scannerQuantity" type="number" min="0.1" step="0.1" class="qty-input" />
              <button class="btn-qty" @click="scannerQuantity += 1" type="button">+</button>
            </div>
          </div>
        </div>

        <div v-if="scannerLoading" class="loading-inline">
          <div class="spinner spinner-sm"></div>
          <span>Processing barcode…</span>
        </div>

        <div v-if="scannerResults.length > 0" class="results">
          <div v-for="(result, index) in scannerResults" :key="index" :class="['result-item', `result-${result.type}`]">
            {{ result.message }}
          </div>
        </div>
      </div>

      <!-- Camera Scan Panel -->
      <div v-if="scanMode === 'camera'" class="scan-panel">
        <div class="upload-area" @click="triggerBarcodeInput">
          <svg class="upload-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/>
            <circle cx="12" cy="13" r="4"/>
          </svg>
          <div class="upload-text">Tap to photograph a barcode</div>
          <div class="upload-hint">JPG, PNG — takes a snapshot via your camera</div>
        </div>
        <input
          ref="barcodeFileInput"
          type="file"
          accept="image/*"
          capture="environment"
          style="display: none"
          @change="handleBarcodeImageSelect"
        />

        <div class="scan-meta-row" style="margin-top: var(--spacing-md)">
          <div class="form-group scan-location-group">
            <label class="form-label">Location</label>
            <div class="filter-chip-row">
              <button
                v-for="loc in locations"
                :key="loc.value"
                :class="['btn-chip', { active: barcodeLocation === loc.value }]"
                @click="barcodeLocation = loc.value"
                type="button"
              >{{ loc.label }}</button>
            </div>
          </div>

          <div class="form-group scan-qty-group">
            <label class="form-label">Qty</label>
            <div class="quantity-control">
              <button class="btn-qty" @click="barcodeQuantity = Math.max(0.1, barcodeQuantity - 1)" type="button">−</button>
              <input v-model.number="barcodeQuantity" type="number" min="0.1" step="0.1" class="qty-input" />
              <button class="btn-qty" @click="barcodeQuantity += 1" type="button">+</button>
            </div>
          </div>
        </div>

        <div v-if="barcodeLoading" class="loading-inline">
          <div class="spinner spinner-sm"></div>
          <span>Scanning barcode…</span>
        </div>

        <div v-if="barcodeResults.length > 0" class="results">
          <div v-for="(result, index) in barcodeResults" :key="index" :class="['result-item', `result-${result.type}`]">
            {{ result.message }}
          </div>
        </div>
      </div>

      <!-- Manual Add Panel -->
      <div v-if="scanMode === 'manual'" class="scan-panel">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Product Name *</label>
            <input v-model="manualForm.name" type="text" placeholder="e.g., Organic Milk" required class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label">Brand</label>
            <input v-model="manualForm.brand" type="text" placeholder="e.g., Horizon" class="form-input" />
          </div>
        </div>

        <div class="scan-meta-row">
          <div class="form-group scan-location-group">
            <label class="form-label">Location *</label>
            <div class="filter-chip-row">
              <button
                v-for="loc in locations"
                :key="loc.value"
                :class="['btn-chip', { active: manualForm.location === loc.value }]"
                @click="manualForm.location = loc.value"
                type="button"
              >{{ loc.label }}</button>
            </div>
          </div>

          <div class="form-group scan-qty-group">
            <label class="form-label">Qty</label>
            <div class="quantity-control">
              <button class="btn-qty" @click="manualForm.quantity = Math.max(0.1, manualForm.quantity - 1)" type="button">−</button>
              <input v-model.number="manualForm.quantity" type="number" min="0.1" step="0.1" required class="qty-input" />
              <button class="btn-qty" @click="manualForm.quantity += 1" type="button">+</button>
            </div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Unit</label>
            <div class="filter-chip-row">
              <button
                v-for="unit in units"
                :key="unit.value"
                :class="['btn-chip', { active: manualForm.unit === unit.value }]"
                @click="manualForm.unit = unit.value"
                type="button"
              >{{ unit.label }}</button>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Expiration Date</label>
            <input v-model="manualForm.expirationDate" type="date" class="form-input" />
          </div>
        </div>

        <button @click="addManualItem" class="btn btn-primary w-full" :disabled="manualLoading">
          {{ manualLoading ? 'Adding…' : 'Add to Pantry' }}
        </button>
      </div>
    </div>

    <!-- Inventory Section -->
    <div class="inventory-section">
      <!-- Filter chips -->
      <div class="inventory-header">
        <h2 class="section-title">Pantry</h2>
      </div>

      <div class="filter-row">
        <div class="filter-chip-row">
          <button
            :class="['btn-chip', { active: locationFilter === 'all' }]"
            @click="locationFilter = 'all'; onFilterChange()"
            type="button"
          >All</button>
          <button
            v-for="loc in locations"
            :key="loc.value"
            :class="['btn-chip', { active: locationFilter === loc.value }]"
            @click="locationFilter = loc.value; onFilterChange()"
            type="button"
          >{{ loc.label }}</button>
        </div>

        <div class="filter-chip-row status-filter-row">
          <button
            v-for="status in statuses"
            :key="status.value"
            :class="['btn-chip', { active: statusFilter === status.value }]"
            @click="statusFilter = status.value; onFilterChange()"
            type="button"
          >{{ status.label }}</button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading && items.length === 0" class="empty-state">
        <div class="spinner"></div>
        <p class="text-muted text-sm" style="margin-top: var(--spacing-md)">Loading pantry…</p>
      </div>

      <!-- Empty State: clean slate (no items at all) -->
      <div v-else-if="!loading && filteredItems.length === 0 && store.items.length === 0" class="empty-state">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
          <rect x="6" y="10" width="36" height="6" rx="2"/>
          <rect x="6" y="21" width="36" height="6" rx="2"/>
          <rect x="6" y="32" width="36" height="6" rx="2"/>
        </svg>
        <p class="text-secondary">Clean slate.</p>
        <p class="text-muted text-sm">Your pantry is ready for anything — scan a barcode or add an item above.</p>
      </div>

      <!-- Empty State: filter has no matches -->
      <div v-else-if="!loading && filteredItems.length === 0" class="empty-state">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
          <circle cx="20" cy="20" r="12"/>
          <line x1="29" y1="29" x2="42" y2="42"/>
        </svg>
        <p class="text-secondary">Nothing matches that filter.</p>
        <p class="text-muted text-sm">Try a different location or status.</p>
      </div>

      <!-- Inventory shelf list -->
      <div v-else class="inv-list">
        <div
          v-for="item in filteredItems"
          :key="item.id"
          class="inv-row"
          :class="[getItemClass(item), `inv-row-${item.location}`]"
        >
          <!-- Location dot -->
          <span :class="['loc-dot', `loc-dot-${item.location}`]"></span>

          <!-- Name -->
          <div class="inv-row-name">
            <span class="inv-name">{{ item.product_name || 'Unknown Product' }}</span>
            <span v-if="item.category" class="inv-category">{{ item.category }}</span>
          </div>

          <!-- Right side: qty + expiry + actions -->
          <div class="inv-row-right">
            <span class="inv-qty">{{ item.quantity }}<span class="inv-unit"> {{ item.unit }}</span></span>

            <span
              v-if="item.expiration_date"
              :class="['expiry-badge', getExpiryBadgeClass(item.expiration_date)]"
            >{{ formatDateShort(item.expiration_date) }}</span>

            <div class="inv-actions">
              <button @click="editItem(item)" class="btn-icon" aria-label="Edit">
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828L7 14.828 4 16l1.172-3L13.586 3.586z"/>
                </svg>
              </button>
              <button @click="markAsConsumed(item)" class="btn-icon btn-icon-success" aria-label="Mark consumed">
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                  <polyline points="4 10 8 14 16 6"/>
                </svg>
              </button>
              <button @click="confirmDelete(item)" class="btn-icon btn-icon-danger" aria-label="Delete">
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                  <polyline points="3 6 5 6 17 6"/>
                  <path d="M8 6V4h4v2"/>
                  <rect x="5" y="6" width="10" height="10" rx="1"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Export -->
    <div class="card export-card">
      <h2 class="section-title">Export</h2>
      <div class="flex gap-sm" style="margin-top: var(--spacing-sm)">
        <button @click="exportCSV" class="btn btn-secondary">Download CSV</button>
        <button @click="exportExcel" class="btn btn-secondary">Download Excel</button>
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

// Scan mode toggle
const scanMode = ref<'gun' | 'camera' | 'manual'>('gun')

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
  // Auto-focus scanner gun input — desktop only (avoids popping mobile keyboard)
  if (!('ontouchstart' in window)) {
    setTimeout(() => {
      scannerGunInput.value?.focus()
    }, 100)
  }
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
        message: `Added: ${item.product_name || 'item'} to ${scannerLocation.value}`,
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
        message: `Found: ${item.product_name || 'item'}`,
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

// Short date for compact row display
function formatDateShort(dateStr: string): string {
  const date = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(dateStr)
  expiry.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return `${Math.abs(diffDays)}d ago`
  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'tmrw'
  if (diffDays <= 14) return `${diffDays}d`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getExpiryBadgeClass(expiryStr: string): string {
  const today = new Date()
  const expiry = new Date(expiryStr)
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'expiry-expired'
  if (diffDays <= 3) return 'expiry-urgent'
  if (diffDays <= 7) return 'expiry-soon'
  return 'expiry-ok'
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
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-xs) 0 0;
  overflow-x: hidden;  /* prevent item rows from expanding page width on mobile */
}

/* ============================================
   STATS STRIP
   ============================================ */
.stats-strip {
  display: flex;
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.stat-strip-item {
  flex: 1;
  text-align: center;
  padding: var(--spacing-sm) var(--spacing-xs);
  border-right: 1px solid var(--color-border);
}

.stat-strip-item:last-child {
  border-right: none;
}

.stat-num {
  font-family: var(--font-mono);
  font-size: var(--font-size-xl);
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.1;
}

.stat-lbl {
  font-family: var(--font-body);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 2px;
}

/* ============================================
   SCAN CARD
   ============================================ */
.scan-card {
  padding: var(--spacing-md);
}

.scan-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
}

.scan-mode-toggle {
  display: flex;
  gap: 2px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 3px;
}

.scan-mode-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px var(--spacing-sm);
  border: none;
  border-radius: calc(var(--radius-lg) - 3px);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 600;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.scan-mode-btn svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.scan-mode-btn:hover {
  color: var(--color-text-secondary);
  transform: none;
  border-color: transparent;
}

.scan-mode-btn.active {
  background: var(--color-primary);
  color: #1e1c1a;
}

.scan-panel {
  /* spacing handled by parent gap */
}

.scan-meta-row {
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-start;
  flex-wrap: wrap;
}

.scan-location-group {
  flex: 1;
  min-width: 0;
  margin-bottom: 0;
}

.scan-qty-group {
  flex-shrink: 0;
  margin-bottom: 0;
}

/* ============================================
   UPLOAD AREA
   ============================================ */
.upload-area {
  border: 2px dashed var(--color-border-focus);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl) var(--spacing-lg);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-bg-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-elevated);
}

.upload-icon-svg {
  width: 40px;
  height: 40px;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-xs);
}

.upload-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.upload-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

/* ============================================
   FORMS
   ============================================ */
.scanner-input {
  font-family: var(--font-mono);
  font-size: var(--font-size-base);
  background: var(--color-bg-input);
}

.quantity-control {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.btn-qty {
  width: 34px;
  height: 34px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-qty:hover {
  background: var(--color-primary);
  color: #1e1c1a;
  border-color: var(--color-primary);
  transform: none;
}

.btn-qty:active {
  transform: scale(0.93);
}

.qty-input {
  width: 72px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  font-weight: 500;
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-input);
  color: var(--color-text-primary);
}

/* ============================================
   INVENTORY SHELF LIST
   ============================================ */
.inventory-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.inventory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
}

.filter-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.status-filter-row {
  padding-top: 0;
}

.inv-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.inv-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border-left: 3px solid var(--color-border);
  background: var(--color-bg-card);
  transition: background 0.15s ease;
  min-height: 52px;
  border-bottom: 1px solid var(--color-border);
}

.inv-row:last-child {
  border-bottom: none;
}

.inv-row:hover {
  background: var(--color-bg-elevated);
}

/* Urgency borders */
.inv-row.item-expiring-soon {
  border-left-color: var(--color-error) !important;
  animation: urgencyPulse 1.8s ease-in-out infinite;
}

.inv-row.item-expiring-warning {
  border-left-color: var(--color-warning) !important;
}

.inv-row.item-expired {
  opacity: 0.55;
  border-left-color: var(--color-text-muted) !important;
}

.inv-row-name {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.inv-name {
  font-family: var(--font-body);
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inv-category {
  font-family: var(--font-body);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inv-row-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-shrink: 0;
}

.inv-qty {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.inv-unit {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

/* Expiry badges */
.expiry-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}

.expiry-urgent {
  background: var(--color-error-bg);
  color: var(--color-error-light);
  border: 1px solid var(--color-error-border);
}

.expiry-soon {
  background: var(--color-warning-bg);
  color: var(--color-warning-light);
  border: 1px solid var(--color-warning-border);
}

.expiry-ok {
  background: var(--color-success-bg);
  color: var(--color-success-light);
  border: 1px solid var(--color-success-border);
}

.expiry-expired {
  background: rgba(100, 100, 100, 0.15);
  color: var(--color-text-muted);
  border: 1px solid rgba(100, 100, 100, 0.25);
  text-decoration: line-through;
}

/* Action icons inline */
.inv-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* ============================================
   EMPTY STATE
   ============================================ */
.empty-state {
  text-align: center;
  padding: var(--spacing-xl) var(--spacing-lg);
  color: var(--color-text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: var(--color-text-muted);
}

/* ============================================
   LOADING
   ============================================ */
.loading-inline {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  margin-top: var(--spacing-sm);
}

/* ============================================
   RESULTS
   ============================================ */
.results {
  margin-top: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.result-item {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.result-success {
  background: var(--color-success-bg);
  color: var(--color-success-light);
  border: 1px solid var(--color-success-border);
}

.result-error {
  background: var(--color-error-bg);
  color: var(--color-error-light);
  border: 1px solid var(--color-error-border);
}

.result-info {
  background: var(--color-info-bg);
  color: var(--color-info-light);
  border: 1px solid var(--color-info-border);
}

/* ============================================
   EXPORT CARD
   ============================================ */
.export-card {
  padding: var(--spacing-md);
}

/* ============================================
   URGENCY ANIMATION
   ============================================ */
@keyframes urgencyPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ============================================
   MOBILE RESPONSIVE
   ============================================ */
@media (max-width: 480px) {
  .scan-card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }

  /* Mode toggle fills the card width when header stacks */
  .scan-mode-toggle {
    width: 100%;
  }

  .scan-mode-btn {
    flex: 1;
    justify-content: center;
  }

  .scan-meta-row {
    flex-direction: column;
  }

  .scan-location-group,
  .scan-qty-group {
    width: 100%;
  }

  .inv-row {
    padding: var(--spacing-xs) var(--spacing-sm);
    min-height: 46px;
  }

  /* On very small screens, hide category line */
  .inv-category {
    display: none;
  }

  .stats-strip .stat-num {
    font-size: var(--font-size-lg);
  }

  .inv-actions {
    gap: 1px;
  }

  /* Prevent right section from blowing out row width on narrow screens */
  .inv-row-right {
    flex-shrink: 1;
    min-width: 0;
    gap: var(--spacing-xs);
  }

  /* Shrink action buttons slightly on mobile */
  .inv-row-right .btn-icon {
    width: 28px;
    height: 28px;
  }
}

/* Very narrow phones (360px and below): hide mode button labels, keep icons */
@media (max-width: 360px) {
  .scan-mode-btn span {
    display: none;
  }

  .scan-mode-btn svg {
    width: 16px;
    height: 16px;
  }
}

@media (min-width: 481px) and (max-width: 768px) {
  .scan-meta-row {
    flex-wrap: nowrap;
  }
}
</style>
