<template>
  <div class="shopping-view">
    <!-- Header -->
    <div class="shopping-header">
      <div class="shopping-title-row">
        <h2 class="shopping-title">Shopping List</h2>
        <span v-if="store.totalCount > 0" class="shopping-count badge">
          {{ store.checkedCount }}/{{ store.totalCount }}
        </span>
      </div>
      <div class="shopping-actions">
        <button class="btn btn-secondary btn-sm" @click="showAddForm = !showAddForm">
          + Add item
        </button>
        <button
          v-if="store.checkedCount > 0"
          class="btn btn-secondary btn-sm"
          @click="handleClearChecked"
        >
          Clear checked ({{ store.checkedCount }})
        </button>
      </div>
    </div>

    <!-- Add item form -->
    <div v-if="showAddForm" class="card card-sm add-form">
      <div class="add-form-fields">
        <input
          v-model="newItem.name"
          class="input"
          placeholder="Item name"
          @keyup.enter="handleAdd"
          ref="nameInput"
        />
        <input
          v-model="newItem.quantity"
          class="input input-sm"
          type="number"
          placeholder="Qty"
          min="0"
          step="0.1"
        />
        <input
          v-model="newItem.unit"
          class="input input-sm"
          placeholder="Unit"
        />
      </div>
      <div class="add-form-footer">
        <button class="btn btn-primary btn-sm" :disabled="!newItem.name.trim()" @click="handleAdd">
          Add
        </button>
        <button class="btn btn-secondary btn-sm" @click="showAddForm = false">
          Cancel
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="shopping-empty">Loading…</div>

    <!-- Error -->
    <div v-else-if="store.error" class="card card-error shopping-error">
      {{ store.error }}
    </div>

    <!-- Empty state -->
    <div v-else-if="store.totalCount === 0" class="shopping-empty">
      <div class="empty-icon">🛒</div>
      <p class="empty-title">Your list is empty</p>
      <p class="empty-hint">Add items manually or use "Add to list" from any recipe.</p>
    </div>

    <!-- Items -->
    <div v-else class="shopping-sections">
      <!-- Unchecked -->
      <ul v-if="store.uncheckedItems.length > 0" class="shopping-list">
        <ShoppingItemRow
          v-for="item in store.uncheckedItems"
          :key="item.id"
          :item="item"
          @toggle="store.toggleChecked(item.id)"
          @remove="store.removeItem(item.id)"
          @confirm="openConfirmModal(item)"
        />
      </ul>

      <!-- Checked / in-cart -->
      <div v-if="store.checkedItems.length > 0" class="checked-section">
        <button class="checked-toggle" @click="showChecked = !showChecked">
          {{ showChecked ? '▾' : '▸' }} In cart ({{ store.checkedCount }})
        </button>
        <ul v-if="showChecked" class="shopping-list shopping-list--checked">
          <ShoppingItemRow
            v-for="item in store.checkedItems"
            :key="item.id"
            :item="item"
            @toggle="store.toggleChecked(item.id)"
            @remove="store.removeItem(item.id)"
            @confirm="openConfirmModal(item)"
          />
        </ul>
      </div>
    </div>

    <!-- Confirm purchase modal -->
    <div v-if="confirmItem" class="modal-backdrop" @click.self="confirmItem = null">
      <div class="modal card">
        <h3 class="modal-title">Confirm purchase</h3>
        <p class="modal-body">
          Add <strong>{{ confirmItem.name }}</strong> to your pantry?
        </p>
        <div class="modal-fields">
          <label class="field-label">Location</label>
          <select v-model="confirmLocation" class="input">
            <option value="pantry">Pantry</option>
            <option value="fridge">Fridge</option>
            <option value="freezer">Freezer</option>
          </select>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" @click="handleConfirmPurchase">
            Add to pantry
          </button>
          <button class="btn btn-secondary" @click="confirmItem = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useShoppingStore } from '@/stores/shopping'
import type { ShoppingItem } from '@/services/api'
import ShoppingItemRow from './ShoppingItemRow.vue'

const store = useShoppingStore()

const showAddForm = ref(false)
const showChecked = ref(true)
const nameInput = ref<HTMLInputElement | null>(null)

const newItem = ref({ name: '', quantity: undefined as number | undefined, unit: '' })

const confirmItem = ref<ShoppingItem | null>(null)
const confirmLocation = ref('pantry')

onMounted(() => store.fetchItems())

async function handleAdd() {
  if (!newItem.value.name.trim()) return
  await store.addItem({
    name: newItem.value.name.trim(),
    quantity: newItem.value.quantity || undefined,
    unit: newItem.value.unit.trim() || undefined,
  })
  newItem.value = { name: '', quantity: undefined, unit: '' }
  await nextTick()
  nameInput.value?.focus()
}

async function handleClearChecked() {
  if (!confirm(`Remove ${store.checkedCount} checked items?`)) return
  await store.clearChecked()
}

function openConfirmModal(item: ShoppingItem) {
  confirmItem.value = item
  confirmLocation.value = 'pantry'
}

async function handleConfirmPurchase() {
  if (!confirmItem.value) return
  await store.confirmPurchase(confirmItem.value.id, confirmLocation.value)
  confirmItem.value = null
}
</script>

<style scoped>
.shopping-view {
  padding: var(--spacing-md);
  max-width: 680px;
  margin: 0 auto;
}

.shopping-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.shopping-title-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.shopping-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.shopping-count {
  background: var(--color-primary);
  color: #1e1c1a;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 99px;
  font-weight: 600;
}

.shopping-actions {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 0.85rem;
}

.add-form {
  margin-bottom: var(--spacing-md);
}

.add-form-fields {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-sm);
}

.add-form-fields .input {
  flex: 1;
  min-width: 120px;
}

.input-sm {
  max-width: 100px;
}

.add-form-footer {
  display: flex;
  gap: var(--spacing-xs);
}

.shopping-empty {
  text-align: center;
  padding: var(--spacing-xl) var(--spacing-md);
  color: var(--color-text-secondary);
}

.empty-icon {
  font-size: 2.5rem;
  margin-bottom: var(--spacing-sm);
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 var(--spacing-xs);
  color: var(--color-text-primary);
}

.empty-hint {
  font-size: 0.875rem;
  margin: 0;
}

.shopping-error {
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.shopping-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.checked-section {
  margin-top: var(--spacing-sm);
}

.checked-toggle {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
  padding: var(--spacing-xs) 0;
  margin-bottom: var(--spacing-xs);
}

.shopping-list--checked {
  opacity: 0.65;
}

/* Confirm modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--spacing-md);
}

.modal {
  width: 100%;
  max-width: 400px;
  padding: var(--spacing-lg);
}

.modal-title {
  margin: 0 0 var(--spacing-sm);
  font-size: 1.1rem;
}

.modal-body {
  margin: 0 0 var(--spacing-md);
  color: var(--color-text-secondary);
}

.modal-fields {
  margin-bottom: var(--spacing-md);
}

.field-label {
  display: block;
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-xs);
}

.modal-footer {
  display: flex;
  gap: var(--spacing-sm);
}

@media (max-width: 480px) {
  .shopping-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
