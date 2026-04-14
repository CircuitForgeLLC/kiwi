<!-- frontend/src/components/ShoppingListPanel.vue -->
<template>
  <div class="shopping-list-panel">
    <div v-if="loading" class="panel-loading">Loading shopping list...</div>

    <template v-else-if="shoppingList">
      <!-- Disclosure banner -->
      <div v-if="shoppingList.disclosure && shoppingList.gap_items.length" class="disclosure-banner">
        {{ shoppingList.disclosure }}
      </div>

      <!-- Gap items (need to buy) -->
      <section v-if="shoppingList.gap_items.length" aria-label="Items to buy">
        <h3 class="section-heading">To buy ({{ shoppingList.gap_items.length }})</h3>
        <ul class="item-list" role="list">
          <li v-for="item in shoppingList.gap_items" :key="item.ingredient_name" class="gap-item">
            <label class="item-row">
              <input type="checkbox" class="item-check" :aria-label="`Mark ${item.ingredient_name} as grabbed`" />
              <span class="item-name">{{ item.ingredient_name }}</span>
              <span v-if="item.needed_raw" class="item-qty gap">{{ item.needed_raw }}</span>
            </label>
            <div v-if="item.retailer_links.length" class="retailer-links">
              <a
                v-for="link in item.retailer_links"
                :key="link.retailer"
                :href="link.url"
                target="_blank"
                rel="noopener noreferrer sponsored"
                class="retailer-link"
                :aria-label="`Buy ${item.ingredient_name} at ${link.label}`"
              >{{ link.label }}</a>
            </div>
          </li>
        </ul>
      </section>

      <!-- Covered items (already in pantry) -->
      <section v-if="shoppingList.covered_items.length" aria-label="Items already in pantry">
        <h3 class="section-heading covered-heading">In your pantry ({{ shoppingList.covered_items.length }})</h3>
        <ul class="item-list covered-list" role="list">
          <li v-for="item in shoppingList.covered_items" :key="item.ingredient_name" class="covered-item">
            <span class="check-icon" aria-hidden="true">✓</span>
            <span class="item-name">{{ item.ingredient_name }}</span>
            <span v-if="item.have_quantity" class="item-qty">{{ item.have_quantity }} {{ item.have_unit }}</span>
          </li>
        </ul>
      </section>

      <div v-if="!shoppingList.gap_items.length && !shoppingList.covered_items.length" class="empty-state">
        No ingredients yet — add some recipes to your plan first.
      </div>
    </template>

    <div v-else class="empty-state">
      <button class="load-btn" @click="$emit('load')">Generate shopping list</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMealPlanStore } from '../stores/mealPlan'
import { storeToRefs } from 'pinia'

defineEmits<{ (e: 'load'): void }>()

const store = useMealPlanStore()
const { shoppingList, shoppingListLoading: loading } = storeToRefs(store)
</script>

<style scoped>
.shopping-list-panel { display: flex; flex-direction: column; gap: 1rem; }
.panel-loading { font-size: 0.85rem; opacity: 0.6; padding: 1rem 0; }

.disclosure-banner {
  font-size: 0.72rem; opacity: 0.55; padding: 0.4rem 0.6rem;
  background: var(--color-surface-2); border-radius: 6px;
}

.section-heading { font-size: 0.8rem; font-weight: 600; margin: 0 0 0.5rem; }
.covered-heading { opacity: 0.6; }

.item-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }

.gap-item { display: flex; flex-direction: column; gap: 3px; padding: 6px 0; border-bottom: 1px solid var(--color-border); }
.gap-item:last-child { border-bottom: none; }
.item-row { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
.item-check { width: 16px; height: 16px; flex-shrink: 0; }
.item-name { flex: 1; font-size: 0.85rem; }
.item-qty { font-size: 0.75rem; opacity: 0.7; }
.item-qty.gap { color: var(--color-warning, #e88); opacity: 1; }

.retailer-links { display: flex; flex-wrap: wrap; gap: 4px; padding-left: 1.5rem; }
.retailer-link {
  font-size: 0.68rem; padding: 2px 8px; border-radius: 20px;
  background: var(--color-surface-2); color: var(--color-accent);
  text-decoration: none; border: 1px solid var(--color-border);
  transition: background 0.15s;
}
.retailer-link:hover { background: var(--color-accent-subtle); }
.retailer-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

.covered-item { display: flex; align-items: center; gap: 0.5rem; padding: 4px 0; opacity: 0.6; font-size: 0.82rem; }
.check-icon { color: var(--color-success); font-size: 0.75rem; }

.empty-state { font-size: 0.85rem; opacity: 0.55; padding: 1rem 0; text-align: center; }
.load-btn {
  font-size: 0.85rem; padding: 0.5rem 1.2rem;
  background: var(--color-accent-subtle); color: var(--color-accent);
  border: 1px solid var(--color-accent); border-radius: 20px; cursor: pointer;
}
.load-btn:hover { background: var(--color-accent); color: white; }
</style>
