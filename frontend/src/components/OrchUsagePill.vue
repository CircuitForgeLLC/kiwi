<template>
  <!-- Only shown when user has opted in AND a lifetime key is present (usage != null) -->
  <div
    v-if="enabled && usage !== null"
    class="orch-usage-pill"
    :class="{ 'orch-usage-pill--low': isLow }"
    :title="`Cloud recipe calls this period: ${usage.calls_used} of ${usage.calls_total}`"
  >
    <span class="orch-usage-pill__label">
      {{ usage.calls_used + usage.topup_calls }} / {{ usage.calls_total }} calls
      <span class="orch-usage-pill__reset">· resets {{ resetsLabel }}</span>
    </span>
    <a
      class="orch-usage-pill__topup"
      href="https://circuitforge.tech/kiwi/topup"
      target="_blank"
      rel="noopener"
    >Topup</a>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useOrchUsage } from '@/composables/useOrchUsage'

const { usage, enabled, resetsLabel } = useOrchUsage()

// Warn visually when less than 20% remains — calm yellow only, no red/panic
const isLow = computed(() => {
  if (!usage.value || usage.value.calls_total === 0) return false
  const remaining = usage.value.calls_total - usage.value.calls_used + usage.value.topup_calls
  return remaining / usage.value.calls_total < 0.2
})
</script>

<style scoped>
.orch-usage-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 0.25rem 0.625rem;
  border-radius: 999px;
  font-size: var(--font-size-sm);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.orch-usage-pill--low {
  background: var(--color-warning-bg);
  border-color: var(--color-warning-border);
  color: var(--color-warning);
}

.orch-usage-pill__reset {
  opacity: 0.7;
}

.orch-usage-pill__topup {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
  white-space: nowrap;
  margin-left: var(--spacing-xs);
}

.orch-usage-pill__topup:hover {
  text-decoration: underline;
}
</style>
