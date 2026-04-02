<template>
  <div class="settings-view">
    <div class="card">
      <h2 class="section-title text-xl mb-md">Settings</h2>

      <!-- Cooking Equipment -->
      <section>
        <h3 class="text-lg font-semibold mb-xs">Cooking Equipment</h3>
        <p class="text-sm text-secondary mb-md">
          Tell Kiwi what you have — used when Hard Day Mode is on to filter out recipes requiring
          equipment you don't own.
        </p>

        <!-- Current equipment tags -->
        <div class="tags-wrap flex flex-wrap gap-xs mb-sm">
          <span
            v-for="item in settingsStore.cookingEquipment"
            :key="item"
            class="tag-chip status-badge status-info"
          >
            {{ item }}
            <button class="chip-remove" @click="removeEquipment(item)" aria-label="Remove">×</button>
          </span>
        </div>

        <!-- Custom input -->
        <div class="form-group">
          <label class="form-label">Add equipment</label>
          <input
            class="form-input"
            v-model="equipmentInput"
            placeholder="Type equipment name, press Enter or comma"
            @keydown="onEquipmentKey"
            @blur="commitEquipmentInput"
          />
        </div>

        <!-- Quick-add chips -->
        <div class="form-group">
          <label class="form-label">Quick-add</label>
          <div class="flex flex-wrap gap-xs">
            <button
              v-for="eq in quickAddOptions"
              :key="eq"
              :class="['btn', 'btn-sm', 'btn-secondary', { active: settingsStore.cookingEquipment.includes(eq) }]"
              @click="toggleEquipment(eq)"
            >
              {{ eq }}
            </button>
          </div>
        </div>

        <!-- Save button -->
        <div class="flex-start gap-sm">
          <button
            class="btn btn-primary"
            :disabled="settingsStore.loading"
            @click="settingsStore.save()"
          >
            <span v-if="settingsStore.loading">Saving…</span>
            <span v-else-if="settingsStore.saved">✓ Saved!</span>
            <span v-else>Save Settings</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'

const settingsStore = useSettingsStore()

const equipmentInput = ref('')

const quickAddOptions = [
  'Oven',
  'Stovetop',
  'Microwave',
  'Air Fryer',
  'Instant Pot',
  'Slow Cooker',
  'Grill',
  'Blender',
]

function addEquipment(value: string) {
  const item = value.trim()
  if (item && !settingsStore.cookingEquipment.includes(item)) {
    settingsStore.cookingEquipment = [...settingsStore.cookingEquipment, item]
  }
  equipmentInput.value = ''
}

function removeEquipment(item: string) {
  settingsStore.cookingEquipment = settingsStore.cookingEquipment.filter((e) => e !== item)
}

function toggleEquipment(item: string) {
  if (settingsStore.cookingEquipment.includes(item)) {
    removeEquipment(item)
  } else {
    addEquipment(item)
  }
}

function onEquipmentKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addEquipment(equipmentInput.value)
  }
}

function commitEquipmentInput() {
  if (equipmentInput.value.trim()) {
    addEquipment(equipmentInput.value)
  }
}

onMounted(async () => {
  await settingsStore.load()
})
</script>

<style scoped>
.mb-md {
  margin-bottom: var(--spacing-md);
}

.mb-sm {
  margin-bottom: var(--spacing-sm);
}

.mb-xs {
  margin-bottom: var(--spacing-xs);
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.chip-remove {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
  line-height: 1;
  color: inherit;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.chip-remove:hover {
  opacity: 1;
  transform: none;
}
</style>
