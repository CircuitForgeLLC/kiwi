<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h2>Edit Inventory Item</h2>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </div>

      <form @submit.prevent="handleSubmit" class="edit-form">
        <div class="form-group">
          <label>Product</label>
          <div class="product-info">
            <strong>{{ item.product.name }}</strong>
            <span v-if="item.product.brand" class="brand">({{ item.product.brand }})</span>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="quantity">Quantity *</label>
            <input
              id="quantity"
              v-model.number="formData.quantity"
              type="number"
              step="0.1"
              min="0"
              required
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label for="unit">Unit</label>
            <select id="unit" v-model="formData.unit" class="form-input">
              <option value="count">Count</option>
              <option value="kg">Kilograms</option>
              <option value="g">Grams</option>
              <option value="lb">Pounds</option>
              <option value="oz">Ounces</option>
              <option value="l">Liters</option>
              <option value="ml">Milliliters</option>
              <option value="gal">Gallons</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="location">Location *</label>
            <select id="location" v-model="formData.location" required class="form-input">
              <option value="fridge">Fridge</option>
              <option value="freezer">Freezer</option>
              <option value="pantry">Pantry</option>
              <option value="cabinet">Cabinet</option>
            </select>
          </div>

          <div class="form-group">
            <label for="sublocation">Sublocation</label>
            <input
              id="sublocation"
              v-model="formData.sublocation"
              type="text"
              placeholder="e.g., Top Shelf"
              class="form-input"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="purchase_date">Purchase Date</label>
            <input
              id="purchase_date"
              v-model="formData.purchase_date"
              type="date"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label for="expiration_date">Expiration Date</label>
            <input
              id="expiration_date"
              v-model="formData.expiration_date"
              type="date"
              class="form-input"
              :class="getExpiryInputClass()"
            />
            <small v-if="formData.expiration_date" class="expiry-hint">
              {{ getExpiryHint() }}
            </small>
          </div>
        </div>

        <div class="form-group">
          <label for="status">Status</label>
          <select id="status" v-model="formData.status" class="form-input">
            <option value="available">Available</option>
            <option value="consumed">Consumed</option>
            <option value="expired">Expired</option>
            <option value="discarded">Discarded</option>
          </select>
        </div>

        <div class="form-group">
          <label for="notes">Notes</label>
          <textarea
            id="notes"
            v-model="formData.notes"
            rows="3"
            placeholder="Add any notes about this item..."
            class="form-input"
          ></textarea>
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <div class="form-actions">
          <button type="button" @click="$emit('close')" class="btn-cancel">
            Cancel
          </button>
          <button type="submit" class="btn-save" :disabled="saving">
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useInventoryStore } from '../stores/inventory'
import type { InventoryItem } from '../services/api'

const props = defineProps<{
  item: InventoryItem
}>()

const emit = defineEmits<{
  close: []
  save: []
}>()

const store = useInventoryStore()

const saving = ref(false)
const error = ref<string | null>(null)

// Initialize form data
const formData = reactive({
  quantity: props.item.quantity,
  unit: props.item.unit,
  location: props.item.location,
  sublocation: props.item.sublocation || '',
  purchase_date: props.item.purchase_date || '',
  expiration_date: props.item.expiration_date || '',
  status: props.item.status,
  notes: props.item.notes || '',
})

async function handleSubmit() {
  saving.value = true
  error.value = null

  try {
    // Prepare update object (only include changed fields)
    const update: any = {}

    if (formData.quantity !== props.item.quantity) update.quantity = formData.quantity
    if (formData.unit !== props.item.unit) update.unit = formData.unit
    if (formData.location !== props.item.location) update.location = formData.location
    if (formData.sublocation !== props.item.sublocation) update.sublocation = formData.sublocation || null
    if (formData.purchase_date !== props.item.purchase_date) update.purchase_date = formData.purchase_date || null
    if (formData.expiration_date !== props.item.expiration_date) update.expiration_date = formData.expiration_date || null
    if (formData.status !== props.item.status) update.status = formData.status
    if (formData.notes !== props.item.notes) update.notes = formData.notes || null

    await store.updateItem(props.item.id, update)

    emit('save')
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to update item'
  } finally {
    saving.value = false
  }
}

function getExpiryInputClass(): string {
  if (!formData.expiration_date) return ''

  const today = new Date()
  const expiry = new Date(formData.expiration_date)
  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'expiry-expired'
  if (diffDays <= 3) return 'expiry-soon'
  if (diffDays <= 7) return 'expiry-warning'
  return 'expiry-good'
}

function getExpiryHint(): string {
  if (!formData.expiration_date) return ''

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(formData.expiration_date)
  expiry.setHours(0, 0, 0, 0)

  const diffDays = Math.ceil((expiry.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return `⚠️ Expired ${Math.abs(diffDays)} days ago`
  if (diffDays === 0) return '⚠️ Expires today!'
  if (diffDays === 1) return '⚠️ Expires tomorrow'
  if (diffDays <= 3) return `⚠️ Expires in ${diffDays} days (use soon!)`
  if (diffDays <= 7) return `Expires in ${diffDays} days`
  return `Expires in ${diffDays} days`
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h2 {
  margin: 0;
  font-size: var(--font-size-xl);
}

.close-btn {
  background: none;
  border: none;
  font-size: 32px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  line-height: 1;
}

.close-btn:hover {
  color: var(--color-text-primary);
}

.edit-form {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

/* Using .form-row from theme.css */

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.form-input {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}

.form-input:focus {
  outline: none;
  border-color: #2196F3;
  box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

.form-input.expiry-expired {
  border-color: #f44336;
}

.form-input.expiry-soon {
  border-color: #ff5722;
}

.form-input.expiry-warning {
  border-color: #ff9800;
}

.form-input.expiry-good {
  border-color: #4CAF50;
}

textarea.form-input {
  resize: vertical;
  font-family: inherit;
}

.product-info {
  padding: 10px;
  background: #f5f5f5;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}

.product-info .brand {
  color: var(--color-text-secondary);
  margin-left: 8px;
}

.expiry-hint {
  display: block;
  margin-top: 5px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.error-message {
  background: #ffebee;
  color: #c62828;
  padding: 12px;
  border-radius: var(--radius-sm);
  margin-bottom: 15px;
  font-size: var(--font-size-sm);
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 25px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.btn-cancel,
.btn-save {
  padding: 10px 24px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-cancel {
  background: #f5f5f5;
  color: var(--color-text-primary);
}

.btn-cancel:hover {
  background: #e0e0e0;
}

.btn-save {
  background: var(--color-success);
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: var(--color-success-dark);
}

.btn-save:disabled {
  background: var(--color-text-muted);
  cursor: not-allowed;
}

/* Mobile Responsive - Form row handled by theme.css
   Component-specific overrides only below */

@media (max-width: 480px) {
  .modal-content {
    width: 95%;
    max-height: 95vh;
  }

  .modal-header {
    padding: 15px;
  }

  .modal-header h2 {
    font-size: var(--font-size-lg);
  }

  .edit-form {
    padding: 15px;
  }

  .form-group {
    margin-bottom: 15px;
  }

  /* Form actions stack on very small screens */
  .form-actions {
    flex-direction: column-reverse;
    gap: 10px;
  }

  .btn-cancel,
  .btn-save {
    width: 100%;
    padding: 12px;
  }
}

@media (min-width: 481px) and (max-width: 768px) {
  .modal-content {
    width: 92%;
  }

  .modal-header {
    padding: 18px;
  }

  .edit-form {
    padding: 18px;
  }
}
</style>
