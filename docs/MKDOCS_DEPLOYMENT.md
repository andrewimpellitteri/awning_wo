# MkDocs Deployment Guide

## Overview

This project uses **MkDocs** with the **Material theme** for documentation. The documentation is automatically built and can be deployed to GitHub Pages or viewed locally.

## Local Development

### Prerequisites

MkDocs and dependencies are already listed in `requirements.txt`:
```txt
mkdocs
mkdocs-material
```

### Serving Documentation Locally

```bash
# Serve docs with live reload
mkdocs serve

# Visit http://127.0.0.1:8000
```

The documentation will automatically reload when you make changes to any `.md` files in the `docs/` directory.

### Building Documentation

```bash
# Build documentation to site/ directory
mkdocs build

# Build with strict mode (fails on warnings)
mkdocs build --strict
```

## GitHub Pages Deployment

### Automatic Deployment

The easiest way to deploy to GitHub Pages:

```bash
# Deploy to gh-pages branch
mkdocs gh-deploy

# With custom commit message
mkdocs gh-deploy -m "Updated docs with new utility functions guide"
```

This command will:
1. Build the documentation
2. Push it to the `gh-pages` branch
3. GitHub Pages will automatically serve it

### Manual Deployment

If you prefer manual control:

```bash
# Build documentation
mkdocs build

# The built site is in site/ directory
# Copy contents to your web server
```

## Project Structure

```
awning_wo/
├── mkdocs.yml                          # MkDocs configuration
├── docs/                               # Documentation source files
│   ├── index.md                        # Homepage
│   ├── user-guide/                     # User documentation
│   │   ├── index.md
│   │   ├── getting-started.md
│   │   └── work-orders.md
│   ├── developer-guide/                # Developer documentation
│   │   ├── index.md
│   │   ├── setup.md
│   │   ├── utility-functions.md        # ✨ NEW
│   │   ├── testing.md                  # ✨ NEW
│   │   ├── file-uploads.md             # ✨ NEW
│   │   ├── project-structure.md
│   │   ├── database-schema.md
│   │   └── ...
│   ├── database/                       # Database docs
│   ├── deployment/                     # Deployment guides
│   ├── architecture/                   # Architecture docs
│   ├── planning/                       # Planning docs
│   └── reference/                      # Reference docs
└── site/                               # Built documentation (git-ignored)
```

## Configuration

### MkDocs Configuration (`mkdocs.yml`)

Key sections:

```yaml
site_name: Awning Management System Documentation
site_url: https://andrewimpellitteri.github.com/awning_wo
repo_url: https://github.com/andrewimpellitteri/awning_wo

theme:
  name: material
  palette:
    # Light/dark mode toggle
  features:
    - navigation.tabs
    - navigation.sections
    - search.suggest
    - content.code.copy
    - content.mermaid

nav:
  - Home: index.md
  - User Guide:
      - user-guide/index.md
      - Getting Started: user-guide/getting-started.md
  - Developer Guide:
      - developer-guide/index.md
      - Utility Functions: developer-guide/utility-functions.md  # NEW
      - Testing: developer-guide/testing.md                      # NEW
      - File Uploads: developer-guide/file-uploads.md            # NEW
  # ... more sections

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - admonition
  - tables
  - toc
```

## Adding New Documentation

### 1. Create the Markdown File

```bash
# Create a new doc file
touch docs/developer-guide/new-feature.md
```

### 2. Write Content

```markdown
# New Feature Guide

## Overview

Description of the new feature...

## Usage

Examples and code snippets...
```

### 3. Update Navigation

Edit `mkdocs.yml` to add the new page:

```yaml
nav:
  - Developer Guide:
      - New Feature: developer-guide/new-feature.md
```

### 4. Test Locally

```bash
mkdocs serve
```

### 5. Deploy

```bash
mkdocs gh-deploy
```

## Recently Added Documentation

The following comprehensive guides were recently added:

### 1. **Utility Functions Reference** ([developer-guide/utility-functions.md](../developer-guide/utility-functions.md))
- Complete reference for all utility modules
- 500+ lines covering helpers, order items, forms, dates, data processing
- Usage examples and best practices
- Race condition and memory management documentation

### 2. **Testing Guide** ([developer-guide/testing.md](../developer-guide/testing.md))
- Comprehensive testing manual with pytest
- All fixtures documented (app, client, auth_user, mock_s3_client)
- Mocking patterns (S3, database, Flask-Login)
- Test writing examples and best practices
- Coverage expectations and CI integration

### 3. **File Upload System** ([developer-guide/file-uploads.md](../developer-guide/file-uploads.md))
- In-depth file upload architecture documentation
- Deferred upload pattern (prevents orphaned S3 files)
- Complete workflow diagrams
- S3 integration, thumbnail generation
- Memory management and cleanup
- Production-ready examples

## Material Theme Features

### Admonitions

```markdown
!!! note
    This is a note admonition.

!!! warning
    This is a warning admonition.

!!! tip
    This is a tip admonition.
```

### Code Blocks

````markdown
```python
def hello_world():
    print("Hello, World!")
```
````

### Tables

```markdown
| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
```

### Tabs

```markdown
=== "Tab 1"
    Content for tab 1

=== "Tab 2"
    Content for tab 2
```

### Mermaid Diagrams

````markdown
```mermaid
graph LR
    A[Start] --> B[Process]
    B --> C[End]
```
````

## Troubleshooting

### Build Warnings

```bash
# Check for broken links and issues
mkdocs build --strict
```

Common warnings:
- **Missing files**: Referenced in nav but don't exist
- **Broken links**: Links to non-existent docs
- **Excluded files**: Listed in `exclude_docs` won't be processed

### Port Already in Use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
mkdocs serve -a 127.0.0.1:8001
```

### Theme Not Loading

```bash
# Reinstall mkdocs-material
pip install --upgrade mkdocs-material
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/docs.yml`:

```yaml
name: Deploy Docs

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.x

      - name: Install dependencies
        run: |
          pip install mkdocs mkdocs-material

      - name: Deploy docs
        run: mkdocs gh-deploy --force
```

## Best Practices

### Documentation Writing

1. **Use descriptive headings** - Clear hierarchy with H1, H2, H3
2. **Include code examples** - Show, don't just tell
3. **Add navigation links** - Link to related pages
4. **Use admonitions** - Highlight important information
5. **Keep it updated** - Update docs when code changes

### Organization

1. **Group related topics** - Use directory structure
2. **Use index pages** - Landing pages for each section
3. **Logical navigation** - Order makes sense to users
4. **Search-friendly** - Use good keywords and headings

### Maintenance

1. **Test builds locally** - Before deploying
2. **Fix broken links** - Run `mkdocs build --strict`
3. **Update regularly** - Keep docs in sync with code
4. **Review PRs** - Require doc updates for features

## Useful Commands

```bash
# Serve docs locally
mkdocs serve

# Build docs
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy

# Deploy with message
mkdocs gh-deploy -m "Update docs"

# Build with strict mode (fail on warnings)
mkdocs build --strict

# Clean build directory
rm -rf site/

# Check MkDocs version
mkdocs --version

# Validate configuration
mkdocs build --strict --verbose
```

## Resources

- **MkDocs:** https://www.mkdocs.org/
- **Material for MkDocs:** https://squidfunk.github.io/mkdocs-material/
- **Markdown Guide:** https://www.markdownguide.org/
- **Project Repo:** https://github.com/andrewimpellitteri/awning_wo

## See Also

- [Developer Guide Index](../developer-guide/index.md) - All developer documentation
- [Utility Functions](../developer-guide/utility-functions.md) - Utility functions reference
- [Testing Guide](../developer-guide/testing.md) - Testing documentation
- [File Uploads](../developer-guide/file-uploads.md) - File upload system
