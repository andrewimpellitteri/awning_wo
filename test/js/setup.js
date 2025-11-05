/**
 * Jest setup file
 * Runs before each test file
 */

// Add custom matchers from @testing-library/jest-dom
require('@testing-library/jest-dom');

// Polyfill DataTransfer for JSDOM (not available by default)
// This needs to be set up BEFORE importing any modules that use DataTransfer
class MockFileList extends Array {
    item(index) {
        return this[index];
    }
}

if (typeof DataTransfer === 'undefined') {
    global.DataTransfer = class DataTransfer {
        constructor() {
            this._files = new MockFileList();
            this.items = {
                add: (file) => {
                    this._files.push(file);
                }
            };
        }

        get files() {
            // Create a FileList-like object
            const fileList = new MockFileList(...this._files);
            Object.defineProperty(fileList, 'length', {
                value: this._files.length,
                writable: false
            });
            return fileList;
        }

        set files(value) {
            this._files = new MockFileList(...Array.from(value));
        }
    };
}

// Mock console methods to reduce noise in tests (optional)
global.console = {
  ...console,
  // Uncomment to suppress console.error in tests
  // error: jest.fn(),
  // Uncomment to suppress console.warn in tests
  // warn: jest.fn(),
};

// Global test utilities
global.createMockElement = (tag, attributes = {}) => {
  const element = document.createElement(tag);
  Object.entries(attributes).forEach(([key, value]) => {
    if (key.startsWith('data-')) {
      element.setAttribute(key, value);
    } else if (key === 'className') {
      element.className = value;
    } else if (key === 'innerHTML') {
      element.innerHTML = value;
    } else {
      element[key] = value;
    }
  });
  return element;
};