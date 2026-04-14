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

      <!-- Display Preferences -->
      <section class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Display</h3>
        <label class="orch-pill-toggle flex-start gap-sm text-sm">
          <input
            type="checkbox"
            :checked="orchPillEnabled"
            @change="setOrchPillEnabled(($event.target as HTMLInputElement).checked)"
          />
          Show cloud recipe call budget in Recipes
        </label>
        <p class="text-xs text-muted mt-xs">
          Displays your remaining cloud recipe calls near the level selector. Only visible if you have a lifetime or founders key.
        </p>
      </section>
    </div>
    <div class="card mt-md">
      <h2 class="section-title text-xl mb-md">Cook History</h2>
      <p v-if="recipesStore.cookLog.length === 0" class="text-sm text-muted">
        No recipes cooked yet. Tap "I cooked this" on any recipe to log it.
      </p>
      <template v-else>
        <div class="log-list">
          <div
            v-for="entry in sortedCookLog"
            :key="entry.cookedAt"
            class="log-entry"
          >
            <span class="log-title text-sm">{{ entry.title }}</span>
            <span class="log-date text-xs text-muted">{{ formatCookDate(entry.cookedAt) }}</span>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm mt-sm" @click="recipesStore.clearCookLog()">
          Clear history
        </button>
      </template>
    </div>

    <!-- Household (Premium) -->
    <div v-if="householdVisible" class="card mt-md">
      <h2 class="section-title text-xl mb-md">Household</h2>

      <!-- Loading -->
      <p v-if="householdLoading" class="text-sm text-muted">Loading…</p>

      <!-- Error -->
      <p v-if="householdError" class="text-sm status-badge status-error">{{ householdError }}</p>

      <!-- Not in a household -->
      <template v-else-if="!householdStatus?.in_household">
        <p class="text-sm text-secondary mb-md">
          Create a household to share your pantry with family or housemates.
          All members see and edit the same inventory.
        </p>
        <button class="btn btn-primary" :disabled="householdLoading" @click="handleCreateHousehold">
          Create Household
        </button>
      </template>

      <!-- In household -->
      <template v-else>
        <p class="text-sm text-muted mb-sm">
          Household ID: <code class="household-id">{{ householdStatus.household_id }}</code>
        </p>

        <!-- Owner: member list + invite -->
        <template v-if="householdStatus.is_owner">
          <h3 class="text-base font-semibold mb-xs">Members ({{ householdStatus.members.length }}/{{ householdStatus.max_seats }})</h3>
          <div class="member-list mb-md">
            <div v-for="m in householdStatus.members" :key="m.user_id" class="member-row">
              <span class="text-sm member-id">{{ m.user_id }}</span>
              <span v-if="m.is_owner" class="status-badge status-info text-xs">Owner</span>
              <button
                v-else
                class="btn btn-ghost btn-sm"
                @click="handleRemoveMember(m.user_id)"
              >Remove</button>
            </div>
          </div>

          <!-- Invite link -->
          <div v-if="inviteUrl" class="invite-row mb-sm">
            <input class="form-input invite-input" :value="inviteUrl" readonly />
            <button class="btn btn-secondary btn-sm" @click="copyInvite">
              {{ inviteCopied ? '✓ Copied' : 'Copy' }}
            </button>
          </div>
          <button
            class="btn btn-primary btn-sm"
            :disabled="householdLoading"
            @click="handleInvite"
          >{{ inviteUrl ? 'New invite link' : 'Generate invite link' }}</button>
        </template>

        <!-- Member: leave button -->
        <template v-else>
          <p class="text-sm text-secondary mb-md">
            You are a member of this shared household pantry.
          </p>
          <button class="btn btn-ghost btn-sm" @click="handleLeave">Leave Household</button>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useRecipesStore } from '../stores/recipes'
import { householdAPI, type HouseholdStatus } from '../services/api'
import { useOrchUsage } from '../composables/useOrchUsage'

const settingsStore = useSettingsStore()
const recipesStore = useRecipesStore()
const { enabled: orchPillEnabled, setEnabled: setOrchPillEnabled } = useOrchUsage()

const sortedCookLog = computed(() =>
  [...recipesStore.cookLog].sort((a, b) => b.cookedAt - a.cookedAt)
)

function formatCookDate(ms: number): string {
  return new Date(ms).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

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

// Household (#5)
const householdVisible = ref(false)
const householdLoading = ref(false)
const householdError = ref<string | null>(null)
const householdStatus = ref<HouseholdStatus | null>(null)
const inviteUrl = ref<string | null>(null)
const inviteCopied = ref(false)

async function loadHouseholdStatus() {
  householdLoading.value = true
  householdError.value = null
  try {
    householdStatus.value = await householdAPI.status()
    householdVisible.value = true
  } catch (err: unknown) {
    // 403 = not premium — hide the card silently
    const status = (err as any)?.response?.status
    if (status !== 403) {
      householdError.value = 'Could not load household status.'
      householdVisible.value = true
    }
  } finally {
    householdLoading.value = false
  }
}

async function handleCreateHousehold() {
  householdLoading.value = true
  try {
    await householdAPI.create()
    await loadHouseholdStatus()
  } catch {
    householdError.value = 'Could not create household. Please try again.'
  } finally {
    householdLoading.value = false
  }
}

async function handleInvite() {
  householdLoading.value = true
  try {
    const result = await householdAPI.invite()
    inviteUrl.value = result.invite_url
  } catch {
    householdError.value = 'Could not generate invite link.'
  } finally {
    householdLoading.value = false
  }
}

async function copyInvite() {
  if (!inviteUrl.value) return
  await navigator.clipboard.writeText(inviteUrl.value)
  inviteCopied.value = true
  setTimeout(() => { inviteCopied.value = false }, 2000)
}

async function handleLeave() {
  if (!confirm('Leave the household? You will return to your personal pantry.')) return
  householdLoading.value = true
  try {
    await householdAPI.leave()
    await loadHouseholdStatus()
    inviteUrl.value = null
  } catch {
    householdError.value = 'Could not leave household. Please try again.'
  } finally {
    householdLoading.value = false
  }
}

async function handleRemoveMember(userId: string) {
  if (!confirm(`Remove member ${userId}?`)) return
  householdLoading.value = true
  try {
    await householdAPI.removeMember(userId)
    await loadHouseholdStatus()
  } catch {
    householdError.value = 'Could not remove member.'
  } finally {
    householdLoading.value = false
  }
}

onMounted(async () => {
  await settingsStore.load()
  await loadHouseholdStatus()
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

.mt-md {
  margin-top: var(--spacing-md);
}

.mt-sm {
  margin-top: var(--spacing-sm);
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-entry {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
}

.log-entry:last-child {
  border-bottom: none;
}

.log-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-date {
  flex-shrink: 0;
}

.btn-ghost {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
}

.btn-ghost:hover {
  color: var(--color-error, #dc2626);
  background: transparent;
  transform: none;
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
}

.household-id {
  font-size: var(--font-size-xs);
  background: var(--color-bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

.member-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
  gap: var(--spacing-sm);
}

.member-row:last-child {
  border-bottom: none;
}

.member-id {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.invite-row {
  display: flex;
  gap: var(--spacing-xs);
  align-items: center;
}

.invite-input {
  flex: 1;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.orch-pill-toggle {
  cursor: pointer;
  align-items: center;
  color: var(--color-text);
}

.orch-pill-toggle input[type="checkbox"] {
  accent-color: var(--color-primary);
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}
</style>
