<template>
  <li class="shopping-row" :class="{ 'shopping-row--checked': item.checked }">
    <button class="check-btn" :aria-label="item.checked ? 'Uncheck' : 'Check'" @click="$emit('toggle')">
      <span class="check-box" :class="{ 'check-box--checked': item.checked }">
        {{ item.checked ? '✓' : '' }}
      </span>
    </button>

    <div class="row-body">
      <span class="row-name">{{ item.name }}</span>
      <span v-if="item.quantity || item.unit" class="row-qty">
        {{ item.quantity ? item.quantity : '' }}{{ item.unit ? ' ' + item.unit : '' }}
      </span>

      <!-- Affiliate links -->
      <div v-if="!item.checked && item.grocery_links.length > 0" class="grocery-links">
        <a
          v-for="link in item.grocery_links"
          :key="link.retailer"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          class="grocery-link"
          :title="'Buy on ' + link.retailer"
        >
          {{ retailerIcon(link.retailer) }} {{ link.retailer }}
        </a>
      </div>
    </div>

    <div class="row-actions">
      <button
        v-if="item.checked"
        class="btn btn-success btn-xs"
        title="Confirm purchase → add to pantry"
        @click="$emit('confirm')"
      >
        + Pantry
      </button>
      <button class="btn-icon" aria-label="Remove" @click="$emit('remove')">✕</button>
    </div>
  </li>
</template>

<script setup lang="ts">
import type { ShoppingItem } from '@/services/api'

defineProps<{ item: ShoppingItem }>()
defineEmits<{
  toggle: []
  remove: []
  confirm: []
}>()

function retailerIcon(retailer: string): string {
  if (retailer.toLowerCase().includes('amazon')) return '📦'
  if (retailer.toLowerCase().includes('instacart')) return '🛒'
  if (retailer.toLowerCase().includes('walmart')) return '🏪'
  return '🔗'
}
</script>

<style scoped>
.shopping-row {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-sm);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  transition: background 0.15s;
}

.shopping-row:hover {
  background: var(--color-bg-hover);
}

.shopping-row--checked .row-name {
  text-decoration: line-through;
  color: var(--color-text-secondary);
}

.check-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  flex-shrink: 0;
  margin-top: 2px;
}

.check-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  transition: background 0.15s, border-color 0.15s;
}

.check-box--checked {
  background: var(--color-success);
  border-color: var(--color-success);
  color: white;
}

.row-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-name {
  font-size: 0.95rem;
  color: var(--color-text-primary);
  word-break: break-word;
}

.row-qty {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
}

.grocery-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: 4px;
}

.grocery-link {
  font-size: 0.75rem;
  color: var(--color-primary);
  text-decoration: none;
  padding: 2px 6px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  white-space: nowrap;
  transition: background 0.15s;
}

.grocery-link:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
}

.row-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-shrink: 0;
}

.btn-xs {
  padding: 2px 8px;
  font-size: 0.75rem;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: 0.8rem;
  padding: 4px;
  border-radius: 4px;
  line-height: 1;
  transition: color 0.15s;
}

.btn-icon:hover {
  color: var(--color-error);
}
</style>
