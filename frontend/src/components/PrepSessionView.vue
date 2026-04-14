<!-- frontend/src/components/PrepSessionView.vue -->
<template>
  <div class="prep-session-view">
    <div v-if="loading" class="panel-loading">Building prep schedule...</div>

    <template v-else-if="prepSession">
      <p class="prep-intro">
        Tasks are ordered to make the most of your oven and stovetop.
        Edit any time estimate that looks wrong — your changes are saved.
      </p>

      <ol class="task-list" role="list">
        <li
          v-for="task in prepSession.tasks"
          :key="task.id"
          class="task-item"
          :class="{ 'user-edited': task.user_edited }"
        >
          <div class="task-header">
            <span class="task-order" aria-hidden="true">{{ task.sequence_order }}</span>
            <span class="task-label">{{ task.task_label }}</span>
            <span v-if="task.equipment" class="task-equip">{{ task.equipment }}</span>
          </div>

          <div class="task-meta">
            <label class="duration-label">
              Time estimate (min):
              <input
                type="number"
                min="1"
                class="duration-input"
                :value="task.duration_minutes ?? ''"
                :placeholder="task.duration_minutes ? '' : 'unknown'"
                :aria-label="`Duration for ${task.task_label} in minutes`"
                @change="onDurationChange(task.id, ($event.target as HTMLInputElement).value)"
              />
            </label>
            <span v-if="task.user_edited" class="edited-badge" title="You edited this">edited</span>
          </div>

          <div v-if="task.notes" class="task-notes">{{ task.notes }}</div>
        </li>
      </ol>

      <div v-if="!prepSession.tasks.length" class="empty-state">
        No recipes assigned yet — add some to your plan first.
      </div>
    </template>

    <div v-else class="empty-state">
      <button class="load-btn" @click="$emit('load')">Build prep schedule</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMealPlanStore } from '../stores/mealPlan'
import { storeToRefs } from 'pinia'

defineEmits<{ (e: 'load'): void }>()

const store = useMealPlanStore()
const { prepSession, prepLoading: loading } = storeToRefs(store)

async function onDurationChange(taskId: number, value: string) {
  const minutes = parseInt(value, 10)
  if (!isNaN(minutes) && minutes > 0) {
    await store.updatePrepTask(taskId, { duration_minutes: minutes })
  }
}
</script>

<style scoped>
.prep-session-view { display: flex; flex-direction: column; gap: 1rem; }
.panel-loading { font-size: 0.85rem; opacity: 0.6; padding: 1rem 0; }
.prep-intro { font-size: 0.82rem; opacity: 0.65; margin: 0; }

.task-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; }

.task-item {
  padding: 0.6rem 0.8rem; border-radius: 8px;
  background: var(--color-surface-2); border: 1px solid var(--color-border);
  display: flex; flex-direction: column; gap: 0.35rem;
}
.task-item.user-edited { border-color: var(--color-accent); }

.task-header { display: flex; align-items: center; gap: 0.5rem; }
.task-order {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--color-accent); color: white;
  font-size: 0.7rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.task-label { flex: 1; font-size: 0.88rem; font-weight: 500; }
.task-equip { font-size: 0.68rem; padding: 2px 6px; border-radius: 12px; background: var(--color-surface); opacity: 0.7; }

.task-meta { display: flex; align-items: center; gap: 0.75rem; }
.duration-label { font-size: 0.75rem; opacity: 0.7; display: flex; align-items: center; gap: 0.3rem; }
.duration-input {
  width: 52px; padding: 2px 4px; border-radius: 4px;
  border: 1px solid var(--color-border); background: var(--color-surface);
  font-size: 0.78rem; color: var(--color-text);
}
.duration-input:focus { outline: 2px solid var(--color-accent); outline-offset: 1px; }
.edited-badge { font-size: 0.65rem; opacity: 0.5; font-style: italic; }
.task-notes { font-size: 0.75rem; opacity: 0.6; }

.empty-state { font-size: 0.85rem; opacity: 0.55; padding: 1rem 0; text-align: center; }
.load-btn {
  font-size: 0.85rem; padding: 0.5rem 1.2rem;
  background: var(--color-accent-subtle); color: var(--color-accent);
  border: 1px solid var(--color-accent); border-radius: 20px; cursor: pointer;
}
.load-btn:hover { background: var(--color-accent); color: white; }
</style>
