<template>
  <Transition name="toast">
    <div v-if="visible" :class="['toast', type]" @click="close">
      <div class="toast-icon">{{ icon }}</div>
      <div class="toast-content">
        <div class="toast-message">{{ message }}</div>
      </div>
      <button class="toast-close" @click.stop="close">×</button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

interface Props {
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  show?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  duration: 3000,
  show: false,
})

const emit = defineEmits<{
  close: []
}>()

const visible = ref(props.show)
let timeout: number | null = null

const icon = {
  success: '✓',
  error: '✗',
  warning: '⚠',
  info: 'ℹ',
}[props.type]

watch(() => props.show, (newVal) => {
  if (newVal) {
    visible.value = true
    if (props.duration > 0) {
      if (timeout) clearTimeout(timeout)
      timeout = window.setTimeout(() => {
        close()
      }, props.duration)
    }
  } else {
    visible.value = false
  }
})

onMounted(() => {
  if (props.show && props.duration > 0) {
    timeout = window.setTimeout(() => {
      close()
    }, props.duration)
  }
})

function close() {
  visible.value = false
  if (timeout) {
    clearTimeout(timeout)
    timeout = null
  }
  emit('close')
}
</script>

<style scoped>
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  min-width: 300px;
  max-width: 500px;
  padding: var(--spacing-md);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  z-index: 10000;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.toast:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-xl);
}

.toast-icon {
  font-size: var(--font-size-xl);
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.toast-content {
  flex: 1;
  min-width: 0;
}

.toast-message {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  word-wrap: break-word;
}

.toast-close {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-2xl);
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color 0.2s ease;
}

.toast-close:hover {
  color: var(--color-text-primary);
}

/* Type-specific styles */
.toast.success {
  border-left: 4px solid var(--color-success);
}

.toast.success .toast-icon {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.toast.error {
  border-left: 4px solid var(--color-error);
}

.toast.error .toast-icon {
  background: var(--color-error-bg);
  color: var(--color-error);
}

.toast.warning {
  border-left: 4px solid var(--color-warning);
}

.toast.warning .toast-icon {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.toast.info {
  border-left: 4px solid var(--color-info);
}

.toast.info .toast-icon {
  background: var(--color-info-bg);
  color: var(--color-info);
}

/* Animations */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

/* Mobile Responsive */

/* Small phones (320px - 480px) */
@media (max-width: 480px) {
  .toast {
    top: 10px;
    right: 10px;
    left: 10px;
    min-width: auto;
    max-width: none;
    padding: var(--spacing-sm) var(--spacing-md);
    gap: var(--spacing-sm);
  }

  .toast-icon {
    font-size: var(--font-size-lg);
    width: 28px;
    height: 28px;
  }

  .toast-message {
    font-size: var(--font-size-sm);
  }

  .toast-close {
    font-size: var(--font-size-xl);
    width: 20px;
    height: 20px;
  }

  /* Adjust animation for centered toast */
  .toast-enter-from {
    transform: translateY(-100%);
  }

  .toast-leave-to {
    transform: translateY(-100%);
  }
}

/* Large phones and small tablets (481px - 768px) */
@media (min-width: 481px) and (max-width: 768px) {
  .toast {
    top: 15px;
    right: 15px;
    min-width: 250px;
    max-width: 400px;
  }
}

/* Tablets (769px - 1024px) */
@media (min-width: 769px) and (max-width: 1024px) {
  .toast {
    min-width: 280px;
    max-width: 450px;
  }
}
</style>
