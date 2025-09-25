// Keyboard Shortcuts for Work Order Forms
// Global variables
let helpVisible = false;

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

    // Global navigation shortcuts
    hotkeys('ctrl+shift+1', (e) => {
        e.preventDefault();
        window.location.href = '/sources';
        console.log('Navigating to Sources');
    });

    hotkeys('ctrl+shift+2', (e) => {
        e.preventDefault();
        window.location.href = '/customers';
        console.log('Navigating to Customers');
    });

    hotkeys('ctrl+shift+3', (e) => {
        e.preventDefault();
        window.location.href = '/work_orders';
        console.log('Navigating to Work Orders');
    });

    hotkeys('ctrl+shift+4', (e) => {
        e.preventDefault();
        window.location.href = '/repair_work_orders';
        console.log('Navigating to Repair Orders');
    });

    hotkeys('ctrl+shift+5', (e) => {
        e.preventDefault();
        window.location.href = '/cleaning_queue/cleaning-queue';
        console.log('Navigating to Queue');
    });

    console.log('Global navigation shortcuts initialized');
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeKeyboardShortcuts();
    initializeGlobalShortcuts();
});

// Export functions for manual initialization if needed
window.initializeKeyboardShortcuts = initializeKeyboardShortcuts;
window.initializeGlobalShortcuts = initializeGlobalShortcuts;
window.toggleHelp = toggleHelp;
