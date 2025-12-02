/**
 * Draft Auto-Save Module
 *
 * Automatically saves form data to the server every 30 seconds to prevent data loss.
 * User-specific drafts stored in database, not localStorage.
 *
 * Usage:
 *   Add to form page: <script src="{{ url_for('static', filename='js/draft-autosave.js') }}"></script>
 *   Initialize: DraftAutoSave.init('work_order', '#workOrderForm');
 */

const DraftAutoSave = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        AUTOSAVE_INTERVAL: 30000,  // 30 seconds
        API_ENDPOINT: '/api/drafts',
        DEBOUNCE_DELAY: 1000,      // Wait 1s after last change before marking as dirty
    };

    // State
    let state = {
        formType: null,
        formSelector: null,
        draftId: null,
        timer: null,
        debounceTimer: null,
        isDirty: false,
        lastSaveTime: null,
        isEnabled: true,
    };

    /**
     * Initialize auto-save for a form
     * @param {string} formType - Type of form (e.g., 'work_order', 'repair_order')
     * @param {string} formSelector - CSS selector for form element
     */
    function init(formType, formSelector) {
        state.formType = formType;
        state.formSelector = formSelector;

        // Check if draft exists on page load
        checkForExistingDrafts();

        // Set up form change listeners
        attachFormListeners();

        // Start auto-save timer
        startAutoSave();

        // Save draft before page unload
        window.addEventListener('beforeunload', handleBeforeUnload);

        console.log(`[DraftAutoSave] Initialized for ${formType}`);
    }

    /**
     * Check for existing drafts and prompt user
     */
    async function checkForExistingDrafts() {
        // Skip check if we're already restoring a draft (via URL parameter)
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('draft_id')) {
            console.log('[DraftAutoSave] Already restoring from draft_id URL parameter');
            return;
        }

        try {
            const response = await fetch(`${CONFIG.API_ENDPOINT}/list?form_type=${state.formType}&limit=1`);
            const data = await response.json();

            if (data.success && data.drafts && data.drafts.length > 0) {
                const draft = data.drafts[0];
                const lastUpdated = new Date(draft.updated_at);
                const timeAgo = getTimeAgo(lastUpdated);

                // Show prompt to user
                const shouldRestore = confirm(
                    `Found a saved draft from ${timeAgo}.\n\n` +
                    `Would you like to restore it?\n\n` +
                    `Click OK to restore, or Cancel to start fresh.`
                );

                if (shouldRestore) {
                    // Redirect to the same page with draft_id parameter
                    // This will cause the server to pre-fill the form with draft data
                    const currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set('draft_id', draft.id);
                    window.location.href = currentUrl.toString();
                } else {
                    // User declined, delete the old draft
                    await deleteDraft(draft.id);
                }
            }
        } catch (error) {
            console.error('[DraftAutoSave] Error checking for drafts:', error);
        }
    }

    /**
     * Note: Draft restoration now happens server-side via URL parameter (?draft_id=123)
     * The server pre-fills the form_data when rendering the template, which is more
     * reliable than client-side restoration and properly handles complex fields.
     */

    /**
     * Attach change listeners to form inputs
     */
    function attachFormListeners() {
        const form = document.querySelector(state.formSelector);
        if (!form) {
            console.warn(`[DraftAutoSave] Form not found: ${state.formSelector}`);
            return;
        }

        // Listen for any input changes
        form.addEventListener('input', handleFormChange);
        form.addEventListener('change', handleFormChange);
    }

    /**
     * Handle form change events
     */
    function handleFormChange() {
        // Clear existing debounce timer
        if (state.debounceTimer) {
            clearTimeout(state.debounceTimer);
        }

        // Set dirty flag after debounce delay
        state.debounceTimer = setTimeout(() => {
            state.isDirty = true;
            updateSaveIndicator();
        }, CONFIG.DEBOUNCE_DELAY);
    }

    /**
     * Start the auto-save timer
     */
    function startAutoSave() {
        if (state.timer) {
            clearInterval(state.timer);
        }

        state.timer = setInterval(() => {
            if (state.isDirty && state.isEnabled) {
                saveDraft();
            }
        }, CONFIG.AUTOSAVE_INTERVAL);
    }

    /**
     * Save the current form data as a draft
     */
    async function saveDraft() {
        const form = document.querySelector(state.formSelector);
        if (!form) return;

        try {
            // Collect form data
            const formData = new FormData(form);
            const data = {};

            // Convert FormData to plain object
            for (let [key, value] of formData.entries()) {
                // Handle multiple values (checkboxes with same name)
                if (data[key]) {
                    if (!Array.isArray(data[key])) {
                        data[key] = [data[key]];
                    }
                    data[key].push(value);
                } else {
                    data[key] = value;
                }
            }

            // Send to server
            const response = await fetch(`${CONFIG.API_ENDPOINT}/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    form_type: state.formType,
                    form_data: data,
                    draft_id: state.draftId,
                }),
            });

            const result = await response.json();

            if (result.success) {
                state.draftId = result.draft_id;
                state.isDirty = false;
                state.lastSaveTime = new Date(result.updated_at);
                updateSaveIndicator();

                console.log(`[DraftAutoSave] Saved draft ${result.draft_id}`);
            } else {
                console.error('[DraftAutoSave] Failed to save draft:', result.error);
            }

        } catch (error) {
            console.error('[DraftAutoSave] Error saving draft:', error);
        }
    }

    /**
     * Delete a draft by ID
     */
    async function deleteDraft(draftId) {
        try {
            await fetch(`${CONFIG.API_ENDPOINT}/${draftId}`, {
                method: 'DELETE',
            });
            console.log(`[DraftAutoSave] Deleted draft ${draftId}`);
        } catch (error) {
            console.error('[DraftAutoSave] Error deleting draft:', error);
        }
    }

    /**
     * Handle before unload - save draft if dirty
     */
    function handleBeforeUnload(e) {
        if (state.isDirty && state.isEnabled) {
            // Modern browsers ignore custom messages, but this still works
            e.preventDefault();

            // Try to save synchronously (not ideal, but better than nothing)
            saveDraft();

            // Standard way to show "are you sure?" prompt
            e.returnValue = '';
        }
    }

    /**
     * Update the save indicator in the UI
     */
    function updateSaveIndicator() {
        let indicator = document.getElementById('draft-save-indicator');

        // Create indicator if it doesn't exist
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'draft-save-indicator';
            indicator.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                padding: 10px 15px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                border-radius: 5px;
                font-size: 13px;
                z-index: 9999;
                transition: opacity 0.3s;
            `;
            document.body.appendChild(indicator);
        }

        if (state.isDirty) {
            indicator.textContent = '⚠️ Unsaved changes';
            indicator.style.opacity = '1';
        } else if (state.lastSaveTime) {
            const timeAgo = getTimeAgo(state.lastSaveTime);
            indicator.textContent = `✓ Draft saved ${timeAgo}`;
            indicator.style.opacity = '0.7';

            // Fade out after 3 seconds
            setTimeout(() => {
                indicator.style.opacity = '0';
            }, 3000);
        }
    }

    /**
     * Show a notification to the user
     */
    function showNotification(message, type = 'info') {
        // Use existing flash message system if available
        const flashContainer = document.querySelector('.flashes');
        if (flashContainer) {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
            alertDiv.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            flashContainer.appendChild(alertDiv);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    }

    /**
     * Get human-readable time ago string
     */
    function getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);

        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
        return `${Math.floor(seconds / 86400)} days ago`;
    }

    /**
     * Manually trigger a save
     */
    function manualSave() {
        state.isDirty = true;
        saveDraft();
    }

    /**
     * Disable auto-save (useful when submitting form)
     */
    function disable() {
        state.isEnabled = false;
        if (state.timer) {
            clearInterval(state.timer);
        }
    }

    /**
     * Enable auto-save
     */
    function enable() {
        state.isEnabled = true;
        startAutoSave();
    }

    /**
     * Clean up - call when leaving page or form submitted
     */
    function cleanup() {
        disable();

        // Delete draft if form was successfully submitted
        if (state.draftId) {
            deleteDraft(state.draftId);
        }

        window.removeEventListener('beforeunload', handleBeforeUnload);
        console.log('[DraftAutoSave] Cleaned up');
    }

    /**
     * Set the draft ID (useful when restoring from URL parameter)
     */
    function setDraftId(id) {
        state.draftId = id;
    }

    // Public API
    return {
        init,
        manualSave,
        disable,
        enable,
        cleanup,
        setDraftId,
        get isDirty() { return state.isDirty; },
        get lastSaveTime() { return state.lastSaveTime; },
        get draftId() { return state.draftId; },
    };
})();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DraftAutoSave;
}
