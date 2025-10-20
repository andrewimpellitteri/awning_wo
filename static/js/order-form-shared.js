/**
 * Shared JavaScript functionality for Work Order and Repair Order forms
 * This provides DRY code for common operations
 */

// Global counters
let newItemCounter = 0;
let selectedItemsCount = 0;
let newItemsCount = 0;

/**
 * Get inventory keys of items currently in the order
 * @returns {Set} Set of inventory keys
 */
function getExistingItemInventoryKeys() {
    const existingItems = document.querySelectorAll('.existing-item-card[data-inventory-key], input[type="checkbox"][name="existing_item_id[]"][data-inventory-key]');
    const keys = new Set();

    existingItems.forEach(item => {
        // Check if the item is checked (not removed)
        let isChecked = true;
        if (item.tagName === 'INPUT') {
            isChecked = item.checked;
        } else {
            const checkbox = item.querySelector('input[type="checkbox"][name="existing_item_id[]"]');
            isChecked = checkbox ? checkbox.checked : true;
        }

        if (isChecked) {
            const inventoryKey = item.getAttribute('data-inventory-key') || item.dataset.inventoryKey;
            if (inventoryKey && inventoryKey.trim() !== '') {
                keys.add(inventoryKey);
            }
        }
    });

    return keys;
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

            // Filter out items that are already in the order
            const availableItems = data.filter(item => !existingItemKeys.has(item.id));

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
                html += `
                    <div class="inventory-item" onclick="toggleItem(this, '${item.id}')">
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
                                    <div class="col-md-2 text-center">
                                        <small class="text-muted">Size:</small><br>
                                        <small>${item.size_wgt || '-'}</small><br>
                                        <strong>${formatPrice(item.price)}</strong>
                                    </div>
                                    <div class="col-md-2">
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

    if (checkbox.checked) {
        element.classList.add('selected');
        selectedItemsCount++;
    } else {
        element.classList.remove('selected');
        selectedItemsCount--;
    }

    updateCounts();
}

/**
 * Add a new item row (card style)
 */
function addNewItem() {
    const container = document.getElementById('new-items-container');
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
                <div class="col-md-4 mb-3">
                    <label class="form-label detail-label">Color</label>
                    <input type="text" class="form-control" name="new_item_color[]" list="color-list">
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label detail-label">Size/Weight</label>
                    <input type="text" class="form-control" name="new_item_size[]">
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label detail-label">Price</label>
                    <div class="input-group">
                        <span class="input-group-text">$</span>
                        <input type="number" class="form-control" name="new_item_price[]" step="0.01" min="0">
                    </div>
                </div>
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

    updateFileList();
}

/**
 * Clear all files
 */
function clearFiles() {
    const fileInput = document.getElementById('files');
    fileInput.value = '';
    updateFileList();
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

        const validFiles = [];
        for (let i = 0; i < files.length; i++) {
            if (validateFile(files[i])) {
                validFiles.push(files[i]);
            }
        }

        if (validFiles.length > 0) {
            const dataTransfer = new DataTransfer();
            validFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
            updateFileList();
        }
    }, false);

    // Handle file input change
    fileInput.addEventListener('change', () => {
        const validFiles = [];
        for (let i = 0; i < fileInput.files.length; i++) {
            if (validateFile(fileInput.files[i])) {
                validFiles.push(fileInput.files[i]);
            }
        }

        if (validFiles.length !== fileInput.files.length) {
            const dataTransfer = new DataTransfer();
            validFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
        }

        updateFileList();
    });
}
