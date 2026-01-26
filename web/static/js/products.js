/**
 * Product rendering and display logic
 * Note: Depends on utils.js for escapeHtml and createHelpTooltip functions
 */

/**
 * Build product image HTML with fallback icon
 */
function buildProductImage(product, icon) {
  const imageUrl = product.image_url;
  const safeAlt = escapeHtml(product.name || 'Product image');
  const safeIcon = escapeHtml(icon || '📦');
  const hasImageClass = imageUrl ? ' has-image' : '';
  const imgTag = imageUrl
    ? `<img src="${escapeHtml(imageUrl)}" alt="${safeAlt}" loading="lazy" onload="this.closest('.product-image')?.classList.add('has-image')" onerror="this.closest('.product-image')?.classList.remove('has-image')" />`
    : '';

  return `
    <div class="product-image${hasImageClass}">
      <span class="product-icon">${safeIcon}</span>
      ${imgTag}
    </div>
  `;
}

/**
 * Category metadata mapping
 */
const categoryMeta = {
  'drivetrain_cassettes': { name: 'Cassette', icon: '⚙️' },
  'drivetrain_chains': { name: 'Chain', icon: '⛓️' },
  'drivetrain_tools': { name: 'Tools', icon: '🔧' },
  'drivetrain_pedals': { name: 'Pedals', icon: '🦶' },
  'drivetrain_cranks': { name: 'Crankset', icon: '⚙️' },
  'drivetrain_chainrings': { name: 'Chainring', icon: '⚙️' },
  'lighting_bicycle_lights_battery': { name: 'Battery Light', icon: '💡' },
  'lighting_bicycle_lights_dynamo': { name: 'Dynamo Light', icon: '💡' },
  'cassettes': { name: 'Cassette', icon: '⚙️' },
  'chains': { name: 'Chain', icon: '⛓️' },
  'mtb_gloves': { name: 'Gloves', icon: '🧤' },
};

/**
 * Escape a string for safe inclusion in a single-quoted JS string literal (e.g. inline onclick).
 */
function jsStringEscape(str) {
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, '\\\'')
    .replace(/\r?\n/g, '\\n');
}

/**
 * Create a product card element
 */
function createProductCard(product, isBest, icon) {
  const card = document.createElement('a');
  card.className = 'product-card' + (isBest ? ' best' : '');
  card.href = product.url || '#';
  card.target = '_blank';
  card.rel = 'noopener noreferrer';
  
  const specs = [product.brand, product.application].filter(Boolean).join(' · ');
  const imageMarkup = buildProductImage(product, icon);
  const safeName = escapeHtml(product.name || 'Product');
  const safePrice = escapeHtml(product.price || '');
  const safeSpecs = escapeHtml(specs);
  const addToCartName = jsStringEscape(product.name || '');
  
  // Create tooltip for "why it fits" if available
  const whyItFits = product.why_it_fits || '';
  const tooltipHtml = whyItFits ? createHelpTooltip(whyItFits, 'Why') : '';
  
  card.innerHTML = `
    ${imageMarkup}
    <div class="product-info">
      <div class="product-name">
        ${safeName}
        ${isBest ? '<span class="best-badge">Best</span>' : ''}
        ${tooltipHtml}
      </div>
      <div class="product-specs">${safeSpecs}</div>
    </div>
    <div class="product-actions">
      <div class="product-price">${safePrice}</div>
      <button class="add-to-cart-btn" onclick="event.preventDefault(); event.stopPropagation(); addToCart('${addToCartName}')">
        Add to Cart
      </button>
    </div>
  `;
  
  return card;
}

/**
 * Create an alternative product card element
 */
function createAltProductCard(product, icon) {
  const card = document.createElement('a');
  card.className = 'alt-product-card';
  card.href = product.url || '#';
  card.target = '_blank';
  card.rel = 'noopener noreferrer';
  
  const imageMarkup = buildProductImage(product, icon);
  const safeName = escapeHtml(product.name || 'Product');
  const safePrice = escapeHtml(product.price || '');
  const addToCartName = jsStringEscape(product.name || '');
  
  // Create tooltip for "why it fits" if available
  const whyItFits = product.why_it_fits || '';
  const tooltipHtml = whyItFits ? createHelpTooltip(whyItFits) : '';
  
  card.innerHTML = `
    ${imageMarkup}
    <div class="product-info">
      <div class="product-name">${safeName}${tooltipHtml}</div>
    </div>
    <div class="product-actions">
      <div class="product-price">${safePrice}</div>
      <button class="add-to-cart-btn" onclick="event.preventDefault(); event.stopPropagation(); addToCart('${addToCartName}')">
        Add
      </button>
    </div>
  `;
  
  return card;
}

/**
 * Render a product section (primary, tools, optional)
 */
function renderSection(products, sectionTitle, sectionClass, showReason = false) {
  if (!products || products.length === 0) return null;
  
  const categoriesContainer = document.getElementById('categories-container');
  
  const sectionDiv = document.createElement('div');
  sectionDiv.className = `product-section ${sectionClass}`;
  
  if (sectionTitle) {
    const sectionHeader = document.createElement('div');
    sectionHeader.className = 'section-header';
    sectionHeader.innerHTML = `<h3>${sectionTitle}</h3>`;
    sectionDiv.appendChild(sectionHeader);
  }
  
  products.forEach((item) => {
    // New format has {category, category_display, product, reasoning}
    const categoryKey = item.category;
    const categoryDisplay = item.category_display || item.category;
    const product = item.product;
    const reasoning = item.reasoning;
    
    const meta = categoryMeta[categoryKey] || { name: categoryDisplay || 'Products', icon: '📦' };
    
    const section = document.createElement('div');
    section.className = 'category-section';
    
    const header = document.createElement('div');
    header.className = 'category-header';
    
    // Create category name with optional tooltip for reasoning
    let headerContent = `<span class="category-name">${meta.icon} ${escapeHtml(meta.name)}</span>`;
    if (showReason && reasoning) {
      headerContent += createHelpTooltip(reasoning, 'Why');
    }
    header.innerHTML = headerContent;
    section.appendChild(header);
    
    const productsDiv = document.createElement('div');
    productsDiv.className = 'category-products';
    
    // Add product with reasoning
    if (product) {
      const productWithReasoning = {
        ...product,
        why_it_fits: reasoning || product.why_it_fits || 'Compatible with your setup.'
      };
      const bestCard = createProductCard(productWithReasoning, true, meta.icon);
      productsDiv.appendChild(bestCard);
    }
    
    section.appendChild(productsDiv);
    sectionDiv.appendChild(section);
  });
  
  categoriesContainer.appendChild(sectionDiv);
}

/**
 * Render all product categories
 */
function renderProductCategories(categories, sections, primaryProducts, optionalProducts, toolProducts) {
  const categoriesContainer = document.getElementById('categories-container');
  categoriesContainer.innerHTML = '';
  
  // Render new structured format
  renderSection(primaryProducts, '🛠️ Primary Parts & Accessories', 'primary-products');
  renderSection(toolProducts, '🔧 Tools for This Job', 'tool-products', true);
  renderSection(optionalProducts, '💡 Optional Extras', 'optional-products', true);
}

/**
 * Render instructions tab content
 */
function renderInstructions(sections, finalInstructions, recipe = null) {
  const container = document.getElementById('instructions-content');
  container.innerHTML = '';
  
  // Prefer recipe format if available
  if (recipe && recipe.ingredients && recipe.steps) {
    const recipeSection = document.createElement('div');
    recipeSection.className = 'recipe-section';
    
    // Render ingredients as a list
    if (recipe.ingredients.length > 0) {
      const ingredientsSection = document.createElement('div');
      ingredientsSection.className = 'ingredients-section';
      ingredientsSection.innerHTML = `
        <h4>📋 Ingredients (Parts & Tools)</h4>
        <ul class="ingredients-list">
          ${recipe.ingredients.map(ing => {
            const typeEmoji = {
              'part': '📦',
              'tool': '🔧',
              'product': '🛒'
            }[ing.type] || '•';
            return `<li><span class="ingredient-type">${typeEmoji}</span> <span class="ingredient-name">${escapeHtml(ing.name)}</span></li>`;
          }).join('')}
        </ul>
      `;
      recipeSection.appendChild(ingredientsSection);
    }
    
    // Render steps
    if (recipe.steps.length > 0) {
      const stepsSection = document.createElement('div');
      stepsSection.className = 'instructions-section';
      stepsSection.innerHTML = `
        <h4>🔧 Step-by-Step Instructions</h4>
        <ol class="instruction-steps">
          ${recipe.steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}
        </ol>
      `;
      recipeSection.appendChild(stepsSection);
    }
    
    container.appendChild(recipeSection);
    return;
  }
  
  // Fall back to final_instructions format
  const workflow = finalInstructions.length > 0 
    ? finalInstructions 
    : (sections.suggested_workflow || []);
  const checklist = sections.checklist || [];
  
  if (workflow.length > 0) {
    const workflowSection = document.createElement('div');
    workflowSection.className = 'instructions-section';
    workflowSection.innerHTML = `
      <h4>🔧 Step-by-Step Instructions</h4>
      <ol class="instruction-steps">${workflow.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ol>
    `;
    container.appendChild(workflowSection);
  }
  
  if (checklist.length > 0) {
    const checklistSection = document.createElement('div');
    checklistSection.className = 'instructions-section';
    checklistSection.innerHTML = `
      <h4>✅ Checklist</h4>
      <ul>${checklist.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
    `;
    container.appendChild(checklistSection);
  }
  
  if (workflow.length === 0 && checklist.length === 0) {
    container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.8rem;">No instructions available.</p>';
  }
}

/**
 * Setup results tabs (Products/Instructions)
 */
function setupResultsTabs() {
  const tabs = document.querySelectorAll('.results-tab');
  const productsTab = document.getElementById('products-tab');
  const instructionsTab = document.getElementById('instructions-tab');
  
  // Reset to products tab
  tabs.forEach(t => t.classList.remove('active'));
  tabs[0].classList.add('active');
  productsTab.classList.add('active');
  instructionsTab.classList.remove('active');
  
  tabs.forEach(tab => {
    tab.onclick = () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      if (tab.dataset.tab === 'products') {
        productsTab.classList.add('active');
        instructionsTab.classList.remove('active');
      } else {
        productsTab.classList.remove('active');
        instructionsTab.classList.add('active');
      }
    };
  });
}

/**
 * Placeholder cart function
 */
function addToCart(productName) {
  alert(`Added "${productName}" to cart! (Demo)`);
}
