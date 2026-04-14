/**
 * useOrchUsage — reactive cf-orch call budget for lifetime/founders users.
 *
 * Auto-fetches on mount when enabled. Returns null for subscription users (no cap applies).
 * The `enabled` state is persisted to localStorage — users opt in to seeing the pill.
 */
import { ref, computed, onMounted } from 'vue'
import { getOrchUsage, type OrchUsage } from '@/services/api'

const STORAGE_KEY = 'kiwi:orchUsagePillEnabled'

// Shared singleton state across all component instances
const usage = ref<OrchUsage | null>(null)
const loading = ref(false)
const enabled = ref<boolean>(
  typeof localStorage !== 'undefined'
    ? localStorage.getItem(STORAGE_KEY) === 'true'
    : false
)

async function fetchUsage(): Promise<void> {
  loading.value = true
  try {
    usage.value = await getOrchUsage()
  } catch {
    // Non-blocking — UI stays hidden on error
    usage.value = null
  } finally {
    loading.value = false
  }
}

function setEnabled(val: boolean): void {
  enabled.value = val
  localStorage.setItem(STORAGE_KEY, String(val))
  if (val && usage.value === null && !loading.value) {
    fetchUsage()
  }
}

const resetsLabel = computed<string>(() => {
  if (!usage.value?.resets_on) return ''
  const d = new Date(usage.value.resets_on + 'T00:00:00')
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
})

export function useOrchUsage() {
  onMounted(() => {
    if (enabled.value && usage.value === null && !loading.value) {
      fetchUsage()
    }
  })

  return { usage, loading, enabled, setEnabled, fetchUsage, resetsLabel }
}
