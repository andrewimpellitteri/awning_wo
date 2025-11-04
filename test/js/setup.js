/**
 * Jest setup file
 * Runs before each test file
 */

// Add custom matchers from @testing-library/jest-dom
require('@testing-library/jest-dom');

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