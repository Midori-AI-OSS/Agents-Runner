# Animation System Documentation

This document describes the animation enhancements added to the Agents Runner UI.

## Overview

The application now includes smooth animations and visual feedback throughout the interface to create a more polished, professional feel.

## Key Features

### 1. Page Transitions
- **Cross-fade animations** when switching between Dashboard, New Task, Environments, Settings, and Task Details
- Duration: 200ms with smooth easing
- Implemented in `_MainWindowNavigationMixin._transition_to_page()`

### 2. Interactive Element Feedback

#### Buttons
- **Navigation buttons** (QToolButton): Glow effect on hover with cyan accent
- **Action buttons** (QPushButton): Enhanced hover brightness and border highlighting
- Smooth transitions between states

#### Input Fields
- **Text inputs and text areas**: Cyan border glow on hover/focus
- **ComboBox dropdowns**: Highlighted on hover with smooth color transitions
- Enhanced visual feedback for user interaction

#### Checkboxes
- **Hover effects**: Subtle border color change
- **Check state**: Smooth color transition when toggled
- Available animated version: `AnimatedCheckBox` widget with progress animation

#### Tabs
- **Hover state**: Cyan accent highlighting
- **Selected state**: Brighter cyan background
- Smooth color transitions

#### Scrollbars
- **Hover effect**: Cyan highlight on scrollbar handle
- **Press effect**: Brighter cyan when dragging

### 3. Custom Widgets

All custom animated widgets are available in `agents_runner/widgets/`:

- **`AnimatedCheckBox`**: Checkbox with smooth check/uncheck animation
- **`AnimatedPushButton`**: Button with scale animation on hover/press
- **`AnimatedToolButton`**: Tool button with glow effect
- **`SmoothScrollArea`**: Scroll area with animated scrolling
- **`GlassCard`**: Enhanced with optional entrance fade-in animation

### 4. Animation Utilities

The `agents_runner/ui/animations.py` module provides reusable animation helpers:

```python
from agents_runner.ui.animations import (
    fade_in,
    fade_out,
    cross_fade,
    slide_fade_in,
    staggered_fade_in,
    AnimationPresets,
)

# Fade in a widget
anim = fade_in(my_widget, duration=250)
anim.start()

# Cross-fade between two widgets
anim = cross_fade(old_widget, new_widget)
anim.start()

# Staggered fade-in for multiple items
widgets = [card1, card2, card3]
anim = staggered_fade_in(widgets, stagger_delay=50)
anim.start()
```

## Color Scheme

The animation system uses the existing color palette with cyan accent:
- **Primary accent**: `rgba(56, 189, 248, *)` - Cyan
- **Success**: `rgba(16, 185, 129, *)` - Green
- **Background**: `rgba(18, 20, 28, *)` - Dark blue-gray
- **Borders**: `rgba(255, 255, 255, *)` - White with varying alpha

## Performance

All animations are:
- Hardware-accelerated where possible
- Short duration (150-350ms) for responsiveness
- Use efficient Qt animation framework
- Non-blocking (async)

## Design Constraints

As per project guidelines:
- **Sharp corners only** - No rounded borders (border-radius: 0px)
- **Minimal diffs** - Changes focused on animation/polish only
- **Consistent style** - Follows existing visual language

## Future Enhancements

Potential improvements:
1. Loading state animations for async operations
2. Micro-interactions for list items
3. Toast/notification animations
4. Progress indicator animations
5. Expandable/collapsible section animations

## Testing

To test animations locally:
```bash
uv run main.py
```

Navigate between pages, hover over buttons, interact with form fields to see the animations in action.
