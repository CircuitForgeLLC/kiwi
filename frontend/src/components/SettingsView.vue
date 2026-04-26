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

      <!-- Sensory Preferences -->
      <section class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Sensory Preferences</h3>
        <p class="text-sm text-secondary mb-md">
          Tell Kiwi what your senses prefer. Recipes that don't match will be
          filtered out quietly in Browse and Find. Leave everything unset and nothing is filtered.
        </p>

        <!-- Texture avoid pills -->
        <div class="form-group">
          <label class="form-label">
            <span class="mr-xs">Texture — avoid</span>
            <span class="text-xs text-muted">(select any textures you'd rather skip)</span>
          </label>
          <div class="flex flex-wrap gap-xs mt-xs" role="group" aria-label="Texture avoidance">
            <button
              v-for="tex in TEXTURE_OPTIONS"
              :key="tex.tag"
              :class="[
                'sensory-pill',
                settingsStore.sensoryPreferences.avoid_textures.includes(tex.tag)
                  ? 'sensory-pill--avoided'
                  : 'sensory-pill--neutral',
              ]"
              :aria-pressed="settingsStore.sensoryPreferences.avoid_textures.includes(tex.tag)"
              @click="toggleTexture(tex.tag)"
            >{{ tex.emoji }} {{ tex.label }}</button>
          </div>
        </div>

        <!-- Smell tolerance -->
        <div class="form-group mt-sm">
          <label class="form-label">
            <span class="mr-xs">Smell — max I'm ok with</span>
            <span class="text-xs text-muted">(tap to set your limit; tap again to clear)</span>
          </label>
          <div class="flex flex-wrap gap-xs mt-xs" role="group" aria-label="Smell tolerance">
            <button
              v-for="(level, idx) in SMELL_LEVELS"
              :key="String(level.value)"
              :class="['sensory-pill', getSmellClass(level.value, idx)]"
              :aria-pressed="settingsStore.sensoryPreferences.max_smell === level.value"
              @click="toggleSmell(level.value)"
            >{{ level.emoji }} {{ level.label }}</button>
          </div>
          <p v-if="settingsStore.sensoryPreferences.max_smell" class="text-xs text-muted mt-xs">
            Recipes stronger than <strong>{{ smellLabel(settingsStore.sensoryPreferences.max_smell) }}</strong> will be hidden.
          </p>
        </div>

        <!-- Noise tolerance -->
        <div class="form-group mt-sm">
          <label class="form-label">
            <span class="mr-xs">Noise — max I'm ok with</span>
            <span class="text-xs text-muted">(tap to set your limit; tap again to clear)</span>
          </label>
          <div class="flex flex-wrap gap-xs mt-xs" role="group" aria-label="Noise tolerance">
            <button
              v-for="(level, idx) in NOISE_LEVELS"
              :key="String(level.value)"
              :class="['sensory-pill', getNoiseClass(level.value, idx)]"
              :aria-pressed="settingsStore.sensoryPreferences.max_noise === level.value"
              @click="toggleNoise(level.value)"
            >{{ level.emoji }} {{ level.label }}</button>
          </div>
          <p v-if="settingsStore.sensoryPreferences.max_noise" class="text-xs text-muted mt-xs">
            Recipes louder than <strong>{{ noiseLabel(settingsStore.sensoryPreferences.max_noise) }}</strong> will be hidden.
          </p>
        </div>

        <div class="flex-start gap-sm mt-sm">
          <button
            class="btn btn-primary btn-sm"
            :disabled="settingsStore.loading"
            @click="settingsStore.saveSensory()"
          >
            <span v-if="settingsStore.loading">Saving…</span>
            <span v-else-if="settingsStore.saved">Saved!</span>
            <span v-else>Save sensory preferences</span>
          </button>
        </div>
      </section>

      <!-- Units -->
      <section class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Units</h3>
        <p class="text-sm text-secondary mb-sm">
          Choose how quantities and temperatures are displayed in your pantry and recipes.
        </p>
        <div class="flex-start gap-sm mb-sm" role="group" aria-label="Unit system">
          <button
            :class="['btn', 'btn-sm', settingsStore.unitSystem === 'metric' ? 'btn-primary' : 'btn-secondary']"
            :aria-pressed="settingsStore.unitSystem === 'metric'"
            @click="settingsStore.unitSystem = 'metric'"
          >
            Metric (g, ml, °C)
          </button>
          <button
            :class="['btn', 'btn-sm', settingsStore.unitSystem === 'imperial' ? 'btn-primary' : 'btn-secondary']"
            :aria-pressed="settingsStore.unitSystem === 'imperial'"
            @click="settingsStore.unitSystem = 'imperial'"
          >
            Imperial (oz, cups, °F)
          </button>
        </div>
        <div class="flex-start gap-sm">
          <button
            class="btn btn-primary btn-sm"
            :disabled="settingsStore.loading"
            @click="settingsStore.save()"
          >
            <span v-if="settingsStore.loading">Saving…</span>
            <span v-else-if="settingsStore.saved">✓ Saved!</span>
            <span v-else>Save</span>
          </button>
        </div>
      </section>

      <!-- Shopping Locale -->
      <section class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Shopping Region</h3>
        <p class="text-sm text-secondary mb-sm">
          Sets your Amazon storefront and which retailers appear in shopping links.
          Instacart and Walmart are US/CA only — other regions get Amazon.
        </p>
        <select
          class="form-input"
          v-model="settingsStore.shoppingLocale"
          aria-label="Shopping region"
          style="max-width: 20rem;"
        >
          <optgroup label="North America">
            <option value="us">United States (USD $)</option>
            <option value="ca">Canada (CAD CA$)</option>
            <option value="mx">Mexico (MXN MX$)</option>
          </optgroup>
          <optgroup label="Europe">
            <option value="gb">United Kingdom (GBP £)</option>
            <option value="de">Germany (EUR €)</option>
            <option value="fr">France (EUR €)</option>
            <option value="it">Italy (EUR €)</option>
            <option value="es">Spain (EUR €)</option>
            <option value="nl">Netherlands (EUR €)</option>
            <option value="se">Sweden (SEK kr)</option>
          </optgroup>
          <optgroup label="Asia Pacific">
            <option value="au">Australia (AUD A$)</option>
            <option value="nz">New Zealand (NZD NZ$) — via Amazon AU</option>
            <option value="jp">Japan (JPY ¥)</option>
            <option value="in">India (INR ₹)</option>
            <option value="sg">Singapore (SGD S$)</option>
          </optgroup>
          <optgroup label="South America">
            <option value="br">Brazil (BRL R$)</option>
          </optgroup>
        </select>
        <div class="flex-start gap-sm mt-sm">
          <button
            class="btn btn-primary btn-sm"
            :disabled="settingsStore.loading"
            @click="settingsStore.save()"
          >
            <span v-if="settingsStore.loading">Saving…</span>
            <span v-else-if="settingsStore.saved">✓ Saved!</span>
            <span v-else>Save</span>
          </button>
        </div>
      </section>

      <!-- Time-First Layout -->
      <section class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Recipe Search Layout</h3>
        <p class="text-sm text-secondary mb-sm">
          Choose how the Find tab looks when you search for recipes.
        </p>
        <div class="flex flex-col gap-xs" role="radiogroup" aria-label="Recipe search layout">
          <label
            v-for="opt in timeFirstLayoutOptions"
            :key="opt.value"
            class="flex-start gap-sm time-layout-option"
          >
            <input
              type="radio"
              name="time_first_layout"
              :value="opt.value"
              :checked="settingsStore.timeFirstLayout === opt.value"
              @change="settingsStore.timeFirstLayout = opt.value"
            />
            <span>
              <strong>{{ opt.label }}</strong>
              <span class="text-xs text-muted ml-xs">{{ opt.description }}</span>
            </span>
          </label>
        </div>
        <div class="flex-start gap-sm mt-sm">
          <button
            class="btn btn-primary btn-sm"
            :disabled="settingsStore.loading"
            @click="settingsStore.save()"
          >
            <span v-if="settingsStore.loading">Saving…</span>
            <span v-else-if="settingsStore.saved">✓ Saved!</span>
            <span v-else>Save</span>
          </button>
        </div>
      </section>

      <!-- Data Sharing (cloud only) -->
      <section v-if="isCloudMode" class="mt-md">
        <h3 class="text-lg font-semibold mb-xs">Data Sharing</h3>
        <label class="data-sharing-toggle flex-start gap-sm text-sm">
          <input
            type="checkbox"
            :checked="magpieOptIn"
            @change="setMagpieOptIn(($event.target as HTMLInputElement).checked)"
          />
          Share anonymized recipe ratings to help improve suggestions
        </label>
        <p class="text-xs text-muted mt-xs">
          When enabled, Kiwi sends the recipe source ID, your star rating, and
          style tags to CircuitForge. No personal information or pantry contents
          are included.
        </p>
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
import { householdAPI, settingsAPI, type HouseholdStatus } from '../services/api'
import type { TextureTag, SmellLevel, NoiseLevel } from '../services/api'
import type { TimeFirstLayout } from '../stores/settings'
import { useOrchUsage } from '../composables/useOrchUsage'

const settingsStore = useSettingsStore()
const recipesStore = useRecipesStore()
const { enabled: orchPillEnabled, setEnabled: setOrchPillEnabled } = useOrchUsage()

// Cloud mode — baked in at build time via VITE_CLOUD_MODE=true in cloud builds
const isCloudMode = import.meta.env.VITE_CLOUD_MODE === 'true'

// Data sharing — magpie opt-in (cloud mode only)
const magpieOptIn = ref(false)

async function loadMagpieOptIn(): Promise<void> {
  if (!isCloudMode) return
  const value = await settingsAPI.getSetting('magpie_opt_in')
  magpieOptIn.value = value === 'true'
}

async function setMagpieOptIn(enabled: boolean): Promise<void> {
  magpieOptIn.value = enabled
  await settingsAPI.setSetting('magpie_opt_in', enabled ? 'true' : 'false')
}

const timeFirstLayoutOptions: Array<{ value: TimeFirstLayout; label: string; description: string }> = [
  { value: 'auto',       label: 'Auto',        description: 'Shows a time selector when recipes are available.' },
  { value: 'time_first', label: 'Time First',  description: 'Always show the time bucket selector at the top.' },
  { value: 'normal',     label: 'Normal',      description: 'Standard layout — no time selector shown.' },
]

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
  await loadMagpieOptIn()
})

// ── Sensory taxonomy ───────────────────────────────────────────────────────

const TEXTURE_OPTIONS: { tag: TextureTag; label: string; emoji: string }[] = [
  { tag: 'mushy',   label: 'Mushy',   emoji: '🦫' },
  { tag: 'slimy',   label: 'Slimy',   emoji: '🫙' },
  { tag: 'crunchy', label: 'Crunchy', emoji: '🥜' },
  { tag: 'chewy',   label: 'Chewy',   emoji: '🍖' },
  { tag: 'creamy',  label: 'Creamy',  emoji: '🥣' },
  { tag: 'chunky',  label: 'Chunky',  emoji: '🫕' },
]

const SMELL_LEVELS: { value: SmellLevel; label: string; emoji: string }[] = [
  { value: 'mild',      label: 'Mild',      emoji: '🌿' },
  { value: 'aromatic',  label: 'Aromatic',  emoji: '🌸' },
  { value: 'pungent',   label: 'Pungent',   emoji: '🧄' },
  { value: 'fermented', label: 'Fermented', emoji: '🧀' },
]

const NOISE_LEVELS: { value: NoiseLevel; label: string; emoji: string }[] = [
  { value: 'quiet',    label: 'Quiet',    emoji: '🤫' },
  { value: 'moderate', label: 'Moderate', emoji: '🍳' },
  { value: 'loud',     label: 'Loud',     emoji: '🔥' },
  { value: 'very_loud', label: 'Very loud', emoji: '💥' },
]

function smellLabel(value: SmellLevel): string {
  return SMELL_LEVELS.find(l => l.value === value)?.label ?? ''
}

function noiseLabel(value: NoiseLevel): string {
  return NOISE_LEVELS.find(l => l.value === value)?.label ?? ''
}

function toggleTexture(tag: TextureTag) {
  const current = settingsStore.sensoryPreferences.avoid_textures
  const updated = current.includes(tag)
    ? current.filter(t => t !== tag)
    : [...current, tag]
  settingsStore.sensoryPreferences = {
    ...settingsStore.sensoryPreferences,
    avoid_textures: updated,
  }
}

function toggleSmell(value: SmellLevel) {
  const current = settingsStore.sensoryPreferences.max_smell
  settingsStore.sensoryPreferences = {
    ...settingsStore.sensoryPreferences,
    max_smell: current === value ? null : value,
  }
}

function toggleNoise(value: NoiseLevel) {
  const current = settingsStore.sensoryPreferences.max_noise
  settingsStore.sensoryPreferences = {
    ...settingsStore.sensoryPreferences,
    max_noise: current === value ? null : value,
  }
}

function getSmellClass(_value: SmellLevel, idx: number): string {
  const maxSmell = settingsStore.sensoryPreferences.max_smell
  if (!maxSmell) return 'sensory-pill--neutral'
  const maxIdx = SMELL_LEVELS.findIndex(l => l.value === maxSmell)
  if (idx === maxIdx) return 'sensory-pill--limit'
  if (idx < maxIdx) return 'sensory-pill--ok'
  return 'sensory-pill--neutral'
}

function getNoiseClass(_value: NoiseLevel, idx: number): string {
  const maxNoise = settingsStore.sensoryPreferences.max_noise
  if (!maxNoise) return 'sensory-pill--neutral'
  const maxIdx = NOISE_LEVELS.findIndex(l => l.value === maxNoise)
  if (idx === maxIdx) return 'sensory-pill--limit'
  if (idx < maxIdx) return 'sensory-pill--ok'
  return 'sensory-pill--neutral'
}
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

.orch-pill-toggle,
.data-sharing-toggle {
  cursor: pointer;
  align-items: center;
  color: var(--color-text);
}

.orch-pill-toggle input[type="checkbox"],
.data-sharing-toggle input[type="checkbox"] {
  accent-color: var(--color-primary);
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

/* ── Time-first layout option ────────────────────────────────────────────── */

.time-layout-option {
  cursor: pointer;
  padding: var(--spacing-xs, 0.25rem) 0;
  align-items: flex-start;
}

.time-layout-option input[type="radio"] {
  accent-color: var(--color-primary);
  margin-top: 0.15rem;
  flex-shrink: 0;
}

/* ── Sensory pills ───────────────────────────────────────────────────────── */

.sensory-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3rem 0.75rem;
  border-radius: 9999px;
  border: 1.5px solid var(--color-border, #e0e0e0);
  background: transparent;
  color: var(--color-text-secondary, #888);
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  user-select: none;
}

.sensory-pill:hover {
  opacity: 0.85;
}

.sensory-pill--avoided {
  background: rgba(220, 80, 60, 0.18);
  border-color: rgba(220, 80, 60, 0.40);
  color: #f08070;
}

.sensory-pill--ok {
  background: rgba(74, 140, 64, 0.15);
  border-color: rgba(74, 140, 64, 0.35);
  color: #7fc073;
}

.sensory-pill--limit {
  background: rgba(200, 140, 30, 0.18);
  border-color: rgba(200, 140, 30, 0.45);
  color: #c8a020;
}

.sensory-pill--neutral {
  background: transparent;
  border-color: var(--color-border, #e0e0e0);
  color: var(--color-text-secondary, #888);
}
</style>