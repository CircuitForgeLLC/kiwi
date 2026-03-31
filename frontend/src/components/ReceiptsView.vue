<template>
  <div class="receipts-view">
    <!-- Upload Section -->
    <div class="card">
      <h2>📸 Upload Receipt</h2>
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

      <div v-if="uploading" class="loading">
        <div class="spinner"></div>
        <p>Processing receipt...</p>
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
      <h2>📋 Recent Receipts</h2>
      <div v-if="receipts.length === 0" style="text-align: center; color: var(--color-text-secondary)">
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

        <div style="margin-top: 20px">
          <button class="button" @click="exportCSV">📊 Download CSV</button>
          <button class="button" @click="exportExcel">📈 Download Excel</button>
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
  gap: 20px;
}

.card {
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  padding: 30px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.card h2 {
  margin-bottom: 20px;
  color: var(--color-text-primary);
}

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

.loading {
  text-align: center;
  padding: 20px;
  margin-top: 20px;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  width: 40px;
  height: 40px;
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

/* Using .grid-stats from theme.css */

.stat-card {
  background: var(--color-bg-secondary);
  padding: 20px;
  border-radius: var(--radius-lg);
  text-align: center;
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

.button {
  background: var(--gradient-primary);
  color: white;
  border: none;
  padding: 12px 30px;
  font-size: var(--font-size-base);
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

.receipts-list {
  margin-top: 20px;
}

.receipt-item {
  background: var(--color-bg-secondary);
  padding: 15px;
  border-radius: var(--radius-md);
  margin-bottom: 10px;
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
  margin-bottom: 5px;
  color: var(--color-text-primary);
}

.receipt-details {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  display: flex;
  gap: 15px;
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

/* Mobile Responsive - Handled by theme.css
   Component-specific overrides only below */

@media (max-width: 480px) {
  .stat-card {
    padding: 15px;
  }

  /* Receipt items stack content vertically */
  .receipt-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
  }

  .receipt-info {
    width: 100%;
  }

  .receipt-details {
    gap: 10px;
    font-size: var(--font-size-xs);
  }

  /* Buttons full width on mobile */
  .button {
    width: 100%;
    margin-right: 0;
    margin-bottom: 10px;
  }
}
</style>
