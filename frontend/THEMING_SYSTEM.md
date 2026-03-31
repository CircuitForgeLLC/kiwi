# Vue Frontend - Theming System Documentation

**Date**: 2025-10-31
**Status**: ✅ Fully Implemented - Light/Dark Mode Support

---

## Overview

The Vue frontend now uses a comprehensive CSS custom properties (variables) system that automatically adapts to the user's system color scheme preference. All components are theme-aware and will automatically switch between light and dark modes.

---

## How It Works

### Automatic Theme Detection

The theming system uses the CSS `prefers-color-scheme` media query to detect the user's system preference:

- **Dark Mode (Default)**: Used when system is set to dark mode or if no preference is detected
- **Light Mode**: Automatically activated when system prefers light mode

### Color Scheme Declaration

All theme variables are defined in `/frontend/src/style.css`:

```css
:root {
  color-scheme: light dark; /* Declares support for both schemes */

  /* Dark mode variables (default) */
  --color-text-primary: rgba(255, 255, 255, 0.87);
  --color-bg-primary: #242424;
  /* ... */
}

@media (prefers-color-scheme: light) {
  :root {
    /* Light mode overrides */
    --color-text-primary: #213547;
    --color-bg-primary: #f5f5f5;
    /* ... */
  }
}
```

---

## Theme Variables Reference

### Text Colors

| Variable | Dark Mode | Light Mode | Usage |
|----------|-----------|------------|-------|
| `--color-text-primary` | `rgba(255, 255, 255, 0.87)` | `#213547` | Main text |
| `--color-text-secondary` | `rgba(255, 255, 255, 0.6)` | `#666` | Secondary text, labels |
| `--color-text-muted` | `rgba(255, 255, 255, 0.4)` | `#999` | Disabled, hints |

### Background Colors

| Variable | Dark Mode | Light Mode | Usage |
|----------|-----------|------------|-------|
| `--color-bg-primary` | `#242424` | `#f5f5f5` | Page background |
| `--color-bg-secondary` | `#1a1a1a` | `#ffffff` | Secondary surfaces |
| `--color-bg-elevated` | `#2d2d2d` | `#ffffff` | Elevated surfaces, dropdowns |
| `--color-bg-card` | `#2d2d2d` | `#ffffff` | Card backgrounds |
| `--color-bg-input` | `#1a1a1a` | `#ffffff` | Input fields |

### Border Colors

| Variable | Dark Mode | Light Mode | Usage |
|----------|-----------|------------|-------|
| `--color-border` | `rgba(255, 255, 255, 0.1)` | `#ddd` | Default borders |
| `--color-border-focus` | `rgba(255, 255, 255, 0.2)` | `#ccc` | Focus state borders |

### Brand Colors

These remain consistent across themes:

| Variable | Value | Usage |
|----------|-------|-------|
| `--color-primary` | `#667eea` | Primary brand color |
| `--color-primary-dark` | `#5568d3` | Darker variant (hover) |
| `--color-primary-light` | `#7d8ff0` | Lighter variant |
| `--color-secondary` | `#764ba2` | Secondary brand color |

### Status Colors

Base colors remain the same, but backgrounds adjust for contrast:

#### Success (Green)

| Variable | Value | Light Mode Bg | Usage |
|----------|-------|---------------|-------|
| `--color-success` | `#4CAF50` | Same | Success actions |
| `--color-success-dark` | `#45a049` | Same | Hover states |
| `--color-success-light` | `#66bb6a` | Same | Accents |
| `--color-success-bg` | `rgba(76, 175, 80, 0.1)` | `#d4edda` | Success backgrounds |
| `--color-success-border` | `rgba(76, 175, 80, 0.3)` | `#c3e6cb` | Success borders |

#### Warning (Orange)

| Variable | Value | Light Mode Bg | Usage |
|----------|-------|---------------|-------|
| `--color-warning` | `#ff9800` | Same | Warning states |
| `--color-warning-dark` | `#f57c00` | Same | Hover states |
| `--color-warning-light` | `#ffb74d` | Same | Accents |
| `--color-warning-bg` | `rgba(255, 152, 0, 0.1)` | `#fff3cd` | Warning backgrounds |
| `--color-warning-border` | `rgba(255, 152, 0, 0.3)` | `#ffeaa7` | Warning borders |

#### Error (Red)

| Variable | Value | Light Mode Bg | Usage |
|----------|-------|---------------|-------|
| `--color-error` | `#f44336` | Same | Error states |
| `--color-error-dark` | `#d32f2f` | Same | Hover states |
| `--color-error-light` | `#ff6b6b` | Same | Accents |
| `--color-error-bg` | `rgba(244, 67, 54, 0.1)` | `#f8d7da` | Error backgrounds |
| `--color-error-border` | `rgba(244, 67, 54, 0.3)` | `#f5c6cb` | Error borders |

#### Info (Blue)

| Variable | Value | Light Mode Bg | Usage |
|----------|-------|---------------|-------|
| `--color-info` | `#2196F3` | Same | Info states |
| `--color-info-dark` | `#1976D2` | Same | Hover states |
| `--color-info-light` | `#64b5f6` | Same | Accents |
| `--color-info-bg` | `rgba(33, 150, 243, 0.1)` | `#d1ecf1` | Info backgrounds |
| `--color-info-border` | `rgba(33, 150, 243, 0.3)` | `#bee5eb` | Info borders |

### Gradients

| Variable | Value | Usage |
|----------|-------|-------|
| `--gradient-primary` | `linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%)` | Headers, buttons |

### Shadows

Adjust opacity for light mode:

| Variable | Dark Mode | Light Mode | Usage |
|----------|-----------|------------|-------|
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.3)` | `0 1px 3px rgba(0,0,0,0.1)` | Small shadows |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.3)` | `0 4px 6px rgba(0,0,0,0.1)` | Medium shadows |
| `--shadow-lg` | `0 10px 20px rgba(0,0,0,0.4)` | `0 10px 20px rgba(0,0,0,0.15)` | Large shadows |
| `--shadow-xl` | `0 20px 40px rgba(0,0,0,0.5)` | `0 20px 40px rgba(0,0,0,0.2)` | Extra large shadows |

### Typography

| Variable | Value | Usage |
|----------|-------|-------|
| `--font-size-xs` | `12px` | Very small text |
| `--font-size-sm` | `14px` | Small text, labels |
| `--font-size-base` | `16px` | Body text |
| `--font-size-lg` | `18px` | Large text |
| `--font-size-xl` | `24px` | Headings |
| `--font-size-2xl` | `32px` | Large headings, stats |

### Spacing

| Variable | Value | Usage |
|----------|-------|-------|
| `--spacing-xs` | `4px` | Tiny gaps |
| `--spacing-sm` | `8px` | Small gaps |
| `--spacing-md` | `16px` | Medium gaps |
| `--spacing-lg` | `24px` | Large gaps |
| `--spacing-xl` | `32px` | Extra large gaps |

### Border Radius

| Variable | Value | Usage |
|----------|-------|-------|
| `--radius-sm` | `4px` | Small radius |
| `--radius-md` | `6px` | Medium radius |
| `--radius-lg` | `8px` | Large radius |
| `--radius-xl` | `12px` | Extra large radius (cards) |

---

## Usage Examples

### In Vue Components

```vue
<style scoped>
.my-component {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
}

.my-button {
  background: var(--gradient-primary);
  color: white;
  font-size: var(--font-size-base);
  padding: var(--spacing-sm) var(--spacing-lg);
}

.success-message {
  background: var(--color-success-bg);
  color: var(--color-success-dark);
  border: 1px solid var(--color-success-border);
}
</style>
```

### Status-Specific Styling

```vue
<style scoped>
.item-expiring-soon {
  border-left: 4px solid var(--color-warning);
  background: var(--color-warning-bg);
}

.item-expired {
  border-left: 4px solid var(--color-error);
  color: var(--color-error);
}

.item-success {
  background: var(--color-success-bg);
  border: 1px solid var(--color-success-border);
}
</style>
```

---

## Testing Theme Modes

### On macOS

1. **System Preferences** → **General** → **Appearance**
2. Select "Dark" or "Light"
3. Vue app will automatically switch

### On Windows

1. **Settings** → **Personalization** → **Colors**
2. Choose "Dark" or "Light" mode
3. Vue app will automatically switch

### On Linux (GNOME)

1. **Settings** → **Appearance**
2. Toggle **Dark Style**
3. Vue app will automatically switch

### Browser DevTools Testing

**Chrome/Edge**:
1. Open DevTools (F12)
2. Press Ctrl+Shift+P (Cmd+Shift+P on Mac)
3. Type "Rendering"
4. Select "Emulate CSS media feature prefers-color-scheme"
5. Choose "prefers-color-scheme: dark" or "light"

**Firefox**:
1. Open DevTools (F12)
2. Click the settings gear icon
3. Scroll to "Inspector"
4. Toggle "Disable prefers-color-scheme media queries"

---

## Components Using Theme Variables

All components have been updated to use theme variables:

✅ **App.vue**
- Header gradient
- Footer styling
- Tab navigation

✅ **InventoryList.vue**
- All cards and backgrounds
- Status colors (success/warning/error)
- Form inputs and labels
- Buttons and actions
- Upload areas
- Loading spinners

✅ **ReceiptsView.vue**
- Upload area
- Receipt cards
- Status indicators
- Stats display

✅ **EditItemModal.vue**
- Modal background
- Form fields
- Expiration date color coding
- Buttons

---

## Best Practices

### DO ✅

1. **Always use theme variables** instead of hardcoded colors
   ```css
   /* Good */
   color: var(--color-text-primary);

   /* Bad */
   color: #333;
   ```

2. **Use semantic variable names**
   ```css
   /* Good */
   background: var(--color-bg-card);

   /* Bad */
   background: var(--color-bg-elevated); /* Wrong semantic meaning */
   ```

3. **Use spacing variables** for consistency
   ```css
   /* Good */
   padding: var(--spacing-lg);

   /* Bad */
   padding: 24px;
   ```

4. **Use status colors appropriately**
   ```css
   /* Good - Expiration warning */
   .expiring { color: var(--color-warning); }

   /* Bad - Using error for warning */
   .expiring { color: var(--color-error); }
   ```

### DON'T ❌

1. **Don't hardcode colors**
   ```css
   /* Bad */
   background: #ffffff;
   color: #333333;
   ```

2. **Don't use pixel values for spacing**
   ```css
   /* Bad */
   margin: 16px;

   /* Good */
   margin: var(--spacing-md);
   ```

3. **Don't mix theme and non-theme styles**
   ```css
   /* Bad */
   .card {
     background: var(--color-bg-card);
     border: 1px solid #ddd; /* Hardcoded! */
   }

   /* Good */
   .card {
     background: var(--color-bg-card);
     border: 1px solid var(--color-border);
   }
   ```

---

## Adding New Theme Variables

If you need to add new theme variables:

1. **Add to dark mode (default)** in `:root`:
   ```css
   :root {
     --color-my-new-color: #value;
   }
   ```

2. **Add light mode override** in media query:
   ```css
   @media (prefers-color-scheme: light) {
     :root {
       --color-my-new-color: #different-value;
     }
   }
   ```

3. **Use in components**:
   ```css
   .my-element {
     color: var(--color-my-new-color);
   }
   ```

---

## Future Enhancements

Potential additions to the theming system:

1. **Manual Theme Toggle**
   - Add a theme switcher button
   - Store preference in localStorage
   - Override system preference

2. **Custom Color Schemes**
   - Allow users to choose accent colors
   - Save theme preferences per user

3. **High Contrast Mode**
   - Support `prefers-contrast: high`
   - Increase border widths and color differences

4. **Reduced Motion**
   - Support `prefers-reduced-motion`
   - Disable animations for accessibility

---

## Browser Support

The theming system is supported in:

✅ **Chrome/Edge**: 76+
✅ **Firefox**: 67+
✅ **Safari**: 12.1+
✅ **Opera**: 62+

CSS Custom Properties (Variables) are supported in all modern browsers.

---

## Summary

**What We Have**:
- ✅ Automatic light/dark mode detection
- ✅ Comprehensive variable system (50+ variables)
- ✅ All components are theme-aware
- ✅ Semantic, maintainable color system
- ✅ Consistent spacing, typography, and shadows
- ✅ Status colors with proper contrast in both modes

**Benefits**:
- 🎨 Consistent design across the entire app
- 🌓 Automatic theme switching based on system preference
- 🔧 Easy to maintain and update colors globally
- ♿ Better accessibility with proper contrast ratios
- 🚀 Future-proof for theme customization

**The Vue frontend now fully supports light and dark modes! 🎉**
