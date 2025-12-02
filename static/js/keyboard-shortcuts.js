// Keyboard Shortcuts for Work Order Forms
// Global variables
let helpVisible = false;

// Mobile detection - detect mobile devices to hide keyboard shortcuts
// Uses multiple signals to minimize false positives
function isMobileDevice() {
    // Check 1: User agent patterns for mobile devices
    const mobilePatterns = [
        /Android/i,
        /webOS/i,
        /iPhone/i,
        /iPad/i,
        /iPod/i,
        /BlackBerry/i,
        /Windows Phone/i
    ];

    const userAgent = navigator.userAgent || navigator.vendor || window.opera;
    const hasMobileUA = mobilePatterns.some(pattern => pattern.test(userAgent));

    // Check 2: Touch capability (not sufficient alone - many laptops have touch)
    const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    // Check 3: Screen size (phones and small tablets)
    const isSmallScreen = window.innerWidth <= 768;

    // Check 4: Pointer type (coarse = touch-based primary input)
    const hasCoarsePointer = window.matchMedia('(pointer: coarse)').matches;

    // Decision logic to minimize false positives:
    // - If user agent clearly indicates mobile, it's mobile
    // - If small screen AND (touch OR coarse pointer), it's probably mobile
    // - Otherwise, assume desktop to avoid hiding for desktop users
    if (hasMobileUA) {
        return true;
    }

    if (isSmallScreen && (hasTouch || hasCoarsePointer)) {
        return true;
    }

    return false;
}

// Apply mobile detection on page load
function applyMobileDetection() {
    if (isMobileDevice()) {
        document.documentElement.classList.add('is-mobile-device');
        console.log('Mobile device detected - hiding keyboard shortcuts');
    } else {
        console.log('Desktop device detected - showing keyboard shortcuts');
    }
}

// Run detection as early as possible
applyMobileDetection();

function toggleHelp() {
    const helpPanel = document.getElementById('floating-help');
    if (!helpPanel) {
        console.error('Help panel not found!');
        return;
    }
    
    helpVisible = !helpVisible;
    window.helpVisible = helpVisible; // Make globally accessible
    
    if (helpVisible) {
        helpPanel.classList.add('show');
    } else {
        helpPanel.classList.remove('show');
    }
}

// Initialize keyboard shortcuts
function initializeKeyboardShortcuts() {
    // Check if hotkeys is loaded
    if (typeof hotkeys === 'undefined') {
        console.error('hotkeys-js library not loaded!');
        return;
    }

    // Form field shortcuts
    hotkeys('alt+c', (e) => {
        e.preventDefault();
        const element = document.getElementById('CustID');
        if (element) {
            element.focus();
            console.log('Alt+C pressed - Customer ID focused');
        }
    });
    
    hotkeys('alt+n', (e) => {
        e.preventDefault();
        const element = document.getElementById('WOName');
        if (element) element.focus();
    });
    
    hotkeys('alt+s', (e) => {
        e.preventDefault();
        const element = document.getElementById('RackNo');
        if (element) element.focus();
    });
    
    hotkeys('alt+r', (e) => {
        e.preventDefault();
        const element = document.getElementById('ShipTo');
        if (element) element.focus();
    });
    
    hotkeys('alt+i', (e) => {
        e.preventDefault();
        const element = document.getElementById('SpecialInstructions');
        if (element) element.focus();
    });

    hotkeys('alt+d', (e) => {
        e.preventDefault();
        const element = document.getElementById('RepairsNeeded');
        if (element) element.focus();
    });

    hotkeys('alt+q', (e) => {
        e.preventDefault();
        const element = document.getElementById('Quote');
        if (element) element.focus();
    });
    
    // Item management
    hotkeys('alt+a', (e) => {
        e.preventDefault();
        if (typeof addNewItem === 'function') {
            addNewItem();
            setTimeout(() => {
                const newItems = document.querySelectorAll('input[name="new_item_description[]"]');
                if (newItems.length > 0) {
                    newItems[newItems.length - 1].focus();
                }
            }, 100);
        } else {
            console.warn('addNewItem function not found');
        }
    });
    
    // Priority toggles
    hotkeys('alt+u', (e) => {
        e.preventDefault();
        const rushCheckbox = document.getElementById('RushOrder');
        if (rushCheckbox) {
            rushCheckbox.checked = !rushCheckbox.checked;
            rushCheckbox.dispatchEvent(new Event('change'));
        }
    });
    
    hotkeys('alt+e', (e) => {
        e.preventDefault();
        const firmRushCheckbox = document.getElementById('FirmRush');
        if (firmRushCheckbox) {
            firmRushCheckbox.checked = !firmRushCheckbox.checked;
            firmRushCheckbox.dispatchEvent(new Event('change'));
            if (firmRushCheckbox.checked) {
                setTimeout(() => {
                    const dateReq = document.getElementById('DateRequired');
                    if (dateReq) dateReq.focus();
                }, 100);
            }
        }
    });
    
    // Form actions
    hotkeys('ctrl+shift+s', (e) => {
        e.preventDefault();
        console.log('Attempting to submit form...');
        
        const form = document.getElementById('workOrderForm');
        if (form) {
            console.log('Form found, submitting...');
            // Try clicking the submit button instead of calling submit() directly
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.click();
                console.log('Submit button clicked');
            } else {
                // Fallback to direct submission
                form.submit();
                console.log('Form submitted directly');
            }
        } else {
            console.error('Form not found');
        }
    });
    
    // Improved ESC behavior
    hotkeys('escape', (e) => {
        // First check if help is open
        if (window.helpVisible || helpVisible) {
            e.preventDefault();
            toggleHelp();
            return;
        }
        
        // Check if an element is focused and blur it
        const activeElement = document.activeElement;
        if (activeElement && activeElement !== document.body) {
            e.preventDefault();
            activeElement.blur();
            console.log('Blurred active element');
            return;
        }
        
        // If no element is focused, offer to cancel
        e.preventDefault();
        if (confirm('Are you sure you want to cancel? Any unsaved changes will be lost.')) {
            window.history.back();
        }
    });
    
    // File upload
    hotkeys('alt+f', (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('files');
        if (fileInput) {
            fileInput.click();
        }
    });

    // Edit order (works for both clean + repair)
    hotkeys('ctrl+e', (e) => {
        e.preventDefault();

        // Try repair edit button first
        let repairEdit = document.querySelector("a.btn-warning[href*='repair_work_orders']");
        if (repairEdit) {
            repairEdit.click();
            console.log('Ctrl+E pressed - Repair Edit clicked');
            return;
        }

        // Then try clean edit button
        let cleanEdit = document.querySelector("a.btn-primary[href*='work_orders']");
        if (cleanEdit) {
            cleanEdit.click();
            console.log('Ctrl+E pressed - Clean Edit clicked');
            return;
        }

        console.warn("Ctrl+E pressed - No edit button found on this page");
    });
    
    
    // Show help
    hotkeys('alt+shift+/', (e) => {
        e.preventDefault();
        toggleHelp();
    });

    // Close help when clicking outside
    document.addEventListener('click', function(e) {
        if (!window.helpVisible && !helpVisible) return;
        
        const helpPanel = document.getElementById('floating-help');
        const helpButton = document.querySelector('.help-trigger');
        
        if (helpPanel && helpButton && 
            !helpPanel.contains(e.target) && 
            !helpButton.contains(e.target)) {
            toggleHelp();
        }
    });

    console.log('Keyboard shortcuts initialized successfully');
}


// Initialize global navigation shortcuts (available on all pages)
function initializeGlobalShortcuts() {
    if (typeof hotkeys === 'undefined') {
        console.warn('hotkeys-js not loaded for global shortcuts');
        return;
    }

    // Define key → route mapping
    const shortcuts = {
        1: { path: '/sources', label: 'Sources' },
        2: { path: '/customers', label: 'Customers' },
        3: { path: '/work_orders', label: 'Work Orders' },
        4: { path: '/repair_work_orders', label: 'Repair Orders' },
        5: { path: '/cleaning_queue/cleaning-queue', label: 'Queue' },
    };

    // Register both top-row and numpad combos
    Object.entries(shortcuts).forEach(([num, { path, label }]) => {
        const combos = [`ctrl+shift+${num}`, `ctrl+shift+numpad${num}`];
        hotkeys(combos.join(','), (e) => {
            e.preventDefault();
            window.location.href = path;
            console.log(`Navigating to ${label}`);
        });
    });

    console.log('Global navigation shortcuts initialized');
}

// Test this func out to see if it works for the numpad, otherwise not messing with this anymore..
// function initializeGlobalShortcuts() {
//     // Define key → route mapping
//     const shortcuts = {
//         '1': { path: '/sources', label: 'Sources' },
//         '2': { path: '/customers', label: 'Customers' },
//         '3': { path: '/work_orders', label: 'Work Orders' },
//         '4': { path: '/repair_work_orders', label: 'Repair Orders' },
//         '5': { path: '/cleaning_queue/cleaning-queue', label: 'Queue' },
//     };

//     // Use vanilla JS to handle keydown events
//     document.addEventListener('keydown', (e) => {
//         // Check for Ctrl + Shift + number (works for both top-row and numpad)
//         if (e.ctrlKey && e.shiftKey && Object.keys(shortcuts).includes(e.key)) {
//             e.preventDefault();
//             const { path, label } = shortcuts[e.key];
//             window.location.href = path;
//             console.log(`Navigating to ${label}`);
//         }
//     });

//     console.log('Global navigation shortcuts initialized');
// }


// Table Navigation Module
let tableNavigator = null;

class TableNavigator {
    constructor() {
        this.selectedRowIndex = -1;
        this.table = null;
        this.tableType = null; // 'tabulator' or 'standard'
        this.rows = [];
        this.init();
    }

    init() {
        // Detect table type on page
        if (document.querySelector('.tabulator') ||
            document.querySelector('#work-orders-table') ||
            document.querySelector('#repair-orders-table') ||
            document.querySelector('#customers-table')) {
            this.tableType = 'tabulator';
            console.log('Tabulator table detected, initializing...');
            // Wait for tabulator to fully initialize
            setTimeout(() => this.initTabulator(), 1000);
        } else if (document.querySelector('table.table')) {
            this.tableType = 'standard';
            this.initStandardTable();
        }
    }

    initTabulator() {
        // Wait a bit longer for Tabulator to be fully initialized
        let retryCount = 0;
        const maxRetries = 10;

        const checkTabulator = () => {
            console.log(`Checking for Tabulator instance (attempt ${retryCount + 1}/${maxRetries})...`);

            // Check for globally exposed Tabulator instances
            this.table = window.workOrdersTable ||
                        window.repairOrdersTable ||
                        window.customersTable;

            if (this.table) {
                console.log('✓ Table navigation initialized for Tabulator', this.table);
                // Enable row selection
                this.table.on("rowClick", (e, row) => {
                    this.selectRow(row);
                });
            } else {
                retryCount++;
                if (retryCount < maxRetries) {
                    console.warn(`✗ Tabulator instance not found (window.workOrdersTable=${!!window.workOrdersTable}, window.repairOrdersTable=${!!window.repairOrdersTable}, window.customersTable=${!!window.customersTable}), retrying...`);
                    // Try again after a short delay
                    setTimeout(checkTabulator, 500);
                } else {
                    console.error('✗ Failed to find Tabulator instance after', maxRetries, 'attempts');
                }
            }
        };

        checkTabulator();
    }

    initStandardTable() {
        const table = document.querySelector('table.table tbody');
        if (!table) return;

        this.table = table;
        console.log('Table navigation initialized for standard table');

        // Add click handlers to rows
        this.getStandardRows().forEach((row, index) => {
            row.addEventListener('click', () => {
                this.selectStandardRow(index);
            });
        });
    }

    getStandardRows() {
        if (!this.table) return [];
        return Array.from(this.table.querySelectorAll('tr'));
    }

    selectRow(row) {
        if (this.tableType === 'tabulator' && this.table) {
            this.table.deselectRow();
            this.table.selectRow(row);
            row.getElement().scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    selectStandardRow(index) {
        const rows = this.getStandardRows();
        if (index < 0 || index >= rows.length) return;

        // Remove previous selection
        rows.forEach(r => r.classList.remove('table-active', 'selected-row'));

        // Add selection to new row
        rows[index].classList.add('table-active', 'selected-row');
        rows[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
        this.selectedRowIndex = index;
    }

    nextRow() {
        if (this.tableType === 'tabulator' && this.table) {
            const selectedRows = this.table.getSelectedRows();
            if (selectedRows.length === 0) {
                const firstRow = this.table.getRows()[0];
                if (firstRow) this.selectRow(firstRow);
            } else {
                const currentRow = selectedRows[0];
                const nextRow = currentRow.getNextRow();
                if (nextRow) this.selectRow(nextRow);
            }
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            if (rows.length === 0) return;

            if (this.selectedRowIndex === -1) {
                this.selectStandardRow(0);
            } else if (this.selectedRowIndex < rows.length - 1) {
                this.selectStandardRow(this.selectedRowIndex + 1);
            }
        }
    }

    prevRow() {
        if (this.tableType === 'tabulator' && this.table) {
            const selectedRows = this.table.getSelectedRows();
            if (selectedRows.length === 0) {
                const rows = this.table.getRows();
                if (rows.length > 0) this.selectRow(rows[0]);
            } else {
                const currentRow = selectedRows[0];
                const prevRow = currentRow.getPrevRow();
                if (prevRow) this.selectRow(prevRow);
            }
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            if (rows.length === 0) return;

            if (this.selectedRowIndex === -1) {
                this.selectStandardRow(0);
            } else if (this.selectedRowIndex > 0) {
                this.selectStandardRow(this.selectedRowIndex - 1);
            }
        }
    }

    firstRow() {
        if (this.tableType === 'tabulator' && this.table) {
            const rows = this.table.getRows();
            if (rows.length > 0) this.selectRow(rows[0]);
        } else if (this.tableType === 'standard') {
            this.selectStandardRow(0);
        }
    }

    lastRow() {
        if (this.tableType === 'tabulator' && this.table) {
            const rows = this.table.getRows();
            if (rows.length > 0) this.selectRow(rows[rows.length - 1]);
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            if (rows.length > 0) this.selectStandardRow(rows.length - 1);
        }
    }

    openSelected() {
        if (this.tableType === 'tabulator' && this.table) {
            const selectedRows = this.table.getSelectedRows();
            if (selectedRows.length > 0) {
                const data = selectedRows[0].getData();
                if (data.detail_url) {
                    window.location.href = data.detail_url;
                }
            }
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            if (this.selectedRowIndex >= 0 && this.selectedRowIndex < rows.length) {
                const link = rows[this.selectedRowIndex].querySelector('a');
                if (link) link.click();
            }
        }
    }

    editSelected() {
        if (this.tableType === 'tabulator' && this.table) {
            const selectedRows = this.table.getSelectedRows();
            if (selectedRows.length > 0) {
                const data = selectedRows[0].getData();
                if (data.edit_url) {
                    window.location.href = data.edit_url;
                }
            }
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            if (this.selectedRowIndex >= 0 && this.selectedRowIndex < rows.length) {
                const editBtn = rows[this.selectedRowIndex].querySelector('a[href*="edit"]');
                if (editBtn) editBtn.click();
            }
        }
    }

    clearSelection() {
        if (this.tableType === 'tabulator' && this.table) {
            this.table.deselectRow();
        } else if (this.tableType === 'standard') {
            const rows = this.getStandardRows();
            rows.forEach(r => r.classList.remove('table-active', 'selected-row'));
            this.selectedRowIndex = -1;
        }
    }

    nextPage() {
        if (this.tableType === 'tabulator' && this.table) {
            this.table.nextPage();
        } else if (this.tableType === 'standard') {
            const nextBtn = document.querySelector('.pagination .page-item:not(.disabled) a:contains("Next")') ||
                          document.querySelector('.pagination .page-link[aria-label="Next"]');
            if (nextBtn) nextBtn.click();
        }
    }

    prevPage() {
        if (this.tableType === 'tabulator' && this.table) {
            this.table.previousPage();
        } else if (this.tableType === 'standard') {
            const prevBtn = document.querySelector('.pagination .page-item:not(.disabled) a:contains("Previous")') ||
                          document.querySelector('.pagination .page-link[aria-label="Previous"]');
            if (prevBtn) prevBtn.click();
        }
    }

    isInputFocused() {
        const activeElement = document.activeElement;
        return activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        );
    }
}

// Initialize table navigation shortcuts
function initializeTableShortcuts() {
    if (typeof hotkeys === 'undefined') {
        console.warn('hotkeys-js not loaded for table shortcuts');
        return;
    }

    // Initialize table navigator
    tableNavigator = new TableNavigator();

    // Navigation shortcuts - only when not in input field
    const navigationHandler = (key, handler) => {
        hotkeys(key, (e) => {
            if (tableNavigator && !tableNavigator.isInputFocused()) {
                e.preventDefault();
                handler();
            }
        });
    };

    // Next/Previous row
    navigationHandler('j', () => tableNavigator.nextRow());
    navigationHandler('down', () => tableNavigator.nextRow());
    navigationHandler('k', () => tableNavigator.prevRow());
    navigationHandler('up', () => tableNavigator.prevRow());

    // First/Last row
    navigationHandler('g', () => {
        // Double-tap g to go to first
        if (window.lastGPress && Date.now() - window.lastGPress < 500) {
            tableNavigator.firstRow();
            window.lastGPress = null;
        } else {
            window.lastGPress = Date.now();
        }
    });
    navigationHandler('shift+g', () => tableNavigator.lastRow());

    // Open/Edit
    navigationHandler('enter', () => tableNavigator.openSelected());
    navigationHandler('e', () => tableNavigator.editSelected());

    // Clear selection (handled by existing escape handler, but add specific clear)
    hotkeys('escape', (e) => {
        if (tableNavigator && !tableNavigator.isInputFocused()) {
            const hasSelection = (tableNavigator.tableType === 'tabulator' && tableNavigator.table && tableNavigator.table.getSelectedRows().length > 0) ||
                               (tableNavigator.tableType === 'standard' && tableNavigator.selectedRowIndex >= 0);

            if (hasSelection) {
                e.preventDefault();
                tableNavigator.clearSelection();
                return;
            }
        }
    });

    // Page navigation
    navigationHandler('ctrl+j', () => tableNavigator.nextPage());
    navigationHandler('pagedown', () => tableNavigator.nextPage());
    navigationHandler('ctrl+k', () => tableNavigator.prevPage());
    navigationHandler('pageup', () => tableNavigator.prevPage());

    // Clear all table filters
    hotkeys('alt+x', (e) => {
        if (!tableNavigator || tableNavigator.isInputFocused()) return;
        e.preventDefault();
        clearAllFilters();
    });

    console.log('Table navigation shortcuts initialized');
}

// Clear all Tabulator filters function
function clearAllFilters() {
    // Find the clear filters button and click it
    const clearBtn = document.getElementById('clear-filters-btn') ||
                     document.getElementById('clear-table-filters-btn');

    if (clearBtn) {
        clearBtn.click();
        console.log('Cleared all table filters via button');
    } else {
        // Fallback: try to clear directly via table instance
        const table = window.workOrdersTable ||
                     window.repairOrdersTable ||
                     window.customersTable;

        if (table && typeof table.clearHeaderFilter === 'function') {
            table.clearHeaderFilter();
            table.setData();
            console.log('Cleared all table filters directly');
        } else {
            console.warn('No table or clear button found');
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeKeyboardShortcuts();
    initializeGlobalShortcuts();
    initializeTableShortcuts();
});

// Export functions for manual initialization if needed
window.initializeKeyboardShortcuts = initializeKeyboardShortcuts;
window.initializeGlobalShortcuts = initializeGlobalShortcuts;
window.initializeTableShortcuts = initializeTableShortcuts;
window.toggleHelp = toggleHelp;
