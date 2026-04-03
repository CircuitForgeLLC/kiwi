import { ref, onMounted, onUnmounted } from 'vue'

const KONAMI = ['ArrowUp','ArrowUp','ArrowDown','ArrowDown','ArrowLeft','ArrowRight','ArrowLeft','ArrowRight','b','a']
const KIWI_WORD = ['k','i','w','i']

// Module-level shared state — single instance across all component uses
const neonMode = ref(false)
const kiwiVisible = ref(false)
const kiwiDirection = ref<'ltr' | 'rtl'>('rtl') // bird enters from right by default

const NEON_VARS: Record<string, string> = {
  '--color-bg-primary':      '#070011',
  '--color-bg-secondary':    '#0f001f',
  '--color-bg-elevated':     '#160028',
  '--color-bg-card':         '#160028',
  '--color-bg-input':        '#0f001f',
  '--color-primary':         '#ff006e',
  '--color-text-primary':    '#f0e6ff',
  '--color-text-secondary':  '#c090ff',
  '--color-text-muted':      '#7040a0',
  '--color-border':          'rgba(255, 0, 110, 0.22)',
  '--color-border-focus':    '#ff006e',
  '--color-info':            '#00f5ff',
  '--color-info-bg':         'rgba(0, 245, 255, 0.10)',
  '--color-info-border':     'rgba(0, 245, 255, 0.30)',
  '--color-info-light':      '#00f5ff',
  '--color-success':         '#39ff14',
  '--color-success-bg':      'rgba(57, 255, 20, 0.10)',
  '--color-success-border':  'rgba(57, 255, 20, 0.30)',
  '--color-success-light':   '#39ff14',
  '--color-warning':         '#ffbe0b',
  '--color-warning-bg':      'rgba(255, 190, 11, 0.10)',
  '--color-warning-border':  'rgba(255, 190, 11, 0.30)',
  '--color-warning-light':   '#ffbe0b',
  '--shadow-amber':          '0 0 18px rgba(255, 0, 110, 0.55)',
  '--shadow-md':             '0 2px 16px rgba(255, 0, 110, 0.18)',
  '--shadow-lg':             '0 4px 28px rgba(255, 0, 110, 0.25)',
  '--gradient-primary':      'linear-gradient(135deg, #ff006e 0%, #8338ec 100%)',
  '--gradient-header':       'linear-gradient(135deg, #070011 0%, #160028 100%)',
  '--color-loc-fridge':      '#00f5ff',
  '--color-loc-freezer':     '#8338ec',
  '--color-loc-pantry':      '#ff006e',
  '--color-loc-cabinet':     '#ffbe0b',
  '--color-loc-garage-freezer': '#39ff14',
}

function applyNeon() {
  const root = document.documentElement
  for (const [prop, val] of Object.entries(NEON_VARS)) {
    root.style.setProperty(prop, val)
  }
  document.body.classList.add('neon-mode')
}

function removeNeon() {
  const root = document.documentElement
  for (const prop of Object.keys(NEON_VARS)) {
    root.style.removeProperty(prop)
  }
  document.body.classList.remove('neon-mode')
}

function toggleNeon() {
  neonMode.value = !neonMode.value
  if (neonMode.value) {
    applyNeon()
    localStorage.setItem('kiwi-neon-mode', '1')
  } else {
    removeNeon()
    localStorage.removeItem('kiwi-neon-mode')
  }
}

function spawnKiwi() {
  kiwiDirection.value = Math.random() > 0.5 ? 'ltr' : 'rtl'
  kiwiVisible.value = true
  setTimeout(() => { kiwiVisible.value = false }, 5500)
}

export function useEasterEggs() {
  const konamiBuffer: string[] = []
  const kiwiBuffer: string[] = []

  function onKeyDown(e: KeyboardEvent) {
    // Skip when user is typing in a form input
    const tag = (e.target as HTMLElement)?.tagName
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'

    // Konami code — works even in inputs
    konamiBuffer.push(e.key)
    if (konamiBuffer.length > KONAMI.length) konamiBuffer.shift()
    if (konamiBuffer.join(',') === KONAMI.join(',')) {
      toggleNeon()
      konamiBuffer.length = 0
    }

    // KIWI word — only when not in a form input
    if (!isInput) {
      const key = e.key.toLowerCase()
      if ('kiwi'.includes(key) && key.length === 1) {
        kiwiBuffer.push(key)
        if (kiwiBuffer.length > KIWI_WORD.length) kiwiBuffer.shift()
        if (kiwiBuffer.join('') === 'kiwi') {
          spawnKiwi()
          kiwiBuffer.length = 0
        }
      } else {
        kiwiBuffer.length = 0
      }
    }
  }

  onMounted(() => {
    if (localStorage.getItem('kiwi-neon-mode')) {
      neonMode.value = true
      applyNeon()
    }
    window.addEventListener('keydown', onKeyDown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeyDown)
  })

  return {
    neonMode,
    kiwiVisible,
    kiwiDirection,
    toggleNeon,
    spawnKiwi,
  }
}
