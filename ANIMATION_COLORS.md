# Animation Color Reference

This document provides a quick reference for the colors used in the animation system.

## Primary Colors

### Cyan Accent (Primary Interactive)
- **Base**: `rgba(56, 189, 248, *)` - `#38BDF8`
- **Usage**: Hover states, focus borders, active elements
- **Variants**:
  - Light hover: `rgba(56, 189, 248, 30)` - 12% opacity
  - Medium hover: `rgba(56, 189, 248, 60)` - 24% opacity
  - Focus border: `rgba(56, 189, 248, 120)` - 47% opacity
  - Scrollbar hover: `rgba(56, 189, 248, 100)` - 39% opacity

### Green Success
- **Base**: `rgba(16, 185, 129, *)` - `#10B981`
- **Usage**: Checkboxes (checked state), success indicators
- **Variants**:
  - Checked: `rgba(16, 185, 129, 165)` - 65% opacity
  - Hover checked: `rgba(16, 185, 129, 195)` - 76% opacity

### Dark Background
- **Base**: `rgba(18, 20, 28, *)` - `#12141C`
- **Usage**: Input backgrounds, cards, overlays
- **Variants**:
  - Input base: `rgba(18, 20, 28, 190)` - 75% opacity
  - Input hover: `rgba(18, 20, 28, 205)` - 80% opacity
  - Input focus: `rgba(18, 20, 28, 225)` - 88% opacity

### White Accents
- **Base**: `rgba(255, 255, 255, *)`
- **Usage**: Borders, text, subtle highlights
- **Variants**:
  - Subtle border: `rgba(255, 255, 255, 22)` - 9% opacity
  - Border hover: `rgba(255, 255, 255, 35)` - 14% opacity

## State Colors

### Button States
- **Default**: `rgba(18, 20, 28, 135)` background
- **Hover**: `rgba(56, 189, 248, 30)` background, cyan border
- **Pressed**: `rgba(56, 189, 248, 70)` background
- **Focus**: `rgba(56, 189, 248, 80)` border

### Input States
- **Default**: `rgba(255, 255, 255, 22)` border
- **Hover**: `rgba(56, 189, 248, 50)` border
- **Focus**: `rgba(56, 189, 248, 120)` border

### Tab States
- **Default**: `rgba(18, 20, 28, 135)` background
- **Hover**: `rgba(56, 189, 248, 25)` background
- **Selected**: `rgba(56, 189, 248, 75)` background
- **Selected+Hover**: `rgba(56, 189, 248, 90)` background

## Animation Timing

All animations use consistent easing curves from `AnimationPresets`:
- **EASE_IN_OUT**: `QEasingCurve.Type.InOutCubic` - Smooth start and end
- **EASE_OUT**: `QEasingCurve.Type.OutCubic` - Quick start, smooth end
- **EASE_IN**: `QEasingCurve.Type.InCubic` - Smooth start, quick end
- **EASE_BOUNCE**: `QEasingCurve.Type.OutBack` - Slight overshoot effect

## Design Notes

1. **Consistency**: All interactive elements use cyan (`#38BDF8`) as the primary accent
2. **Hierarchy**: Opacity values create visual hierarchy without additional colors
3. **Accessibility**: Sufficient contrast maintained at all states
4. **Performance**: RGBA values are hardware-accelerated by Qt
5. **Sharp aesthetics**: 0px border-radius maintained throughout
