# JavaScript Tests

This directory contains Jest tests for the frontend JavaScript code.

## Setup

Install dependencies:
```bash
npm install
```

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode (during development)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run tests in CI mode (used by GitHub Actions)
npm run test:ci
```

## Test Structure

- `setup.js` - Global test setup and utilities
- `order-form-shared.test.js` - Tests for inventory item management functions

## Writing Tests

Tests use Jest with jsdom environment to simulate browser DOM APIs.

Example test:
```javascript
describe('MyFunction', () => {
    test('should do something', () => {
        const result = myFunction('input');
        expect(result).toBe('expected output');
    });
});
```

## Coverage Thresholds

Current coverage thresholds (defined in package.json):
- Branches: 50%
- Functions: 60%
- Lines: 60%
- Statements: 60%

These will fail the build if not met.

## Continuous Integration

JavaScript tests run automatically in GitHub Actions on every push and pull request.
Coverage badges are generated and updated in the repository.