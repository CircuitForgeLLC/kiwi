/**
 * Unit conversion utilities — mirrors app/utils/units.py.
 * Source of truth: metric (g, ml). Display conversion happens here.
 */

export type UnitSystem = 'metric' | 'imperial'

// ── Conversion thresholds ─────────────────────────────────────────────────

const IMPERIAL_MASS: [number, string, number][] = [
  [453.592, 'lb', 453.592],
  [0, 'oz', 28.3495],
]

const METRIC_MASS: [number, string, number][] = [
  [1000, 'kg', 1000],
  [0, 'g', 1],
]

const IMPERIAL_VOLUME: [number, string, number][] = [
  [3785.41, 'gal', 3785.41],
  [946.353, 'qt', 946.353],
  [473.176, 'pt', 473.176],
  [236.588, 'cup', 236.588],
  [0, 'fl oz', 29.5735],
]

const METRIC_VOLUME: [number, string, number][] = [
  [1000, 'l', 1000],
  [0, 'ml', 1],
]

// ── Public API ────────────────────────────────────────────────────────────

/**
 * Convert a stored metric quantity to a display quantity + unit.
 * baseUnit must be 'g', 'ml', or 'each'.
 */
export function convertFromMetric(
  quantity: number,
  baseUnit: string,
  preferred: UnitSystem = 'metric',
): [number, string] {
  if (baseUnit === 'each') return [quantity, 'each']

  const thresholds =
    baseUnit === 'g'
      ? preferred === 'imperial' ? IMPERIAL_MASS : METRIC_MASS
      : baseUnit === 'ml'
        ? preferred === 'imperial' ? IMPERIAL_VOLUME : METRIC_VOLUME
        : null

  if (!thresholds) return [Math.round(quantity * 100) / 100, baseUnit]

  for (const [min, unit, factor] of thresholds) {
    if (quantity >= min) {
      return [Math.round((quantity / factor) * 100) / 100, unit]
    }
  }

  return [Math.round(quantity * 100) / 100, baseUnit]
}

/** Format a quantity + unit for display, e.g. "1.5 kg" or "3.2 oz". */
export function formatQuantity(
  quantity: number,
  baseUnit: string,
  preferred: UnitSystem = 'metric',
): string {
  const [qty, unit] = convertFromMetric(quantity, baseUnit, preferred)
  if (unit === 'each') return `${qty}`
  return `${qty} ${unit}`
}
