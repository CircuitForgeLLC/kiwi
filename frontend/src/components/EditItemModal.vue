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
            <strong>{{ item.product_name || 'Unknown Product' }}</strong>
            <span v-if="item.category" class="brand">{{ item.category }}</span>
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
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--color-border);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg) var(--spacing-lg) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  margin: 0;
  font-size: var(--font-size-xl);
  font-family: var(--font-display);
  font-style: italic;
  color: var(--color-text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  transition: color 0.18s, background 0.18s;
}

.close-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-elevated);
}

.edit-form {
  padding: var(--spacing-lg);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

/* Using .form-row from theme.css */

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.form-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  background: var(--color-bg-input);
  color: var(--color-text-primary);
  font-family: var(--font-body);
  transition: border-color 0.18s, box-shadow 0.18s;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-warning-bg);
}

.form-input.expiry-expired {
  border-color: var(--color-error);
}

.form-input.expiry-soon {
  border-color: var(--color-error-light);
}

.form-input.expiry-warning {
  border-color: var(--color-warning);
}

.form-input.expiry-good {
  border-color: var(--color-success);
}

textarea.form-input {
  resize: vertical;
  font-family: var(--font-body);
}

.product-info {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  border: 1px solid var(--color-border);
}

.product-info .brand {
  color: var(--color-text-secondary);
  margin-left: var(--spacing-sm);
}

.expiry-hint {
  display: block;
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.error-message {
  background: var(--color-error-bg);
  color: var(--color-error-light);
  border: 1px solid var(--color-error-border);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-sm);
}

.form-actions {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border);
}

.btn-cancel,
.btn-save {
  padding: var(--spacing-sm) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.18s;
}

.btn-cancel {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.btn-cancel:hover {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.btn-save {
  background: var(--color-success);
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: var(--color-success-dark);
}

.btn-save:disabled {
  opacity: 0.45;
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
    padding: var(--spacing-md);
  }

  .modal-header h2 {
    font-size: var(--font-size-lg);
  }

  .edit-form {
    padding: var(--spacing-md);
  }

  .form-group {
    margin-bottom: var(--spacing-sm);
  }

  /* Form actions stack on very small screens */
  .form-actions {
    flex-direction: column-reverse;
    gap: var(--spacing-sm);
  }

  .btn-cancel,
  .btn-save {
    width: 100%;
    padding: var(--spacing-md);
    text-align: center;
  }
}

@media (min-width: 481px) and (max-width: 768px) {
  .modal-content {
    width: 92%;
  }
}
</style>
