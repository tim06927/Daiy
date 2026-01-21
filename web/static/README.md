# Frontend Architecture

This document describes the modular frontend architecture in `/web/static/`.

## Overview

The frontend is organized into separate CSS and JavaScript modules for maintainability, with a clean HTML template that references external assets:

- **3 CSS files** - ~1190 lines organized by concern
- **7 JavaScript modules** - ~1107 lines with clear responsibilities
- **1 HTML template** - 154 lines of semantic markup

## Directory Structure

```
web/
├── static/
│   ├── css/
│   │   ├── base.css           # Variables, resets, layout, header (230 lines)
│   │   ├── components.css     # Buttons, forms, clarification UI (614 lines)
│   │   └── products.css       # Product cards, categories, alternatives (346 lines)
│   └── js/
│       ├── config.js          # Application constants (27 lines)
│       ├── state.js           # Reactive state management (97 lines)
│       ├── image.js           # Image upload & compression (137 lines)
│       ├── api.js             # Backend communication (59 lines)
│       ├── clarification.js   # Clarification UI rendering (251 lines)
│       ├── products.js        # Product display logic (321 lines)
│       └── main.js            # Application initialization (215 lines)
└── templates/
    └── index.html             # Clean HTML structure (154 lines)
```

## Architecture Principles

1. **Separation of Concerns** - CSS handles presentation, JavaScript handles logic, HTML provides structure
2. **Single Responsibility** - Each module has one clear purpose
3. **Dependency Management** - Scripts load in dependency order
4. **State Centralization** - `AppState` object manages all application state
5. **Progressive Enhancement** - Core functionality works, enhancements layer on top

## Module Documentation

### CSS Modules

#### `base.css` - Foundation Styles
**Purpose:** Core variables, resets, and layout structure  
**Contents:**
- CSS custom properties (color palette, shadows, border radii)
- Global resets (`*, body`)
- Header and navigation
- Layout containers (`.app-container`, `.split-panel`)
- Initial and results state layouts
- Responsive grid system
- Animation keyframes (`@keyframes spin`)

**Key Classes:**
- `.header`, `.logo`, `.nav` - Site header
- `.initial-state`, `.results-state` - Main layout states
- `.split-panel`, `.query-panel`, `.results-panel` - Results layout
- `.hero-section`, `.disclaimer` - Initial state content

#### `components.css` - Interactive Elements
**Purpose:** Reusable UI components and controls  
**Contents:**
- Tab navigation (`.tab-selector`, `.results-tabs`)
- Search box and input controls
- Image upload and preview
- Buttons (upload, search, clarification submit)
- Clarification panel layout
- Loading spinners
- Error messages
- Instructions display

**Key Classes:**
- `.search-box-initial`, `.search-input-initial`, `.search-btn-initial`
- `.upload-btn-initial`, `.image-preview-initial`
- `.clarification-panel`, `.clarification-section`, `.option-btn`
- `.loading-state`, `.loading-spinner`
- `.error-message`

#### `products.css` - Product Display
**Purpose:** Product-specific UI elements  
**Contents:**
- Product category sections
- Product cards (primary and alternative)
- Product images with fallback icons
- Price tags and action buttons
- Alternatives toggle/expand
- Responsive product layouts

**Key Classes:**
- `.product-section`, `.category-section`
- `.product-card`, `.product-image`, `.product-info`, `.product-actions`
- `.alt-product-card` - Compact alternative products
- `.alternatives-toggle`, `.alternatives-list`
- `.best-badge` - "Best" product indicator

### JavaScript Modules

#### `config.js` - Constants
**Purpose:** Centralized configuration  
**Dependencies:** None  
**Exports:** `CONFIG` object

**Contents:**
```javascript
CONFIG = {
  API: { RECOMMEND: '/api/recommend' },
  IMAGE: { MAX_SIZE: 960, JPEG_QUALITY: 0.8 },
  UI: { MAX_TEXTAREA_HEIGHT: 150 }
}
```

#### `state.js` - State Management
**Purpose:** Application state and business logic  
**Dependencies:** None  
**Exports:** `AppState` object

**State Properties:**
- `selectedValues` - Generic clarification storage
- `compressedImage`, `imageDataUrl` - Image state
- `currentQuery`, `cachedJob` - Query state
- `pendingClarifications`, `clarificationAnswers` - Clarification tracking

**Methods:**
- `reset()` - Clear all state
- `setSelectedValue(dimension, value)` - Update clarification
- `getAllSelectedValues()` - Get complete selected values
- `getClarificationAnswers()` - Format for API
- `areAllClarificationsAnswered()` - Check completion

#### `image.js` - Image Handling
**Purpose:** Image upload, compression, and preview  
**Dependencies:** `CONFIG`, `AppState`  
**Exports:** Functions for image processing

**Key Functions:**
- `compressImage(file)` - Compress to base64, max 960px, 70-80% quality
- `formatFileSize(bytes)` - Human-readable file sizes
- `initImageHandlers(elements)` - Set up upload/preview listeners
- `triggerUploadInResults()` - Trigger upload from results view

**Features:**
- Canvas-based image compression
- Maintains aspect ratio
- Stores both display URL and compressed base64

#### `api.js` - Backend Communication
**Purpose:** API calls to Flask backend  
**Dependencies:** `CONFIG`, `AppState`  
**Exports:** `fetchRecommendations()`

**Key Functions:**
- `fetchRecommendations(problemText)` - POST to `/api/recommend`
  - Sends clarification answers in new format
  - Caches job identification

**Error Handling:**
- HTTP error detection
- JSON parsing fallback
- User-friendly error messages

#### `clarification.js` - Clarification UI
**Purpose:** Render and manage clarification questions  
**Dependencies:** `AppState`, `handleSearch` (from main.js)  
**Exports:** Clarification UI functions

**Key Functions:**
- `showClarification(data)` - Render clarification panel with questions
- `selectDimension(dim, value, btn)` - Handle option selection
- `showOtherInputGeneric(dim, btn)` - Show custom text input
- `updateSelectedOptions()` - Update left panel chips
- `updateSubmitButton()` - Show/hide submit button based on answers
- `submitClarifications()` - Submit answers and trigger new search

#### `products.js` - Product Rendering
**Purpose:** Render product lists and instructions  
**Dependencies:** None  
**Exports:** Product display functions

**Key Functions:**
- `buildProductImage(product, icon)` - Generate image HTML with fallback
- `createProductCard(product, isBest, icon)` - Primary product card
- `createAltProductCard(product, icon)` - Alternative product card
- `renderProductCategories(...)` - Render all product sections
- `renderInstructions(sections, finalInstructions)` - Render instructions tab
- `setupResultsTabs()` - Initialize Products/Instructions tabs
- `escapeHtml(value)` - XSS protection

**Features:**
- Lazy loading images
- Fallback icons when no image
- Category metadata mapping

#### `main.js` - Application Control
**Purpose:** Initialize app and orchestrate workflow  
**Dependencies:** All other modules  
**Exports:** Core application functions

**Key Functions:**
- `initApp()` - Main initialization (called on DOM ready)
- `initElements()` - Cache DOM element references
- `initEventListeners()` - Set up search, keyboard, resize handlers
- `handleSearch()` - Search submission and API orchestration
- `showResults(data)` - Display recommendation results
- `showError(message)` - Display error state
- `switchToResultsState()` - Transition to results view
- `resetToInitial()` - Return to search state

**Flow Control:**
- Manages state transitions
- Coordinates between modules
- Handles loading states

## Load Order & Dependencies

Scripts load in dependency order at the end of `<body>`:

```html
<script src="/static/js/config.js"></script>       <!-- 1. Constants -->
<script src="/static/js/state.js"></script>        <!-- 2. State -->
<script src="/static/js/image.js"></script>        <!-- 3. Image (uses config, state) -->
<script src="/static/js/api.js"></script>          <!-- 4. API (uses config, state) -->
<script src="/static/js/clarification.js"></script> <!-- 5. Clarification (uses state) -->
<script src="/static/js/products.js"></script>     <!-- 6. Products -->
<script src="/static/js/main.js"></script>         <!-- 7. Main (uses all) -->
```

**Dependency Graph:**
```
config.js (no deps)
    ↓
state.js (no deps)
    ↓
image.js ← config, state
    ↓
api.js ← config, state
    ↓
clarification.js ← state, handleSearch (from main)
    ↓
products.js (no deps)
    ↓
main.js ← all modules
```

## Data Flow

### Search → Results Flow

```
1. User Input
   ↓
2. main.js::handleSearch()
   ↓
3. api.js::fetchRecommendations()
   ↓
4. Backend API Response
   ↓
5. Decision Point:
   ├─ need_clarification? → clarification.js::showClarification()
   │                         ↓
   │                       User Answers → Back to step 2
   │
   └─ has results? → main.js::showResults()
                      ↓
                    products.js::renderProductCategories()
                    products.js::renderInstructions()
```

### State Flow

```
AppState (state.js)
    ↓
Read by: api.js, clarification.js, image.js
    ↓
Updated by: User actions, API responses
    ↓
Displayed by: clarification.js (chips), products.js (results)
```

## Development Guide

### Making Changes

**CSS Changes:**
1. Identify which module handles the component (base/components/products)
2. Edit the appropriate CSS file
3. Hard refresh browser (Ctrl+Shift+R) to bypass cache

**JavaScript Changes:**
1. Identify the responsible module based on functionality
2. Edit the module file
3. Check dependencies - changes may affect other modules
4. Hard refresh browser to load new code

**HTML Changes:**
1. Edit `web/templates/index.html`
2. Flask auto-reloads templates in debug mode (no restart needed)

### Adding New Features

**New UI Component:**
1. Add CSS to appropriate module (typically `components.css`)
2. Add rendering logic to relevant JS module
3. Update `main.js` if initialization is needed

**New API Endpoint:**
1. Add endpoint constant to `config.js::CONFIG.API`
2. Add fetch function to `api.js`
3. Update calling code in relevant module

**New State Variable:**
1. Add property to `AppState` in `state.js`
2. Add getter/setter methods if needed
3. Update reset logic in `AppState.reset()`

### Debugging Tips

- **Console Errors:** Check browser console for module load errors
- **State Inspection:** Access `AppState` object in browser console: `AppState.selectedValues`
- **Network Monitoring:** Use DevTools Network tab to inspect API calls
- **Breakpoints:** Set breakpoints in specific module files for step debugging
- **Logging:** Add `console.log()` statements in modules (remove before commit)

## Performance Considerations

- **CSS Non-Blocking:** External stylesheets load asynchronously
- **JS at End:** Scripts don't block initial HTML render
- **Image Lazy Loading:** Product images use `loading="lazy"` attribute
- **Compression:** Images compressed to ~70% quality, max 960px
- **Caching:** Browser can cache individual module files

## Browser Compatibility

- **Target Browsers:** Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **ES6 Features:** async/await, arrow functions, destructuring, template literals
- **CSS Features:** Grid, Flexbox, custom properties (`:root` variables)
- **No Polyfills:** IE11 not supported

## Testing

### Manual Testing Checklist

After making changes, verify:

- [ ] Initial search page loads without errors
- [ ] Image upload and compression works
- [ ] Search submission shows loading state
- [ ] Clarification panel renders correctly
- [ ] All clarification options are clickable
- [ ] "Other" input fields work
- [ ] Submit button appears when all questions answered
- [ ] Product cards display with images (or fallback icons)
- [ ] Alternatives toggle expands/collapses
- [ ] Instructions tab switches correctly
- [ ] "Edit query" button resets to initial state
- [ ] Responsive layout works on mobile (< 600px)
- [ ] No console errors in DevTools

### Automated Testing

Run backend tests to ensure API endpoints still work:
```bash
pytest web/tests/ -v
```

## Common Issues

### Styles Not Updating
- Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
- Check browser DevTools → Network tab for 304 (cached) vs 200 (fresh)
- Clear browser cache if persistent

### JavaScript Errors
- Check console for module load failures
- Verify script tags in correct order in `index.html`
- Check for typos in `url_for('static', ...)` paths

### Images Not Showing
- Check `image_url` field in product data
- Verify image URLs are absolute (not relative)
- Check browser Network tab for 404 errors on images
- Verify `buildProductImage()` logic in `products.js`

## Future Enhancements

Potential improvements for this architecture:

1. **Build System** - Webpack/Vite for bundling and minification
2. **TypeScript** - Add type safety to JavaScript modules
3. **CSS Preprocessor** - SASS/SCSS for variables, mixins, nesting
4. **Component Library** - Extract reusable components (buttons, cards, forms)
5. **Unit Testing** - Jest tests for JavaScript modules
6. **ES Modules** - Convert to `import/export` instead of globals
7. **State Library** - Replace `AppState` with Zustand or similar
8. **Framework** - Consider lightweight framework like Preact for complex UI

## Resources

- [Flask Static Files](https://flask.palletsprojects.com/en/2.3.x/tutorial/static/)
- [CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
- [JavaScript Modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)
- [Responsive Web Design](https://web.dev/responsive-web-design-basics/)
