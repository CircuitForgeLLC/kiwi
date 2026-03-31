<template>
  <div id="app">
    <header class="app-header">
      <div class="container">
        <h1>🥝 Kiwi</h1>
        <p class="tagline">Smart Pantry Tracking & Recipe Suggestions</p>
      </div>
    </header>

    <main class="app-main">
      <div class="container">
        <!-- Tabs -->
        <div class="tabs">
          <button
            :class="['tab', { active: currentTab === 'inventory' }]"
            @click="switchTab('inventory')"
          >
            🏪 Inventory
          </button>
          <button
            :class="['tab', { active: currentTab === 'receipts' }]"
            @click="switchTab('receipts')"
          >
            🧾 Receipts
          </button>
        </div>

        <!-- Tab Content -->
        <div v-show="currentTab === 'inventory'" class="tab-content">
          <InventoryList />
        </div>

        <div v-show="currentTab === 'receipts'" class="tab-content">
          <ReceiptsView />
        </div>
      </div>
    </main>

    <footer class="app-footer">
      <div class="container">
        <p>&copy; 2026 CircuitForge LLC</p>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import InventoryList from './components/InventoryList.vue'
import ReceiptsView from './components/ReceiptsView.vue'

const currentTab = ref<'inventory' | 'receipts'>('inventory')

function switchTab(tab: 'inventory' | 'receipts') {
  currentTab.value = tab
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
}

.app-header {
  background: var(--gradient-primary);
  color: white;
  padding: var(--spacing-xl) 0;
  box-shadow: var(--shadow-md);
}

.app-header h1 {
  font-size: 32px;
  margin-bottom: 5px;
}

.app-header .tagline {
  font-size: 16px;
  opacity: 0.9;
}

.app-main {
  flex: 1;
  padding: 20px 0;
}

.app-footer {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  padding: var(--spacing-lg) 0;
  text-align: center;
  margin-top: var(--spacing-xl);
  border-top: 1px solid var(--color-border);
}

.app-footer p {
  font-size: var(--font-size-sm);
  opacity: 0.8;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.tab {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: none;
  padding: 15px 30px;
  font-size: 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.3);
}

.tab.active {
  background: var(--color-bg-card);
  color: var(--color-primary);
  font-weight: 600;
}

.tab-content {
  animation: fadeIn 0.3s;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Mobile Responsive Breakpoints */
@media (max-width: 480px) {
  .container {
    padding: 0 12px;
  }

  .app-header h1 {
    font-size: 24px;
  }

  .app-header .tagline {
    font-size: 14px;
  }

  .tabs {
    gap: 8px;
  }

  .tab {
    padding: 12px 20px;
    font-size: 14px;
    flex: 1;
  }
}

@media (min-width: 481px) and (max-width: 768px) {
  .container {
    padding: 0 16px;
  }

  .app-header h1 {
    font-size: 28px;
  }

  .tab {
    padding: 14px 25px;
  }
}
</style>
