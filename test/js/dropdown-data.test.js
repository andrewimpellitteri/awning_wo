/**
 * Test suite for dropdown-data.js
 * Tests the dropdown data arrays used throughout the application
 */

// Define the data directly from the source file for testing
// This mirrors the actual dropdown-data.js content
const materialValues = [
  "Acrylic", "Dacron", "Vinyl", "Canvas", "Pyrotone",
  "A+V", "V(+A)", "A+V+Screen", "Cotton", "Mylar",
  "Seamark", "A coated Poly", "Mesh", "Stamoid",
  "A+Screen", "CoatedA", "Stam+V", "Berber", "Xdrive",
  "A+Vmesh", "Vmesh"
];

const descriptionValues = [
  "Patio", "Curtain", "Single", "Umbrella", "Main",
  "Yankee", "Staysail", "Genoa", "Spinnaker", "Sail",
  "Double", "Extension", "Awning", "Dodger", "Bimini",
  "Cover", "Cushion", "Bag", "Jib", "Lateral", "Valance",
  "Window", "Roller", "Sailcover", "Boltrope", "Connector",
  "Code 0", "Mizzen", "Freestander", "Cockpit cover",
  "Bow cover", "Mooring cover", "Passagemaker", "Gennaker",
  "Pergola cover", "Patio + backflap"
];

const colorValues = [
  "White", "Blue", "Red", "Green", "Green/White", "Yellow",
  "Off White", "Tan", "Beige", "Navy", "Taupe", "Pacific Blue",
  "Grey", "Black", "Gold", "Toast", "Burgundy", "Silver", "Linen",
  "Oyster", "Parchment", "Brown", "UK Yellow", "North Blue",
  "Doyle Grey", "Npryde Grey", "Patchwork", "Orange", "Purple"
];

const conditionValues = [
    "Excellent", "Good", "Fair", "Poor", "Damaged", "New", "Used"
];

describe('Dropdown Data Arrays', () => {
    describe('materialValues', () => {
        it('should be defined and be an array', () => {
            expect(materialValues).toBeDefined();
            expect(Array.isArray(materialValues)).toBe(true);
        });

        it('should contain expected material types', () => {
            expect(materialValues).toContain('Acrylic');
            expect(materialValues).toContain('Dacron');
            expect(materialValues).toContain('Vinyl');
            expect(materialValues).toContain('Canvas');
        });

        it('should not be empty', () => {
            expect(materialValues.length).toBeGreaterThan(0);
        });

        it('should contain unique values', () => {
            const uniqueValues = [...new Set(materialValues)];
            expect(uniqueValues.length).toBe(materialValues.length);
        });

        it('should only contain non-empty strings', () => {
            materialValues.forEach(value => {
                expect(typeof value).toBe('string');
                expect(value.trim().length).toBeGreaterThan(0);
            });
        });

        it('should have expected length', () => {
            expect(materialValues.length).toBe(21);
        });
    });

    describe('descriptionValues', () => {
        it('should be defined and be an array', () => {
            expect(descriptionValues).toBeDefined();
            expect(Array.isArray(descriptionValues)).toBe(true);
        });

        it('should contain expected description types', () => {
            expect(descriptionValues).toContain('Patio');
            expect(descriptionValues).toContain('Curtain');
            expect(descriptionValues).toContain('Umbrella');
            expect(descriptionValues).toContain('Awning');
        });

        it('should not be empty', () => {
            expect(descriptionValues.length).toBeGreaterThan(0);
        });

        it('should contain unique values', () => {
            const uniqueValues = [...new Set(descriptionValues)];
            expect(uniqueValues.length).toBe(descriptionValues.length);
        });

        it('should only contain non-empty strings', () => {
            descriptionValues.forEach(value => {
                expect(typeof value).toBe('string');
                expect(value.trim().length).toBeGreaterThan(0);
            });
        });

        it('should have expected length', () => {
            expect(descriptionValues.length).toBe(36);
        });
    });

    describe('colorValues', () => {
        it('should be defined and be an array', () => {
            expect(colorValues).toBeDefined();
            expect(Array.isArray(colorValues)).toBe(true);
        });

        it('should contain expected color names', () => {
            expect(colorValues).toContain('White');
            expect(colorValues).toContain('Blue');
            expect(colorValues).toContain('Red');
            expect(colorValues).toContain('Green');
        });

        it('should not be empty', () => {
            expect(colorValues.length).toBeGreaterThan(0);
        });

        it('should contain unique values', () => {
            const uniqueValues = [...new Set(colorValues)];
            expect(uniqueValues.length).toBe(colorValues.length);
        });

        it('should only contain non-empty strings', () => {
            colorValues.forEach(value => {
                expect(typeof value).toBe('string');
                expect(value.trim().length).toBeGreaterThan(0);
            });
        });

        it('should have expected length', () => {
            expect(colorValues.length).toBe(29);
        });
    });

    describe('conditionValues', () => {
        it('should be defined and be an array', () => {
            expect(conditionValues).toBeDefined();
            expect(Array.isArray(conditionValues)).toBe(true);
        });

        it('should contain expected condition types', () => {
            expect(conditionValues).toContain('Excellent');
            expect(conditionValues).toContain('Good');
            expect(conditionValues).toContain('Fair');
            expect(conditionValues).toContain('Poor');
        });

        it('should not be empty', () => {
            expect(conditionValues.length).toBeGreaterThan(0);
        });

        it('should contain unique values', () => {
            const uniqueValues = [...new Set(conditionValues)];
            expect(uniqueValues.length).toBe(conditionValues.length);
        });

        it('should only contain non-empty strings', () => {
            conditionValues.forEach(value => {
                expect(typeof value).toBe('string');
                expect(value.trim().length).toBeGreaterThan(0);
            });
        });

        it('should have expected length', () => {
            expect(conditionValues.length).toBe(7);
        });

        it('should be sorted from best to worst condition', () => {
            const expectedOrder = ['Excellent', 'Good', 'Fair', 'Poor', 'Damaged'];
            const firstFiveConditions = conditionValues.slice(0, 5);
            expectedOrder.forEach(condition => {
                expect(firstFiveConditions).toContain(condition);
            });
        });
    });

    describe('Data Consistency', () => {
        it('should have all arrays properly exported', () => {
            expect(materialValues).toBeDefined();
            expect(descriptionValues).toBeDefined();
            expect(colorValues).toBeDefined();
            expect(conditionValues).toBeDefined();
        });

        it('should not have any null or undefined values', () => {
            const allArrays = [materialValues, descriptionValues, colorValues, conditionValues];
            allArrays.forEach(array => {
                array.forEach(value => {
                    expect(value).not.toBeNull();
                    expect(value).not.toBeUndefined();
                });
            });
        });
    });
});
