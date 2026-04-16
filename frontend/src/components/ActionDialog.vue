<template>
  <Transition name="modal">
    <div v-if="show" class="modal-overlay" @click="handleCancel">
      <div class="modal-container" @click.stop>
        <div class="modal-header">
          <h3>{{ title }}</h3>
        </div>

        <div class="modal-body">
          <p>{{ message }}</p>

          <!-- Partial quantity input -->
          <div v-if="inputType === 'quantity'" class="action-input-row">
            <label class="action-input-label">{{ inputLabel }}</label>
            <div class="qty-input-group">
              <input
                v-model.number="inputNumber"
                type="number"
                :min="0.01"
                :max="inputMax"
                step="0.5"
                class="action-number-input"
                :aria-label="inputLabel"
              />
              <span class="qty-unit">{{ inputUnit }}</span>
            </div>
            <button class="btn-use-all" @click="inputNumber = inputMax">
              Use all ({{ inputMax }} {{ inputUnit }})
            </button>
          </div>

          <!-- Reason select -->
          <div v-if="inputType === 'select'" class="action-input-row">
            <label class="action-input-label">{{ inputLabel }}</label>
            <select v-model="inputSelect" class="action-select" :aria-label="inputLabel">
              <option value="">— skip —</option>
              <option v-for="opt in inputOptions" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleCancel">Cancel</button>
          <button :class="['btn', `btn-${type}`]" @click="handleConfirm">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  show: boolean
  title?: string
  message: string
  confirmText?: string
  type?: 'primary' | 'danger' | 'warning' | 'secondary'
  inputType?: 'quantity' | 'select' | null
  inputLabel?: string
  inputMax?: number
  inputUnit?: string
  inputOptions?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Confirm',
  confirmText: 'Confirm',
  type: 'primary',
  inputType: null,
  inputLabel: '',
  inputMax: 1,
  inputUnit: '',
  inputOptions: () => [],
})

const emit = defineEmits<{
  confirm: [value: number | string | undefined]
  cancel: []
}>()

const inputNumber = ref<number>(props.inputMax)
const inputSelect = ref<string>('')

watch(() => props.inputMax, (v) => { inputNumber.value = v })
watch(() => props.show, (v) => {
  if (v) {
    inputNumber.value = props.inputMax
    inputSelect.value = ''
  }
})

function handleConfirm() {
  if (props.inputType === 'quantity') {
    const qty = Math.min(Math.max(0.01, inputNumber.value || props.inputMax), props.inputMax)
    emit('confirm', qty)
  } else if (props.inputType === 'select') {
    emit('confirm', inputSelect.value || undefined)
  } else {
    emit('confirm', undefined)
  }
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: var(--spacing-lg);
}

.modal-container {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  max-width: 480px;
  width: 100%;
  overflow: hidden;
}

.modal-header {
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.modal-body {
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.modal-body p {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  line-height: 1.5;
}

.action-input-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.action-input-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  font-weight: 500;
}

.qty-input-group {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.action-number-input {
  width: 90px;
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
}

.qty-unit {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.btn-use-all {
  align-self: flex-start;
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.action-select {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  width: 100%;
}

.modal-footer {
  padding: var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
}

.btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover { background: var(--color-bg-primary); }

.btn-primary {
  background: var(--gradient-primary);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn-danger {
  background: var(--color-error);
  color: white;
}

.btn-danger:hover {
  background: var(--color-error-dark);
  transform: translateY(-1px);
}

.btn-warning {
  background: var(--color-warning);
  color: white;
}

/* Animations */
.modal-enter-active,
.modal-leave-active { transition: opacity 0.3s ease; }
.modal-enter-active .modal-container,
.modal-leave-active .modal-container { transition: transform 0.3s ease; }
.modal-enter-from,
.modal-leave-to { opacity: 0; }
.modal-enter-from .modal-container,
.modal-leave-to .modal-container { transform: scale(0.9) translateY(-20px); }
</style>
