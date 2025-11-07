/**
 * Test suite for keyboard-shortcuts.js
 * Tests keyboard shortcuts, table navigation, and help panel functionality
 */

// Mock the hotkeys library
global.hotkeys = jest.fn((keys, callback) => {
    if (!global.hotkeyHandlers) {
        global.hotkeyHandlers = {};
    }
    keys.split(',').forEach(key => {
        global.hotkeyHandlers[key.trim()] = callback;
    });
});

// Helper to trigger a hotkey
function triggerHotkey(key, event = {}) {
    const handler = global.hotkeyHandlers[key];
    if (handler) {
        const mockEvent = {
            preventDefault: jest.fn(),
            ...event
        };
        handler(mockEvent, null);
        return mockEvent;
    }
    return null;
}

describe('Keyboard Shortcuts', () => {
    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';

        // Reset global state
        global.helpVisible = false;
        global.hotkeyHandlers = {};
        global.hotkeys = jest.fn((keys, callback) => {
            keys.split(',').forEach(key => {
                global.hotkeyHandlers[key.trim()] = callback;
            });
        });

        // Load keyboard-shortcuts.js
        const fs = require('fs');
        const path = require('path');
        const ksPath = path.join(__dirname, '../../static/js/keyboard-shortcuts.js');
        const ksCode = fs.readFileSync(ksPath, 'utf8');
        eval(ksCode);
    });

    describe('toggleHelp()', () => {
        it('should toggle help panel visibility', () => {
            document.body.innerHTML = '<div id="floating-help"></div>';

            toggleHelp();

            const helpPanel = document.getElementById('floating-help');
            expect(helpPanel.classList.contains('show')).toBe(true);
            expect(global.helpVisible).toBe(true);
        });

        it('should hide help panel when called twice', () => {
            document.body.innerHTML = '<div id="floating-help"></div>';

            toggleHelp();
            toggleHelp();

            const helpPanel = document.getElementById('floating-help');
            expect(helpPanel.classList.contains('show')).toBe(false);
            expect(global.helpVisible).toBe(false);
        });

        it('should handle missing help panel', () => {
            const consoleError = jest.spyOn(console, 'error').mockImplementation();

            toggleHelp();

            expect(consoleError).toHaveBeenCalledWith('Help panel not found!');
            consoleError.mockRestore();
        });
    });

    describe('initializeKeyboardShortcuts()', () => {
        it('should register all form field shortcuts', () => {
            initializeKeyboardShortcuts();

            expect(global.hotkeys).toHaveBeenCalledWith('alt+c', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('alt+n', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('alt+s', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('alt+r', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('alt+i', expect.any(Function));
        });

        it('should focus customer ID field on alt+c', () => {
            const custIdField = document.createElement('input');
            custIdField.id = 'CustID';
            custIdField.focus = jest.fn();
            document.body.appendChild(custIdField);

            initializeKeyboardShortcuts();
            const event = triggerHotkey('alt+c');

            expect(custIdField.focus).toHaveBeenCalled();
            expect(event.preventDefault).toHaveBeenCalled();
        });

        it('should focus work order name field on alt+n', () => {
            const woNameField = document.createElement('input');
            woNameField.id = 'WOName';
            woNameField.focus = jest.fn();
            document.body.appendChild(woNameField);

            initializeKeyboardShortcuts();
            triggerHotkey('alt+n');

            expect(woNameField.focus).toHaveBeenCalled();
        });

        it('should toggle rush order checkbox on alt+u', () => {
            const rushCheckbox = document.createElement('input');
            rushCheckbox.id = 'RushOrder';
            rushCheckbox.type = 'checkbox';
            rushCheckbox.checked = false;
            rushCheckbox.dispatchEvent = jest.fn();
            document.body.appendChild(rushCheckbox);

            initializeKeyboardShortcuts();
            triggerHotkey('alt+u');

            expect(rushCheckbox.checked).toBe(true);
            expect(rushCheckbox.dispatchEvent).toHaveBeenCalled();
        });

        it('should handle missing hotkeys library', () => {
            const consoleError = jest.spyOn(console, 'error').mockImplementation();
            delete global.hotkeys;

            initializeKeyboardShortcuts();

            expect(consoleError).toHaveBeenCalledWith('hotkeys-js library not loaded!');
            consoleError.mockRestore();
        });

        it('should call addNewItem function on alt+a', () => {
            global.addNewItem = jest.fn();

            initializeKeyboardShortcuts();
            triggerHotkey('alt+a');

            expect(global.addNewItem).toHaveBeenCalled();
        });

        it('should handle missing addNewItem function', () => {
            const consoleWarn = jest.spyOn(console, 'warn').mockImplementation();
            delete global.addNewItem;

            initializeKeyboardShortcuts();
            triggerHotkey('alt+a');

            expect(consoleWarn).toHaveBeenCalledWith('addNewItem function not found');
            consoleWarn.mockRestore();
        });
    });

    describe('Form submission shortcuts', () => {
        it('should submit form on ctrl+shift+s', () => {
            const form = document.createElement('form');
            form.id = 'workOrderForm';
            const submitButton = document.createElement('button');
            submitButton.type = 'submit';
            submitButton.click = jest.fn();
            form.appendChild(submitButton);
            document.body.appendChild(form);

            initializeKeyboardShortcuts();
            triggerHotkey('ctrl+shift+s');

            expect(submitButton.click).toHaveBeenCalled();
        });

        it('should handle missing submit button', () => {
            const form = document.createElement('form');
            form.id = 'workOrderForm';
            form.submit = jest.fn();
            document.body.appendChild(form);

            initializeKeyboardShortcuts();
            triggerHotkey('ctrl+shift+s');

            expect(form.submit).toHaveBeenCalled();
        });
    });

    describe('ESC key behavior', () => {
        it('should close help panel first if open', () => {
            document.body.innerHTML = '<div id="floating-help" class="show"></div>';
            global.helpVisible = true;

            initializeKeyboardShortcuts();
            const event = triggerHotkey('escape');

            expect(global.helpVisible).toBe(false);
            expect(event.preventDefault).toHaveBeenCalled();
        });

        it('should blur focused element if no help is open', () => {
            const input = document.createElement('input');
            input.blur = jest.fn();
            document.body.appendChild(input);

            Object.defineProperty(document, 'activeElement', {
                value: input,
                writable: true,
                configurable: true
            });

            initializeKeyboardShortcuts();
            triggerHotkey('escape');

            expect(input.blur).toHaveBeenCalled();
        });

        it('should prompt to cancel if nothing focused', () => {
            window.confirm = jest.fn().mockReturnValue(false);
            window.history = { back: jest.fn() };

            Object.defineProperty(document, 'activeElement', {
                value: document.body,
                writable: true,
                configurable: true
            });

            initializeKeyboardShortcuts();
            triggerHotkey('escape');

            expect(window.confirm).toHaveBeenCalledWith(
                expect.stringContaining('Are you sure you want to cancel')
            );
        });
    });

    describe('File upload shortcut', () => {
        it('should trigger file input click on alt+f', () => {
            const fileInput = document.createElement('input');
            fileInput.id = 'files';
            fileInput.type = 'file';
            fileInput.click = jest.fn();
            document.body.appendChild(fileInput);

            initializeKeyboardShortcuts();
            triggerHotkey('alt+f');

            expect(fileInput.click).toHaveBeenCalled();
        });
    });

    describe('Edit order shortcut', () => {
        it('should click repair edit button on ctrl+e', () => {
            const editButton = document.createElement('a');
            editButton.className = 'btn-warning';
            editButton.href = '/repair_work_orders/123/edit';
            editButton.click = jest.fn();
            document.body.appendChild(editButton);

            initializeKeyboardShortcuts();
            triggerHotkey('ctrl+e');

            expect(editButton.click).toHaveBeenCalled();
        });

        it('should fallback to clean edit button if no repair button', () => {
            const editButton = document.createElement('a');
            editButton.className = 'btn-primary';
            editButton.href = '/work_orders/123/edit';
            editButton.click = jest.fn();
            document.body.appendChild(editButton);

            initializeKeyboardShortcuts();
            triggerHotkey('ctrl+e');

            expect(editButton.click).toHaveBeenCalled();
        });
    });

    describe('initializeGlobalShortcuts()', () => {
        beforeEach(() => {
            // Mock window.location to prevent navigation errors in jsdom
            delete window.location;
            window.location = { href: '' };
        });

        it('should register navigation shortcuts', () => {
            initializeGlobalShortcuts();

            expect(global.hotkeys).toHaveBeenCalledWith(
                expect.stringContaining('ctrl+shift+1'),
                expect.any(Function)
            );
        });

        it('should set location href for sources on ctrl+shift+1', () => {
            initializeGlobalShortcuts();
            triggerHotkey('ctrl+shift+1');

            expect(window.location.href).toBe('/sources');
        });

        it('should set location href for customers on ctrl+shift+2', () => {
            initializeGlobalShortcuts();
            triggerHotkey('ctrl+shift+2');

            expect(window.location.href).toBe('/customers');
        });

        it('should set location href for work orders on ctrl+shift+3', () => {
            initializeGlobalShortcuts();
            triggerHotkey('ctrl+shift+3');

            expect(window.location.href).toBe('/work_orders');
        });

        it('should handle missing hotkeys library', () => {
            const consoleWarn = jest.spyOn(console, 'warn').mockImplementation();
            const originalHotkeys = global.hotkeys;
            delete global.hotkeys;

            initializeGlobalShortcuts();

            expect(consoleWarn).toHaveBeenCalledWith('hotkeys-js not loaded for global shortcuts');
            consoleWarn.mockRestore();
            global.hotkeys = originalHotkeys;
        });
    });

    describe('TableNavigator class', () => {
        let navigator;

        beforeEach(() => {
            navigator = new TableNavigator();
        });

        describe('constructor', () => {
            it('should initialize with default values', () => {
                expect(navigator.selectedRowIndex).toBe(-1);
                expect(navigator.table).toBeNull();
                expect(navigator.tableType).toBeNull();
                expect(navigator.rows).toEqual([]);
            });
        });

        describe('initStandardTable()', () => {
            it('should initialize for standard HTML table', () => {
                document.body.innerHTML = `
                    <table class="table">
                        <tbody>
                            <tr><td>Row 1</td></tr>
                            <tr><td>Row 2</td></tr>
                        </tbody>
                    </table>
                `;

                navigator.initStandardTable();

                expect(navigator.table).not.toBeNull();
            });

            it('should handle missing table', () => {
                navigator.initStandardTable();

                expect(navigator.table).toBeNull();
            });
        });

        describe('getStandardRows()', () => {
            it('should return array of table rows', () => {
                document.body.innerHTML = `
                    <table class="table">
                        <tbody>
                            <tr><td>Row 1</td></tr>
                            <tr><td>Row 2</td></tr>
                        </tbody>
                    </table>
                `;

                navigator.table = document.querySelector('table.table tbody');
                const rows = navigator.getStandardRows();

                expect(rows.length).toBe(2);
            });

            it('should return empty array if no table', () => {
                const rows = navigator.getStandardRows();

                expect(rows).toEqual([]);
            });
        });

        describe('selectStandardRow()', () => {
            beforeEach(() => {
                document.body.innerHTML = `
                    <table class="table">
                        <tbody>
                            <tr><td>Row 1</td></tr>
                            <tr><td>Row 2</td></tr>
                            <tr><td>Row 3</td></tr>
                        </tbody>
                    </table>
                `;
                navigator.table = document.querySelector('table.table tbody');
            });

            it('should add selection class to specified row', () => {
                navigator.selectStandardRow(1);

                const rows = navigator.getStandardRows();
                expect(rows[1].classList.contains('table-active')).toBe(true);
                expect(navigator.selectedRowIndex).toBe(1);
            });

            it('should remove selection from previously selected row', () => {
                navigator.selectStandardRow(0);
                navigator.selectStandardRow(1);

                const rows = navigator.getStandardRows();
                expect(rows[0].classList.contains('table-active')).toBe(false);
                expect(rows[1].classList.contains('table-active')).toBe(true);
            });

            it('should handle invalid index', () => {
                navigator.selectStandardRow(999);

                const rows = navigator.getStandardRows();
                rows.forEach(row => {
                    expect(row.classList.contains('table-active')).toBe(false);
                });
            });
        });

        describe('isInputFocused()', () => {
            it('should return true for focused input', () => {
                const input = document.createElement('input');
                Object.defineProperty(document, 'activeElement', {
                    value: input,
                    writable: true,
                    configurable: true
                });

                expect(navigator.isInputFocused()).toBe(true);
            });

            it('should return true for focused textarea', () => {
                const textarea = document.createElement('textarea');
                Object.defineProperty(document, 'activeElement', {
                    value: textarea,
                    writable: true,
                    configurable: true
                });

                expect(navigator.isInputFocused()).toBe(true);
            });

            it('should return false for non-input elements', () => {
                const div = document.createElement('div');
                Object.defineProperty(document, 'activeElement', {
                    value: div,
                    writable: true,
                    configurable: true
                });

                expect(navigator.isInputFocused()).toBe(false);
            });
        });

        describe('clearSelection()', () => {
            it('should clear standard table selection', () => {
                document.body.innerHTML = `
                    <table class="table">
                        <tbody>
                            <tr class="table-active"><td>Row 1</td></tr>
                        </tbody>
                    </table>
                `;
                navigator.tableType = 'standard';
                navigator.table = document.querySelector('table.table tbody');
                navigator.selectedRowIndex = 0;

                navigator.clearSelection();

                const rows = navigator.getStandardRows();
                expect(rows[0].classList.contains('table-active')).toBe(false);
                expect(navigator.selectedRowIndex).toBe(-1);
            });
        });
    });

    describe('initializeTableShortcuts()', () => {
        it('should initialize table navigator', () => {
            initializeTableShortcuts();

            expect(global.tableNavigator).toBeDefined();
            expect(global.tableNavigator).toBeInstanceOf(TableNavigator);
        });

        it('should register navigation shortcuts', () => {
            initializeTableShortcuts();

            expect(global.hotkeys).toHaveBeenCalledWith('j', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('k', expect.any(Function));
            expect(global.hotkeys).toHaveBeenCalledWith('enter', expect.any(Function));
        });

        it('should handle missing hotkeys library', () => {
            const consoleWarn = jest.spyOn(console, 'warn').mockImplementation();
            delete global.hotkeys;

            initializeTableShortcuts();

            expect(consoleWarn).toHaveBeenCalledWith('hotkeys-js not loaded for table shortcuts');
            consoleWarn.mockRestore();
        });
    });

    describe('clearAllFilters()', () => {
        it('should click clear filters button if present', () => {
            const clearButton = document.createElement('button');
            clearButton.id = 'clear-filters-btn';
            clearButton.click = jest.fn();
            document.body.appendChild(clearButton);

            clearAllFilters();

            expect(clearButton.click).toHaveBeenCalled();
        });

        it('should fallback to table.clearHeaderFilter if no button', () => {
            global.workOrdersTable = {
                clearHeaderFilter: jest.fn(),
                setData: jest.fn()
            };

            clearAllFilters();

            expect(global.workOrdersTable.clearHeaderFilter).toHaveBeenCalled();
        });

        it('should handle no table or button found', () => {
            const consoleWarn = jest.spyOn(console, 'warn').mockImplementation();

            clearAllFilters();

            expect(consoleWarn).toHaveBeenCalledWith('No table or clear button found');
            consoleWarn.mockRestore();
        });
    });

    describe('DOMContentLoaded event', () => {
        it('should initialize all shortcuts on page load', () => {
            const initKbShortcuts = jest.fn();
            const initGlobalShortcuts = jest.fn();
            const initTableShortcuts = jest.fn();

            global.initializeKeyboardShortcuts = initKbShortcuts;
            global.initializeGlobalShortcuts = initGlobalShortcuts;
            global.initializeTableShortcuts = initTableShortcuts;

            // Trigger DOMContentLoaded
            const event = new Event('DOMContentLoaded');
            document.dispatchEvent(event);

            expect(initKbShortcuts).toHaveBeenCalled();
            expect(initGlobalShortcuts).toHaveBeenCalled();
            expect(initTableShortcuts).toHaveBeenCalled();
        });
    });
});