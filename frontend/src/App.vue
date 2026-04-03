<template>
  <div id="app" :class="{ 'sidebar-collapsed': sidebarCollapsed }">

    <!-- Desktop sidebar (hidden on mobile) -->
    <aside class="sidebar" role="navigation" aria-label="Main navigation">
      <!-- Wordmark + collapse toggle -->
      <div class="sidebar-header">
        <span class="wordmark-kiwi" @click="onWordmarkClick" style="cursor:pointer">Kiwi</span>
        <button class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed" :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
      </div>

      <nav class="sidebar-nav">
        <button :class="['sidebar-item', { active: currentTab === 'inventory' }]" @click="switchTab('inventory')">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="4" width="18" height="4" rx="1"/>
            <rect x="3" y="11" width="18" height="4" rx="1"/>
            <rect x="3" y="18" width="18" height="3" rx="1"/>
          </svg>
          <span class="sidebar-label">Pantry</span>
        </button>

        <button :class="['sidebar-item', { active: currentTab === 'receipts' }]" @click="switchTab('receipts')">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 4v16l2-1.5 2 1.5 2-1.5 2 1.5 2-1.5 2 1.5 2-1.5V4"/>
            <line x1="8" y1="9" x2="16" y2="9"/>
            <line x1="8" y1="13" x2="14" y2="13"/>
          </svg>
          <span class="sidebar-label">Receipts</span>
        </button>

        <button :class="['sidebar-item', { active: currentTab === 'recipes' }]" @click="switchTab('recipes')">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2C9 2 7 5 7 8c0 2.5 1 4.5 3 5.5V20h4v-6.5c2-1 3-3 3-5.5 0-3-2-6-5-6z"/>
            <line x1="9" y1="12" x2="15" y2="12"/>
          </svg>
          <span class="sidebar-label">Recipes</span>
        </button>

        <button :class="['sidebar-item', { active: currentTab === 'settings' }]" @click="switchTab('settings')">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 1v3M12 20v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M1 12h3M20 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
          </svg>
          <span class="sidebar-label">Settings</span>
        </button>
      </nav>
    </aside>

    <!-- Main area: header + content -->
    <div class="app-body">
      <!-- Mobile-only header -->
      <header class="app-header">
        <div class="header-inner">
          <span class="wordmark-kiwi">Kiwi</span>
        </div>
      </header>

      <main class="app-main">
        <div class="container">
          <div v-show="currentTab === 'inventory'" class="tab-content fade-in">
            <InventoryList />
          </div>
          <div v-show="currentTab === 'receipts'" class="tab-content fade-in">
            <ReceiptsView />
          </div>
          <div v-show="currentTab === 'recipes'" class="tab-content fade-in">
            <RecipesView />
          </div>
          <div v-show="currentTab === 'settings'" class="tab-content fade-in">
            <SettingsView />
          </div>
        </div>
      </main>
    </div>

    <!-- Mobile bottom nav only -->
    <nav class="bottom-nav" role="navigation" aria-label="Main navigation">
      <button :class="['nav-item', { active: currentTab === 'inventory' }]" @click="switchTab('inventory')" aria-label="Pantry">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="4" rx="1"/>
          <rect x="3" y="11" width="18" height="4" rx="1"/>
          <rect x="3" y="18" width="18" height="3" rx="1"/>
        </svg>
        <span class="nav-label">Pantry</span>
      </button>
      <button :class="['nav-item', { active: currentTab === 'receipts' }]" @click="switchTab('receipts')" aria-label="Receipts">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 4v16l2-1.5 2 1.5 2-1.5 2 1.5 2-1.5 2 1.5 2-1.5V4"/>
          <line x1="8" y1="9" x2="16" y2="9"/>
          <line x1="8" y1="13" x2="14" y2="13"/>
        </svg>
        <span class="nav-label">Receipts</span>
      </button>
      <button :class="['nav-item', { active: currentTab === 'recipes' }]" @click="switchTab('recipes')" aria-label="Recipes">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2C9 2 7 5 7 8c0 2.5 1 4.5 3 5.5V20h4v-6.5c2-1 3-3 3-5.5 0-3-2-6-5-6z"/>
          <line x1="9" y1="12" x2="15" y2="12"/>
        </svg>
        <span class="nav-label">Recipes</span>
      </button>
      <button :class="['nav-item', { active: currentTab === 'settings' }]" @click="switchTab('settings')" aria-label="Settings">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 1v3M12 20v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M1 12h3M20 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
        </svg>
        <span class="nav-label">Settings</span>
      </button>
    </nav>

    <!-- Easter egg: Kiwi bird sprite — triggered by typing "kiwi" -->
    <Transition name="kiwi-fade">
      <div v-if="kiwiVisible" class="kiwi-bird-stage" aria-hidden="true">
        <div class="kiwi-bird" :class="kiwiDirection">
          <!-- Kiwi bird SVG — side profile, facing left by default (rtl walk) -->
          <svg class="kiwi-svg" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- Body — plump oval -->
            <ellipse cx="30" cy="38" rx="18" ry="15" fill="#8B6914" />
            <!-- Head -->
            <ellipse cx="46" cy="26" rx="10" ry="9" fill="#6B4F10" />
            <!-- Long beak -->
            <path d="M54 25 Q66 24 70 25 Q66 27 54 27Z" fill="#C8A96E" />
            <!-- Eye -->
            <circle cx="49" cy="23" r="2" fill="#1a1a1a" />
            <circle cx="49.7" cy="22.3" r="0.6" fill="white" />
            <!-- Wing texture lines -->
            <path d="M18 32 Q24 28 34 30" stroke="#6B4F10" stroke-width="1.2" stroke-linecap="round" />
            <path d="M16 37 Q22 33 32 35" stroke="#6B4F10" stroke-width="1.2" stroke-linecap="round" />
            <!-- Legs -->
            <line x1="24" y1="52" x2="22" y2="60" stroke="#A07820" stroke-width="2.5" stroke-linecap="round" />
            <line x1="34" y1="52" x2="36" y2="60" stroke="#A07820" stroke-width="2.5" stroke-linecap="round" />
            <!-- Feet -->
            <path d="M18 60 L22 60 L24 57" stroke="#A07820" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
            <path d="M32 60 L36 60 L38 57" stroke="#A07820" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
            <!-- Feather texture -->
            <path d="M22 38 Q28 34 36 36" stroke="#A07820" stroke-width="0.8" stroke-linecap="round" />
            <path d="M20 43 Q26 39 34 41" stroke="#A07820" stroke-width="0.8" stroke-linecap="round" />
          </svg>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import InventoryList from './components/InventoryList.vue'
import ReceiptsView from './components/ReceiptsView.vue'
import RecipesView from './components/RecipesView.vue'
import SettingsView from './components/SettingsView.vue'
import { useInventoryStore } from './stores/inventory'
import { useEasterEggs } from './composables/useEasterEggs'

type Tab = 'inventory' | 'receipts' | 'recipes' | 'settings'

const currentTab = ref<Tab>('inventory')
const sidebarCollapsed = ref(false)
const inventoryStore = useInventoryStore()
const { kiwiVisible, kiwiDirection } = useEasterEggs()

// Wordmark click counter for chef mode easter egg
const wordmarkClicks = ref(0)
let wordmarkTimer: ReturnType<typeof setTimeout> | null = null
function onWordmarkClick() {
  wordmarkClicks.value++
  if (wordmarkTimer) clearTimeout(wordmarkTimer)
  if (wordmarkClicks.value >= 5) {
    wordmarkClicks.value = 0
    document.querySelector('.wordmark-kiwi')?.classList.add('chef-spin')
    setTimeout(() => document.querySelector('.wordmark-kiwi')?.classList.remove('chef-spin'), 800)
  } else {
    wordmarkTimer = setTimeout(() => { wordmarkClicks.value = 0 }, 1200)
  }
}

async function switchTab(tab: Tab) {
  currentTab.value = tab
  if (tab === 'recipes' && inventoryStore.items.length === 0) {
    await inventoryStore.fetchItems()
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.wordmark-kiwi {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 700;
  color: var(--color-primary);
  letter-spacing: -0.01em;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
}

/* ============================================
   MOBILE LAYOUT  (< 769px)
   sidebar hidden, bottom nav visible
   ============================================ */
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 68px; /* bottom nav clearance */
}

.sidebar { display: none; }
.app-body { display: contents; }

.app-header {
  background: var(--gradient-header);
  border-bottom: 1px solid var(--color-border);
  padding: var(--spacing-sm) var(--spacing-md);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(8px);
}

.header-inner {
  display: flex;
  align-items: center;
  min-height: 44px;
}

.header-inner .wordmark-kiwi { font-size: 24px; }

.app-main {
  flex: 1;
  padding: var(--spacing-md) 0 var(--spacing-xl);
}

.container {
  margin: 0 auto;
  padding: 0 var(--spacing-md);
}

.tab-content { min-height: 0; }

/* ---- Bottom nav ---- */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 200;
  background: var(--color-bg-elevated);
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: stretch;
  padding-bottom: env(safe-area-inset-bottom, 0);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.25);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 8px 4px 10px;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.18s ease, background 0.18s ease;
  border-radius: 0;
  position: relative;
}

.nav-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 20%;
  right: 20%;
  height: 2px;
  background: var(--color-primary);
  border-radius: 0 0 2px 2px;
  transform: scaleX(0);
  transition: transform 0.18s ease;
}

.nav-item:hover {
  color: var(--color-text-secondary);
  background: rgba(232, 168, 32, 0.06);
  transform: none;
  border-color: transparent;
}

.nav-item.active { color: var(--color-primary); }
.nav-item.active::before { transform: scaleX(1); }

.nav-icon { width: 22px; height: 22px; flex-shrink: 0; }

.nav-label {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  line-height: 1;
}

@media (max-width: 480px) {
  .container { padding: 0 var(--spacing-sm); }
  .app-main { padding: var(--spacing-sm) 0 var(--spacing-lg); }
}

/* ============================================
   DESKTOP LAYOUT  (≥ 769px)
   sidebar visible, bottom nav hidden
   ============================================ */
@media (min-width: 769px) {
  .bottom-nav { display: none; }

  #app {
    flex-direction: row;
    padding-bottom: 0;
    min-height: 100vh;
  }

  /* ---- Sidebar ---- */
  .sidebar {
    display: flex;
    flex-direction: column;
    width: 200px;
    min-height: 100vh;
    background: var(--color-bg-elevated);
    border-right: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    flex-shrink: 0;
    transition: width 0.22s cubic-bezier(0.4, 0, 0.2, 1);
    overflow: hidden;
    z-index: 100;
  }

  .sidebar-collapsed .sidebar {
    width: 56px;
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-md) var(--spacing-md) var(--spacing-sm);
    min-height: 56px;
    gap: var(--spacing-sm);
  }

  .sidebar-header .wordmark-kiwi {
    font-size: 22px;
    opacity: 1;
    transition: opacity 0.15s ease, width 0.22s ease;
    flex-shrink: 0;
  }

  .sidebar-collapsed .sidebar-header .wordmark-kiwi {
    opacity: 0;
    width: 0;
    pointer-events: none;
  }

  .sidebar-toggle {
    background: transparent;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    padding: 6px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: color 0.15s, background 0.15s;
  }

  .sidebar-toggle:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-secondary);
    transform: none;
    border-color: transparent;
  }

  .sidebar-nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--spacing-sm);
  }

  .sidebar-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: 10px var(--spacing-sm);
    border: none;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
    white-space: nowrap;
    width: 100%;
    text-align: left;
  }

  .sidebar-item:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-secondary);
    transform: none;
    border-color: transparent;
  }

  .sidebar-item.active {
    color: var(--color-primary);
    background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  }

  .sidebar-item .nav-icon { width: 20px; height: 20px; flex-shrink: 0; }

  .sidebar-label {
    font-size: var(--font-size-sm);
    font-weight: 600;
    opacity: 1;
    transition: opacity 0.12s ease;
    overflow: hidden;
  }

  .sidebar-collapsed .sidebar-label {
    opacity: 0;
    width: 0;
    pointer-events: none;
  }

  /* ---- Main body ---- */
  .app-body {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0; /* prevent overflow */
    contents: unset;
  }

  .app-header { display: none; } /* wordmark lives in sidebar on desktop */

  /* Override style.css #app max-width so sidebar spans full viewport */
  #app {
    max-width: none;
    margin: 0;
  }

  .app-main {
    flex: 1;
    padding: var(--spacing-xl) 0;
  }

  .container {
    max-width: 860px;
    padding: 0 var(--spacing-lg);
  }
}

@media (min-width: 1200px) {
  .container {
    max-width: 960px;
    padding: 0 var(--spacing-xl);
  }
}

/* Easter egg: wordmark spin on 5× click */
@keyframes chefSpin {
  0%   { transform: rotate(0deg) scale(1); }
  30%  { transform: rotate(180deg) scale(1.3); }
  60%  { transform: rotate(340deg) scale(1.1); }
  100% { transform: rotate(360deg) scale(1); }
}

.wordmark-kiwi.chef-spin {
  display: inline-block;
  animation: chefSpin 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

/* Kiwi bird transition */
.kiwi-fade-enter-active,
.kiwi-fade-leave-active {
  transition: opacity 0.4s ease;
}

.kiwi-fade-enter-from,
.kiwi-fade-leave-to {
  opacity: 0;
}
</style>
