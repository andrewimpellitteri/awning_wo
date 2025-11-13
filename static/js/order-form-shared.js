/**
 * Shared JavaScript functionality for Work Order and Repair Order forms
 * This provides DRY code for common operations
 */

// Global counters
let newItemCounter = 0;
let selectedItemsCount = 0;
let newItemsCount = 0;

// Global flag to determine if we're on a repair order form (set by page)
let isRepairOrder = false;

/**
 * Get inventory keys of items currently in the order
 * @returns {Set} Set of inventory keys
 */
function getExistingItemInventoryKeys() {
    const keys = new Set();

    // 1. Get inventory keys from original existing items (already in the work order)
    const existingItems = document.querySelectorAll('input[type="checkbox"][name="existing_item_id[]"][data-inventory-key]');
    existingItems.forEach(checkbox => {
        if (checkbox.checked) {
            const inventoryKey = checkbox.getAttribute('data-inventory-key') || checkbox.dataset.inventoryKey;
            if (inventoryKey && inventoryKey.trim() !== '') {
                keys.add(inventoryKey);
            }
        }
    });

    // 2. Get inventory keys from temp items (newly added from history)
    const tempItems = document.querySelectorAll('input[type="checkbox"][name="existing_item_id_temp[]"][data-inventory-key]');
    tempItems.forEach(checkbox => {
        if (checkbox.checked) {
            const inventoryKey = checkbox.getAttribute('data-inventory-key') || checkbox.dataset.inventoryKey;
            if (inventoryKey && inventoryKey.trim() !== '') {
                keys.add(inventoryKey);
            }
        }
    });

    // 3. Get inventory keys from newly selected items still in customer history
    // (These are items that are checked but haven't been moved to existing items yet)
    const selectedInventoryItems = document.querySelectorAll('input[type="checkbox"][name="selected_items[]"]:checked');
    selectedInventoryItems.forEach(checkbox => {
        const inventoryKey = checkbox.value;
        if (inventoryKey && inventoryKey.trim() !== '') {
            keys.add(inventoryKey);
        }
    });

    return keys;
}

/**
 * Get existing items in the order by their attributes (for items without InventoryKey)
 * Issue #177: Items without InventoryKey should still be filtered out from Customer History
 * @returns {Array} Array of item attribute objects
 */
function getExistingItemsByAttributes() {
    const items = [];
    const existingItemsContainer = document.getElementById('existing-items');
    if (!existingItemsContainer) return items;

    // Get all checked existing items (both original and temp)
    const checkboxes = existingItemsContainer.querySelectorAll('input[type="checkbox"]:checked');

    checkboxes.forEach(checkbox => {
        const card = checkbox.closest('.existing-item-card');
        if (!card) return;

        // Get the inventory key
        const inventoryKey = checkbox.getAttribute('data-inventory-key') || checkbox.dataset.inventoryKey;

        // Skip if it has an inventory key (already handled by getExistingItemInventoryKeys)
        if (inventoryKey && inventoryKey.trim() !== '') return;

        // Extract item attributes from the card HTML
        // The card contains the item details in a specific structure
        const descriptionEl = card.querySelector('.detail-label');
        const materialEl = card.querySelector('.text-muted');
        const conditionEl = card.querySelector('.badge');
        const colorEl = card.querySelectorAll('.text-muted')[1]; // Second text-muted element
        const sizeEl = card.querySelector('.col-md-2.text-center small:last-of-type, .col-md-3.text-center small:last-of-type');

        if (descriptionEl) {
            items.push({
                description: (descriptionEl.textContent || '').trim(),
                material: materialEl ? (materialEl.textContent || '').trim() : '',
                condition: conditionEl ? (conditionEl.textContent || '').trim() : '',
                color: colorEl ? (colorEl.textContent || '').trim() : '',
                size: sizeEl ? (sizeEl.textContent || '').trim() : ''
            });
        }
    });

    return items;
}

/**
 * Check if an inventory item matches any existing item by attributes
 * Issue #177: Helper function to match items without InventoryKey
 * @param {Object} inventoryItem - Inventory item to check
 * @param {Array} existingItems - Array of existing item attribute objects
 * @returns {boolean} True if item matches an existing item
 */
function matchesExistingItem(inventoryItem, existingItems) {
    return existingItems.some(existing => {
        return (
            inventoryItem.description === existing.description &&
            (inventoryItem.material || '') === (existing.material || 'No material specified') &&
            (inventoryItem.condition || '') === existing.condition &&
            (inventoryItem.color || '') === existing.color &&
            (inventoryItem.size_wgt || '') === existing.size
        );
    });
}

/**
 * Escape HTML to prevent XSS attacks
 * @param {string} text - Text to escape
 * @returns {string} HTML-safe text
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Format price as currency
 */
function formatPrice(price) {
    let num = parseFloat(price);
    if (isNaN(num)) return "$0.00";
    return `$${num.toFixed(2)}`;
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Load customer inventory items
 */
function loadCustomerInventory(custId) {
    const inventoryContainer = document.getElementById('customer-inventory');

    if (!custId) {
        inventoryContainer.innerHTML = `
            <div class="inventory-empty">
                <i class="fas fa-boxes"></i>
                <p>Select a customer to view their inventory items</p>
            </div>
        `;
        updateInventoryCount(0);
        return;
    }

    // Show loading
    inventoryContainer.innerHTML = `
        <div class="inventory-empty">
            <div class="spinner-border text-primary loading-spinner" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p>Loading inventory items...</p>
        </div>
    `;

    fetch(`/work_orders/api/customer_inventory/${custId}`)
        .then(response => response.json())
        .then(data => {
            // Get inventory keys of items currently in the order
            const existingItemKeys = getExistingItemInventoryKeys();

            // Issue #177: Also get items by attributes (for items without InventoryKey)
            const existingItemsByAttributes = getExistingItemsByAttributes();

            // Filter out items that are already in the order
            // Check both by InventoryKey AND by attributes
            const availableItems = data.filter(item => {
                // Filter by InventoryKey (if item has one)
                if (existingItemKeys.has(item.id)) {
                    return false;
                }

                // Filter by attributes (for items without InventoryKey)
                if (matchesExistingItem(item, existingItemsByAttributes)) {
                    return false;
                }

                return true;
            });

            updateInventoryCount(availableItems.length);

            if (availableItems.length === 0) {
                inventoryContainer.innerHTML = `
                    <div class="inventory-empty">
                        <i class="fas fa-box-open"></i>
                        <p>No items found in previous work orders for this customer</p>
                        <small class="text-muted">Add new items below to get started</small>
                    </div>
                `;
                return;
            }

            let html = '';
            availableItems.forEach(item => {
                // For repair orders, don't show price (it's a cleaning price, not relevant)
                const priceDisplay = isRepairOrder ? '' : `<strong>${formatPrice(item.price)}</strong>`;
                const sizeColClass = isRepairOrder ? 'col-md-3' : 'col-md-2';
                const qtyColClass = isRepairOrder ? 'col-md-3' : 'col-md-2';

                // Store item data in data attributes for safe retrieval later (Issue #167)
                // This prevents brittle DOM parsing in moveItemToExistingItems()
                html += `
                    <div class="inventory-item" onclick="toggleItem(this, '${item.id}')"
                         data-inventory-key="${escapeHtml(item.id)}"
                         data-description="${escapeHtml(item.description)}"
                         data-material="${escapeHtml(item.material)}"
                         data-condition="${escapeHtml(item.condition)}"
                         data-color="${escapeHtml(item.color)}"
                         data-size="${escapeHtml(item.size_wgt)}"
                         data-price="${escapeHtml(item.price)}"
                         data-qty="${escapeHtml(item.qty)}">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="selected_items[]" value="${item.id}" id="item_${item.id}">
                            <label class="form-check-label w-100" for="item_${item.id}">
                                <div class="row align-items-center">
                                    <div class="col-md-5">
                                        <div class="detail-label">${item.description}</div>
                                        <small class="text-muted">${item.material || 'No material specified'}</small>
                                    </div>
                                    <div class="col-md-3">
                                        <span class="badge bg-secondary">${item.condition || 'Unknown'}</span>
                                        <br><small class="text-muted">${item.color || 'No color'}</small>
                                    </div>
                                    <div class="${sizeColClass} text-center">
                                        <small class="text-muted">Size:</small><br>
                                        <small>${item.size_wgt || '-'}</small><br>
                                        ${priceDisplay}
                                    </div>
                                    <div class="${qtyColClass}">
                                        <label class="form-label small">Qty:</label>
                                        <input type="number" class="form-control form-control-sm qty-input"
                                            name="item_qty_${item.id}" value="${item.qty || 1}" min="1"
                                            onclick="event.stopPropagation()">
                                    </div>
                                </div>
                            </label>
                        </div>
                    </div>
                `;
            });
            inventoryContainer.innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading inventory:', error);
            inventoryContainer.innerHTML = `
                <div class="inventory-empty">
                    <i class="fas fa-exclamation-triangle text-danger"></i>
                    <p class="text-danger">Error loading previous work order items</p>
                </div>
            `;
        });
}

/**
 * Toggle inventory item selection
 */
function toggleItem(element) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    // Use window.event for cross-browser compatibility
    const evt = window.event;
    if (evt && evt.target.type !== 'checkbox' && evt.target.type !== 'number') {
        checkbox.checked = !checkbox.checked;
    }

    // Check if we're on edit page (has existing items section)
    const existingItemsContainer = document.getElementById('existing-items');
    const isEditPage = existingItemsContainer !== null;

    if (checkbox.checked) {
        element.classList.add('selected');
        selectedItemsCount++;

        if (isEditPage) {
            // EDIT PAGE: Move item to "Existing Items" section and hide from history
            moveItemToExistingItems(element, checkbox);
            element.style.display = 'none';
        }
        // CREATE PAGE: Just leave it visible and selected
    } else {
        element.classList.remove('selected');
        selectedItemsCount--;

        if (isEditPage) {
            // EDIT PAGE: Remove from "Existing Items" and show back in history
            removeItemFromExistingItems(checkbox.value);
            element.style.display = '';
        }
        // CREATE PAGE: Just leave it visible and unselected
    }

    updateCounts();
}

/**
 * Move an item from Customer History to Existing Items section
 * Fixed in Issue #167: Now uses data attributes instead of brittle DOM parsing
 */
function moveItemToExistingItems(inventoryElement, checkbox) {
    const existingItemsContainer = document.getElementById('existing-items');
    if (!existingItemsContainer) return; // Not on edit page

    // Remove empty state if present
    const emptyState = existingItemsContainer.querySelector('.empty-state-message');
    if (emptyState) {
        emptyState.remove();
    }

    // Get item data from data attributes (safe and reliable)
    const inventoryKey = checkbox.value;
    const description = inventoryElement.dataset.description || 'Unknown Item';
    const material = inventoryElement.dataset.material || '';
    const condition = inventoryElement.dataset.condition || '';
    const color = inventoryElement.dataset.color || '';
    const size = inventoryElement.dataset.size || '';
    const price = inventoryElement.dataset.price || '0.00';

    // Get quantity from input field (user may have changed it)
    const qtyInput = inventoryElement.querySelector(`input[name="item_qty_${inventoryKey}"]`);
    const qty = qtyInput ? qtyInput.value : (inventoryElement.dataset.qty || '1');

    // Format price display
    const priceDisplay = price ? formatPrice(price) : '$0.00';

    // Create a card for the existing items section
    // Note: We escape HTML here to prevent XSS even though data came from backend
    const cardHtml = `
        <div class="existing-item-card" data-inventory-key="${escapeHtml(inventoryKey)}" data-temp-item="true" id="temp-item-${escapeHtml(inventoryKey)}">
            <div class="form-check">
                <input class="form-check-input" type="checkbox" name="existing_item_id_temp[]"
                       value="${escapeHtml(inventoryKey)}" checked
                       onchange="toggleExistingItem(this)"
                       data-inventory-key="${escapeHtml(inventoryKey)}">
                <label class="form-check-label w-100">
                    <div class="row align-items-center">
                        <div class="col-md-4">
                            <div class="detail-label">${escapeHtml(description)}</div>
                            <small class="text-muted">${escapeHtml(material)}</small>
                        </div>
                        <div class="col-md-3">
                            <span class="badge bg-secondary">${escapeHtml(condition)}</span>
                            <br><small class="text-muted">${escapeHtml(color)}</small>
                        </div>
                        <div class="col-md-2 text-center">
                            <small class="text-muted">Size:</small><br>
                            <small>${escapeHtml(size)}</small><br>
                            <strong>${priceDisplay}</strong>
                        </div>
                        <div class="col-md-2 text-center">
                            <small class="text-muted">Qty:</small><br>
                            <strong>${escapeHtml(qty)}</strong>
                        </div>
                        <div class="col-md-1 text-center">
                            <span class="badge bg-info">New</span>
                        </div>
                    </div>
                </label>
            </div>
        </div>
    `;

    existingItemsContainer.insertAdjacentHTML('beforeend', cardHtml);

    // Update existing items count
    if (typeof updateExistingCount === 'function') {
        updateExistingCount();
    }
}

/**
 * Remove an item from Existing Items section (temp items only)
 */
function removeItemFromExistingItems(inventoryKey) {
    const tempItem = document.getElementById(`temp-item-${inventoryKey}`);
    if (tempItem) {
        tempItem.remove();

        // Update existing items count
        if (typeof updateExistingCount === 'function') {
            updateExistingCount();
        }

        // Check if we need to show empty state
        if (typeof updateExistingItemsEmptyState === 'function') {
            updateExistingItemsEmptyState();
        }
    }
}

/**
 * Add a new item row (card style)
 */
function addNewItem() {
    const container = document.getElementById('new-items-container');

    // For repair orders, don't show price field (only overall repair price matters)
    const priceField = isRepairOrder ? '' : `
                <div class="col-md-4 mb-3">
                    <label class="form-label detail-label">Price</label>
                    <div class="input-group">
                        <span class="input-group-text">$</span>
                        <input type="number" class="form-control" name="new_item_price[]" step="0.01" min="0">
                    </div>
                </div>`;

    const colorColClass = isRepairOrder ? 'col-md-6' : 'col-md-4';
    const sizeColClass = isRepairOrder ? 'col-md-6' : 'col-md-4';

    const itemHtml = `
        <div class="new-item-row" id="new-item-${newItemCounter}">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">
                    <i class="fas fa-box me-2"></i>New Item ${newItemCounter + 1}
                </h6>
                <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeNewItem(${newItemCounter})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>

            <div class="row">
                <div class="col-md-3 mb-3">
                    <label class="form-label detail-label">Quantity</label>
                    <input type="number" class="form-control" name="new_item_qty[]" value="1" min="1">
                </div>
                <div class="col-md-9 mb-3">
                    <label class="form-label detail-label">Description *</label>
                    <input type="text" class="form-control" name="new_item_description[]" required list="description-list">
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label detail-label">Material</label>
                    <input type="text" class="form-control" name="new_item_material[]" list="material-list">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label detail-label">Condition</label>
                    <input type="text" class="form-control" name="new_item_condition[]" list="condition-list">
                </div>
            </div>

            <div class="row">
                <div class="${colorColClass} mb-3">
                    <label class="form-label detail-label">Color</label>
                    <input type="text" class="form-control" name="new_item_color[]" list="color-list">
                </div>
                <div class="${sizeColClass} mb-3">
                    <label class="form-label detail-label">Size/Weight</label>
                    <input type="text" class="form-control" name="new_item_size[]">
                </div>
                ${priceField}
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', itemHtml);
    newItemCounter++;
    newItemsCount++;
    updateCounts();
}

/**
 * Remove a new item row
 */
function removeNewItem(itemId) {
    const element = document.getElementById(`new-item-${itemId}`);
    if (element) {
        element.remove();
        newItemsCount--;
        updateCounts();
    }
}

/**
 * Update inventory count badge
 */
function updateInventoryCount(count) {
    document.getElementById('inventory-count').textContent = count;

    // Show/hide select all controls based on whether there are items
    const selectAllControls = document.getElementById('select-all-controls');
    if (selectAllControls) {
        selectAllControls.style.display = count > 0 ? 'block' : 'none';
    }
}

/**
 * Update all counters and badges
 */
function updateCounts() {
    document.getElementById('selected-count').textContent = selectedItemsCount;
    document.getElementById('new-count').textContent = newItemsCount;
    document.getElementById('new-items-count').textContent = newItemsCount;
    document.getElementById('total-count').textContent = selectedItemsCount + newItemsCount;
}

/**
 * Update rush status badges
 */
function updateRushStatus() {
    const rushOrder = document.getElementById('RushOrder').checked;
    const firmRush = document.getElementById('FirmRush').checked;
    const rushStatus = document.getElementById('rush-status');
    const rushBadge = document.getElementById('rush-badge');
    const firmRushBadge = document.getElementById('firm-rush-badge');

    if (rushOrder || firmRush) {
        rushStatus.style.display = 'block';
        rushBadge.style.display = rushOrder ? 'inline' : 'none';
        firmRushBadge.style.display = firmRush ? 'inline' : 'none';
    } else {
        rushStatus.style.display = 'none';
    }
}

/**
 * Create autocomplete datalists for item fields
 */
function createDatalists() {
    // Description datalist
    const descriptionDatalist = document.createElement('datalist');
    descriptionDatalist.id = 'description-list';
    descriptionValues.forEach(val => {
        const option = document.createElement('option');
        option.value = val;
        descriptionDatalist.appendChild(option);
    });
    document.body.appendChild(descriptionDatalist);

    // Material datalist
    const materialDatalist = document.createElement('datalist');
    materialDatalist.id = 'material-list';
    materialValues.forEach(val => {
        const option = document.createElement('option');
        option.value = val;
        materialDatalist.appendChild(option);
    });
    document.body.appendChild(materialDatalist);

    // Color datalist
    const colorDatalist = document.createElement('datalist');
    colorDatalist.id = 'color-list';
    colorValues.forEach(val => {
        const option = document.createElement('option');
        option.value = val;
        colorDatalist.appendChild(option);
    });
    document.body.appendChild(colorDatalist);

    // Condition datalist
    const conditionDatalist = document.createElement('datalist');
    conditionDatalist.id = 'condition-list';
    conditionValues.forEach(val => {
        const option = document.createElement('option');
        option.value = val;
        conditionDatalist.appendChild(option);
    });
    document.body.appendChild(conditionDatalist);
}

// ============================================================================
// SELECT ALL / DESELECT ALL HANDLERS
// ============================================================================

/**
 * Select all inventory items from customer history
 * Issue #104: Add select all button to customer inventory
 */
function selectAllInventoryItems() {
    const inventoryContainer = document.getElementById('customer-inventory');
    if (!inventoryContainer) return;

    // Get all visible inventory items (not hidden by edit page logic)
    const inventoryItems = inventoryContainer.querySelectorAll('.inventory-item');

    inventoryItems.forEach(item => {
        // Skip items that are already hidden (on edit page, already selected)
        if (item.style.display === 'none') return;

        const checkbox = item.querySelector('input[type="checkbox"][name="selected_items[]"]');
        if (checkbox && !checkbox.checked) {
            // Trigger the checkbox programmatically
            checkbox.checked = true;
            item.classList.add('selected');
            selectedItemsCount++;

            // Check if we're on edit page and move item if needed
            const existingItemsContainer = document.getElementById('existing-items');
            const isEditPage = existingItemsContainer !== null;

            if (isEditPage) {
                // Move item to "Existing Items" section and hide from history
                moveItemToExistingItems(item, checkbox);
                item.style.display = 'none';
            }
        }
    });

    updateCounts();
}

/**
 * Deselect all inventory items from customer history
 * Issue #104: Add select all button to customer inventory
 */
function deselectAllInventoryItems() {
    const inventoryContainer = document.getElementById('customer-inventory');
    if (!inventoryContainer) return;

    // Get all inventory items (including hidden ones)
    const inventoryItems = inventoryContainer.querySelectorAll('.inventory-item');

    inventoryItems.forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"][name="selected_items[]"]');
        if (checkbox && checkbox.checked) {
            // Uncheck the checkbox
            checkbox.checked = false;
            item.classList.remove('selected');
            selectedItemsCount--;

            // Check if we're on edit page and remove from existing items if needed
            const existingItemsContainer = document.getElementById('existing-items');
            const isEditPage = existingItemsContainer !== null;

            if (isEditPage) {
                // Remove from "Existing Items" and show back in history
                removeItemFromExistingItems(checkbox.value);
                item.style.display = '';
            }
        }
    });

    updateCounts();
}

// ============================================================================
// FILE UPLOAD HANDLERS
// ============================================================================

const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx', 'txt', 'csv'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

/**
 * Validate file type and size
 */
function validateFile(file) {
    const extension = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
        alert(`File type not allowed: ${file.name}\nAllowed types: ${ALLOWED_EXTENSIONS.join(', ')}`);
        return false;
    }

    if (file.size > MAX_FILE_SIZE) {
        alert(`File too large: ${file.name}\nMaximum size: 10MB`);
        return false;
    }

    return true;
}

/**
 * Update file list display
 */
function updateFileList() {
    const fileInput = document.getElementById('files');
    const fileList = document.getElementById('fileList');
    const fileListContainer = document.getElementById('fileListContainer');
    const files = fileInput.files;

    if (files.length === 0) {
        fileListContainer.style.display = 'none';
        return;
    }

    fileListContainer.style.display = 'block';
    fileList.innerHTML = '';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';

        const fileInfo = document.createElement('div');
        fileInfo.innerHTML = `
            <i class="fas fa-file me-2"></i>
            <strong>${file.name}</strong>
            <small class="text-muted ms-2">(${formatFileSize(file.size)})</small>
        `;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-sm btn-outline-danger';
        removeBtn.innerHTML = '<i class="fas fa-times"></i>';
        removeBtn.onclick = () => removeFile(i);

        li.appendChild(fileInfo);
        li.appendChild(removeBtn);
        fileList.appendChild(li);
    }
}

/**
 * Remove individual file
 */
function removeFile(index) {
    const fileInput = document.getElementById('files');
    const files = Array.from(fileInput.files);
    files.splice(index, 1);

    const dataTransfer = new DataTransfer();
    files.forEach(file => dataTransfer.items.add(file));
    fileInput.files = dataTransfer.files;

    // Update global storage
    window.uploadedFiles = files;

    updateFileList();
}

/**
 * Clear all files
 */
function clearFiles() {
    const fileInput = document.getElementById('files');
    fileInput.value = '';

    // Clear global storage
    window.uploadedFiles = [];

    updateFileList();
}

/**
 * Show upload progress indicator
 */
function showUploadProgress(fileCount) {
    const progressContainer = document.getElementById('uploadProgressContainer');
    const statusText = document.getElementById('uploadStatusText');
    const fileListContainer = document.getElementById('fileListContainer');
    const dropzone = document.getElementById('fileDropzone');

    if (progressContainer && fileCount > 0) {
        // Hide file list and dropzone
        if (fileListContainer) fileListContainer.style.display = 'none';
        if (dropzone) dropzone.style.pointerEvents = 'none'; // Disable interaction

        // Update status text
        if (statusText) {
            statusText.textContent = fileCount === 1
                ? 'Uploading 1 file...'
                : `Uploading ${fileCount} files...`;
        }

        // Show progress
        progressContainer.style.display = 'block';

        // Disable submit button to prevent double submission
        const submitBtn = document.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
        }
    }
}

/**
 * Initialize file upload dropzone
 */
function initializeFileUpload() {
    const dropzone = document.getElementById('fileDropzone');
    const fileInput = document.getElementById('files');

    if (!dropzone || !fileInput) return;

    // Click opens file selector
    dropzone.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            fileInput.click();
        }
    });

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => {
            dropzone.classList.add('border-primary', 'border-2', 'bg-light');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => {
            dropzone.classList.remove('border-primary', 'border-2', 'bg-light');
        }, false);
    });

    // Handle dropped files
    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;

        // Initialize global file storage if it doesn't exist
        if (!window.uploadedFiles) {
            window.uploadedFiles = [];
        }

        const validFiles = [];
        for (let i = 0; i < files.length; i++) {
            if (validateFile(files[i])) {
                validFiles.push(files[i]);
            }
        }

        if (validFiles.length > 0) {
            // Merge with existing files (prevents removing previously selected files)
            const allFiles = [...window.uploadedFiles, ...validFiles];

            const dataTransfer = new DataTransfer();
            allFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;

            // Store for next time
            window.uploadedFiles = allFiles;

            updateFileList();
        }
    }, false);

    // Handle file input change
    fileInput.addEventListener('change', () => {
        // Initialize global file storage if it doesn't exist
        if (!window.uploadedFiles) {
            window.uploadedFiles = [];
        }

        // Get newly selected files
        const newFiles = Array.from(fileInput.files);
        const validFiles = [];

        // Validate each new file
        for (let i = 0; i < newFiles.length; i++) {
            if (validateFile(newFiles[i])) {
                validFiles.push(newFiles[i]);
            }
        }

        // Merge with existing files (prevents removing previously selected files)
        const allFiles = [...window.uploadedFiles, ...validFiles];

        // Update the file input with all files
        const dataTransfer = new DataTransfer();
        allFiles.forEach(file => dataTransfer.items.add(file));
        fileInput.files = dataTransfer.files;

        // Store for next time
        window.uploadedFiles = allFiles;

        updateFileList();
    });

    // Handle form submission to show progress
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', () => {
            const fileInput = document.getElementById('files');
            if (fileInput && fileInput.files.length > 0) {
                showUploadProgress(fileInput.files.length);
            }
        });
    }
}

// Export for Node.js/Jest (CommonJS) - browser ignores this
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        formatPrice,
        formatFileSize,
        getExistingItemInventoryKeys,
        getExistingItemsByAttributes,
        matchesExistingItem,
        loadCustomerInventory,
        toggleItem,
        moveItemToExistingItems,
        removeItemFromExistingItems,
        addNewItem,
        removeNewItem,
        updateInventoryCount,
        updateCounts,
        updateRushStatus,
        createDatalists,
        selectAllInventoryItems,
        deselectAllInventoryItems,
        validateFile,
        updateFileList,
        removeFile,
        clearFiles,
        initializeFileUpload
    };
}
