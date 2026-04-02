<template>
  <div class="receipts-view">
    <!-- Upload Section -->
    <div class="card">
      <h2 class="section-title mb-md">Upload Receipt</h2>
      <div
        class="upload-area"
        @click="triggerFileInput"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <div class="upload-icon">🧾</div>
        <div class="upload-text">Click to upload or drag and drop</div>
        <div class="upload-hint">Supports JPG, PNG (max 10MB)</div>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        style="display: none"
        @change="handleFileSelect"
      />

      <div v-if="uploading" class="loading-inline mt-md">
        <div class="spinner"></div>
        <span class="text-sm text-muted">Processing receipt…</span>
      </div>

      <div v-if="uploadResults.length > 0" class="results">
        <div
          v-for="(result, index) in uploadResults"
          :key="index"
          :class="['result-item', `result-${result.type}`]"
        >
          {{ result.message }}
        </div>
      </div>
    </div>

    <!-- Receipts List Section -->
    <div class="card">
      <h2 class="section-title mb-md">Recent Receipts</h2>
      <div v-if="receipts.length === 0" class="text-center text-secondary p-lg">
        <p>No receipts yet. Upload one above!</p>
      </div>
      <div v-else>
        <!-- Stats Summary -->
        <div class="grid-stats">
          <div class="stat-card">
            <div class="stat-value">{{ receipts.length }}</div>
            <div class="stat-label">Total Receipts</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">${{ totalSpent.toFixed(2) }}</div>
            <div class="stat-label">Total Spent</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ totalItems }}</div>
            <div class="stat-label">Total Items</div>
          </div>
        </div>

        <!-- Receipts List -->
        <div class="receipts-list">
          <div
            v-for="receipt in receipts"
            :key="receipt.id"
            class="receipt-item"
          >
            <div class="receipt-info">
              <div class="receipt-merchant">
                {{ receipt.ocr_data?.merchant_name || 'Processing...' }}
              </div>
              <div class="receipt-details">
                <span v-if="receipt.ocr_data?.transaction_date">
                  📅 {{ formatDate(receipt.ocr_data.transaction_date) }}
                </span>
                <span v-if="receipt.ocr_data?.total">
                  💵 ${{ receipt.ocr_data.total }}
                </span>
                <span v-if="receipt.ocr_data?.items">
                  📦 {{ receipt.ocr_data.items.length }} items
                </span>
                <span :class="getStatusClass(receipt.status)">
                  {{ receipt.status }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="flex gap-sm mt-md">
          <button class="btn btn-secondary" @click="exportCSV">Download CSV</button>
          <button class="btn btn-secondary" @click="exportExcel">Download Excel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { receiptsAPI } from '../services/api'

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadResults = ref<Array<{ type: string; message: string }>>([])
const receipts = ref<any[]>([])

const totalSpent = computed(() => {
  return receipts.value.reduce((sum, receipt) => {
    const total = parseFloat(receipt.ocr_data?.total || 0)
    return sum + total
  }, 0)
})

const totalItems = computed(() => {
  return receipts.value.reduce((sum, receipt) => {
    const items = receipt.ocr_data?.items?.length || 0
    return sum + items
  }, 0)
})

function triggerFileInput() {
  fileInput.value?.click()
}

function handleDrop(e: DragEvent) {
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    uploadFile(files[0]!)
  }
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    uploadFile(files[0]!)
  }
}

async function uploadFile(file: File) {
  uploading.value = true
  uploadResults.value = []

  try {
    const result = await receiptsAPI.upload(file)

    uploadResults.value.push({
      type: 'success',
      message: `Receipt uploaded! ID: ${result.id}`,
    })
    uploadResults.value.push({
      type: 'info',
      message: 'Processing in background...',
    })

    // Refresh receipts after a delay to allow background processing
    setTimeout(() => {
      loadReceipts()
    }, 3000)
  } catch (error: any) {
    uploadResults.value.push({
      type: 'error',
      message: `Upload failed: ${error.message}`,
    })
  } finally {
    uploading.value = false
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

async function loadReceipts() {
  try {
    const data = await receiptsAPI.listReceipts()
    // Fetch OCR data for each receipt
    receipts.value = await Promise.all(
      data.map(async (receipt: any) => {
        try {
          const ocrData = await receiptsAPI.getOCRData(receipt.id)
          return { ...receipt, ocr_data: ocrData }
        } catch {
          return { ...receipt, ocr_data: null }
        }
      })
    )
  } catch (error) {
    console.error('Failed to load receipts:', error)
  }
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString()
}

function getStatusClass(status: string): string {
  const statusMap: Record<string, string> = {
    completed: 'status-success',
    processing: 'status-processing',
    failed: 'status-error',
  }
  return statusMap[status] || 'status-default'
}

function exportCSV() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  window.open(`${apiUrl}/export/csv`, '_blank')
}

function exportExcel() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  window.open(`${apiUrl}/export/excel`, '_blank')
}

onMounted(() => {
  loadReceipts()
})
</script>

<style scoped>
.receipts-view {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.upload-area {
  border: 2px dashed var(--color-border-focus);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl) var(--spacing-lg);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-bg-secondary);
}

.upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-elevated);
}

.upload-icon {
  font-size: 40px;
  margin-bottom: var(--spacing-md);
  line-height: 1;
}

.upload-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.upload-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.loading-inline {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) 0;
}

.results {
  margin-top: var(--spacing-md);
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

/* Stat cards */
.stat-card {
  background: var(--color-bg-secondary);
  padding: var(--spacing-md);
  border-radius: var(--radius-lg);
  text-align: center;
  border: 1px solid var(--color-border);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: var(--font-size-2xl);
  font-weight: 500;
  color: var(--color-primary);
  margin-bottom: var(--spacing-xs);
  line-height: 1.1;
}

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.receipts-list {
  margin-top: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.receipt-item {
  background: var(--color-bg-secondary);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.receipt-info {
  flex: 1;
}

.receipt-merchant {
  font-weight: 600;
  font-size: var(--font-size-base);
  margin-bottom: var(--spacing-xs);
  color: var(--color-text-primary);
}

.receipt-details {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.status-success {
  color: var(--color-success);
  font-weight: 600;
}

.status-processing {
  color: var(--color-warning);
  font-weight: 600;
}

.status-error {
  color: var(--color-error);
  font-weight: 600;
}

.status-default {
  color: var(--color-text-secondary);
}

/* Mobile */
@media (max-width: 480px) {
  .stat-card {
    padding: var(--spacing-sm);
  }

  .receipt-item {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
  }

  .receipt-info {
    width: 100%;
  }

  .receipt-details {
    gap: var(--spacing-sm);
    font-size: var(--font-size-xs);
  }
}
</style>
