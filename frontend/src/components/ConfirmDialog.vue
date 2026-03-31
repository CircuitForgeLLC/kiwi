<template>
  <Transition name="modal">
    <div v-if="show" class="modal-overlay" @click="handleCancel">
      <div class="modal-container" @click.stop>
        <div class="modal-header">
          <h3>{{ title }}</h3>
        </div>

        <div class="modal-body">
          <p>{{ message }}</p>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleCancel">
            {{ cancelText }}
          </button>
          <button :class="['btn', `btn-${type}`]" @click="handleConfirm">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
interface Props {
  show: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  type?: 'primary' | 'danger' | 'warning'
}

withDefaults(defineProps<Props>(), {
  title: 'Confirm',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  type: 'primary',
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
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
  max-width: 500px;
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
}

.modal-body p {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  line-height: 1.5;
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

.btn-secondary:hover {
  background: var(--color-bg-primary);
}

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
  box-shadow: var(--shadow-md);
}

.btn-warning {
  background: var(--color-warning);
  color: white;
}

.btn-warning:hover {
  background: var(--color-warning-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

/* Animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container {
  transform: scale(0.9) translateY(-20px);
}

.modal-leave-to .modal-container {
  transform: scale(0.9) translateY(-20px);
}
</style>
