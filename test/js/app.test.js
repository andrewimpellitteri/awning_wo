/**
 * Test suite for app.js
 * Tests utility functions, work order management, form validation, and export functionality
 */

describe('App.js Utility Functions', () => {
    let mockDocument;

    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';

        // Mock bootstrap components
        global.bootstrap = {
            Tooltip: jest.fn().mockImplementation(() => ({})),
            Popover: jest.fn().mockImplementation(() => ({})),
            Alert: jest.fn().mockImplementation(() => ({
                close: jest.fn()
            })),
            Toast: jest.fn().mockImplementation(() => ({
                show: jest.fn()
            }))
        };

        // Load app.js functions
        const fs = require('fs');
        const path = require('path');
        const appPath = path.join(__dirname, '../../static/js/app.js');
        const appCode = fs.readFileSync(appPath, 'utf8');

        // Extract only the function definitions we need to test
        eval(appCode);
    });

    describe('Utils.formatCurrency()', () => {
        it('should format numbers as USD currency', () => {
            const result = Utils.formatCurrency(1000);
            expect(result).toBe('$1,000.00');
        });

        it('should handle decimal values', () => {
            const result = Utils.formatCurrency(1234.56);
            expect(result).toBe('$1,234.56');
        });

        it('should handle zero', () => {
            const result = Utils.formatCurrency(0);
            expect(result).toBe('$0.00');
        });

        it('should handle negative numbers', () => {
            const result = Utils.formatCurrency(-500);
            expect(result).toBe('-$500.00');
        });

        it('should handle very large numbers', () => {
            const result = Utils.formatCurrency(1000000);
            expect(result).toBe('$1,000,000.00');
        });
    });

    describe('Utils.formatDate()', () => {
        it('should format valid date strings', () => {
            const result = Utils.formatDate('2025-01-15');
            expect(result).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
        });

        it('should return "-" for null dates', () => {
            const result = Utils.formatDate(null);
            expect(result).toBe('-');
        });

        it('should return "-" for undefined dates', () => {
            const result = Utils.formatDate(undefined);
            expect(result).toBe('-');
        });

        it('should return "-" for empty string', () => {
            const result = Utils.formatDate('');
            expect(result).toBe('-');
        });

        it('should handle Date objects', () => {
            const date = new Date('2025-01-15');
            const result = Utils.formatDate(date);
            expect(result).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
        });
    });

    describe('Utils.showLoading()', () => {
        it('should add loading spinner to element', () => {
            const button = document.createElement('button');
            button.innerHTML = 'Submit';
            button.disabled = false;

            Utils.showLoading(button);

            expect(button.innerHTML).toContain('spinner-border');
            expect(button.innerHTML).toContain('Loading...');
            expect(button.disabled).toBe(true);
        });

        it('should disable the element', () => {
            const button = document.createElement('button');
            button.disabled = false;

            Utils.showLoading(button);

            expect(button.disabled).toBe(true);
        });
    });

    describe('Utils.hideLoading()', () => {
        it('should restore original text and enable element', () => {
            const button = document.createElement('button');
            button.innerHTML = '<span class="spinner-border"></span> Loading...';
            button.disabled = true;

            Utils.hideLoading(button, 'Submit');

            expect(button.innerHTML).toBe('Submit');
            expect(button.disabled).toBe(false);
        });

        it('should handle empty original text', () => {
            const button = document.createElement('button');
            button.innerHTML = 'Loading...';
            button.disabled = true;

            Utils.hideLoading(button, '');

            expect(button.innerHTML).toBe('');
            expect(button.disabled).toBe(false);
        });
    });

    describe('Utils.showToast()', () => {
        it('should create toast container if it does not exist', () => {
            expect(document.getElementById('toast-container')).toBeNull();

            Utils.showToast('Test message');

            const container = document.getElementById('toast-container');
            expect(container).not.toBeNull();
            expect(container.className).toContain('toast-container');
        });

        it('should create toast with message', () => {
            Utils.showToast('Test message', 'success');

            const container = document.getElementById('toast-container');
            const toast = container.querySelector('.toast');
            expect(toast).not.toBeNull();
            expect(toast.innerHTML).toContain('Test message');
        });

        it('should apply correct type class', () => {
            Utils.showToast('Error message', 'danger');

            const toast = document.querySelector('.toast');
            expect(toast.className).toContain('bg-danger');
        });

        it('should default to info type', () => {
            Utils.showToast('Info message');

            const toast = document.querySelector('.toast');
            expect(toast.className).toContain('bg-info');
        });

        it('should reuse existing toast container', () => {
            Utils.showToast('First message');
            Utils.showToast('Second message');

            const containers = document.querySelectorAll('#toast-container');
            expect(containers.length).toBe(1);
        });

        it('should include close button', () => {
            Utils.showToast('Test message');

            const closeButton = document.querySelector('.btn-close');
            expect(closeButton).not.toBeNull();
        });
    });

    describe('searchCustomers()', () => {
        beforeEach(() => {
            global.fetch = jest.fn();
        });

        afterEach(() => {
            jest.restoreAllMocks();
        });

        it('should not search for queries shorter than 2 characters', () => {
            searchCustomers('a');
            expect(global.fetch).not.toHaveBeenCalled();
        });

        it('should make fetch request for valid queries', () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue([])
            });

            searchCustomers('test');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/customers/search?q=test')
            );
        });

        it('should encode query parameters', () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue([])
            });

            searchCustomers('test & query');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('test%20%26%20query')
            );
        });

        it('should handle fetch errors', async () => {
            const consoleError = jest.spyOn(console, 'error').mockImplementation();
            global.fetch.mockRejectedValue(new Error('Network error'));

            await searchCustomers('test');

            // Wait for promise to resolve
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(consoleError).toHaveBeenCalledWith(
                'Error searching customers:',
                expect.any(Error)
            );

            consoleError.mockRestore();
        });
    });

    describe('WorkOrder.addItem()', () => {
        beforeEach(() => {
            global.fetch = jest.fn();
            global.location = { reload: jest.fn() };
        });

        afterEach(() => {
            jest.restoreAllMocks();
        });

        it('should make POST request with item data', () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ success: true })
            });

            const itemData = { description: 'Test Item', quantity: 1 };
            WorkOrder.addItem(123, itemData);

            expect(global.fetch).toHaveBeenCalledWith(
                '/api/work-orders/123/items',
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(itemData)
                })
            );
        });

        it('should reload page on success', async () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ success: true })
            });

            await WorkOrder.addItem(123, {});

            // Wait for promise to resolve
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(global.location.reload).toHaveBeenCalled();
        });

        it('should show success toast on successful add', async () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ success: true })
            });

            const showToastSpy = jest.spyOn(Utils, 'showToast');

            await WorkOrder.addItem(123, {});
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(showToastSpy).toHaveBeenCalledWith('Item added successfully', 'success');
        });

        it('should show error toast on failure', async () => {
            global.fetch.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ success: false })
            });

            const showToastSpy = jest.spyOn(Utils, 'showToast');

            await WorkOrder.addItem(123, {});
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(showToastSpy).toHaveBeenCalledWith('Error adding item', 'danger');
        });

        it('should handle fetch errors', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            const showToastSpy = jest.spyOn(Utils, 'showToast');
            const consoleError = jest.spyOn(console, 'error').mockImplementation();

            await WorkOrder.addItem(123, {});
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(showToastSpy).toHaveBeenCalledWith('Error adding item', 'danger');
            expect(consoleError).toHaveBeenCalled();

            consoleError.mockRestore();
        });
    });

    describe('validateForm()', () => {
        it('should return true for valid form', () => {
            document.body.innerHTML = `
                <form id="testForm">
                    <input type="text" required value="test" />
                    <input type="email" required value="test@example.com" />
                </form>
            `;

            const result = validateForm('testForm');
            expect(result).toBe(true);
        });

        it('should return false for form with empty required fields', () => {
            document.body.innerHTML = `
                <form id="testForm">
                    <input type="text" required value="" />
                    <input type="email" required value="test@example.com" />
                </form>
            `;

            const result = validateForm('testForm');
            expect(result).toBe(false);
        });

        it('should add is-invalid class to empty required fields', () => {
            document.body.innerHTML = `
                <form id="testForm">
                    <input type="text" id="field1" required value="" />
                </form>
            `;

            validateForm('testForm');

            const field = document.getElementById('field1');
            expect(field.classList.contains('is-invalid')).toBe(true);
        });

        it('should remove is-invalid class from valid fields', () => {
            document.body.innerHTML = `
                <form id="testForm">
                    <input type="text" id="field1" class="is-invalid" required value="test" />
                </form>
            `;

            validateForm('testForm');

            const field = document.getElementById('field1');
            expect(field.classList.contains('is-invalid')).toBe(false);
        });

        it('should return false if form does not exist', () => {
            const result = validateForm('nonexistentForm');
            expect(result).toBe(false);
        });

        it('should handle whitespace-only values as invalid', () => {
            document.body.innerHTML = `
                <form id="testForm">
                    <input type="text" required value="   " />
                </form>
            `;

            const result = validateForm('testForm');
            expect(result).toBe(false);
        });
    });

    describe('Export.convertToCSV()', () => {
        it('should convert array of objects to CSV', () => {
            const data = [
                { name: 'John', age: 30 },
                { name: 'Jane', age: 25 }
            ];

            const result = Export.convertToCSV(data);
            const lines = result.split('\n');

            expect(lines[0]).toBe('name,age');
            expect(lines[1]).toContain('John');
            expect(lines[1]).toContain('30');
        });

        it('should return empty string for empty array', () => {
            const result = Export.convertToCSV([]);
            expect(result).toBe('');
        });

        it('should return empty string for null', () => {
            const result = Export.convertToCSV(null);
            expect(result).toBe('');
        });

        it('should handle values with commas by quoting', () => {
            const data = [
                { name: 'Doe, John', company: 'Acme Corp' }
            ];

            const result = Export.convertToCSV(data);
            expect(result).toContain('"Doe, John"');
        });

        it('should handle empty values', () => {
            const data = [
                { name: 'John', email: null },
                { name: 'Jane', email: '' }
            ];

            const result = Export.convertToCSV(data);
            expect(result).toContain('""'); // Empty quoted string for null/empty
        });

        it('should handle special characters', () => {
            const data = [
                { name: 'Test "Quote"', notes: 'Line\nBreak' }
            ];

            const result = Export.convertToCSV(data);
            expect(result).toContain('"Test \\"Quote\\""');
        });
    });

    describe('Export.downloadCSV()', () => {
        let createElementSpy;
        let appendChildSpy;
        let removeChildSpy;
        let mockAnchor;

        beforeEach(() => {
            mockAnchor = {
                setAttribute: jest.fn(),
                click: jest.fn(),
                href: ''
            };

            createElementSpy = jest.spyOn(document, 'createElement').mockReturnValue(mockAnchor);
            appendChildSpy = jest.spyOn(document.body, 'appendChild').mockImplementation();
            removeChildSpy = jest.spyOn(document.body, 'removeChild').mockImplementation();

            global.URL = {
                createObjectURL: jest.fn().mockReturnValue('blob:mock-url'),
                revokeObjectURL: jest.fn()
            };

            global.Blob = jest.fn();
        });

        afterEach(() => {
            createElementSpy.mockRestore();
            appendChildSpy.mockRestore();
            removeChildSpy.mockRestore();
        });

        it('should create blob with correct type', () => {
            Export.downloadCSV('test,data', 'test.csv');

            expect(global.Blob).toHaveBeenCalledWith(
                ['test,data'],
                { type: 'text/csv' }
            );
        });

        it('should create download link with correct filename', () => {
            Export.downloadCSV('test,data', 'export.csv');

            expect(mockAnchor.setAttribute).toHaveBeenCalledWith('download', 'export.csv');
        });

        it('should trigger download by clicking link', () => {
            Export.downloadCSV('test,data', 'test.csv');

            expect(mockAnchor.click).toHaveBeenCalled();
        });

        it('should clean up URL after download', () => {
            Export.downloadCSV('test,data', 'test.csv');

            expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
        });

        it('should remove anchor element after download', () => {
            Export.downloadCSV('test,data', 'test.csv');

            expect(removeChildSpy).toHaveBeenCalledWith(mockAnchor);
        });
    });

    describe('Export.toCSV()', () => {
        beforeEach(() => {
            jest.spyOn(Export, 'downloadCSV').mockImplementation();
        });

        it('should convert data and trigger download', () => {
            const data = [{ name: 'John', age: 30 }];

            Export.toCSV(data, 'test.csv');

            expect(Export.downloadCSV).toHaveBeenCalledWith(
                expect.stringContaining('name,age'),
                'test.csv'
            );
        });
    });
});