# Documentation Reorganization Guide

This guide explains the new documentation structure and how to complete the reorganization.

## What Changed?

### Before
```
docs/
├── ALEMBIC_GUIDE.md
├── CACHING_GUIDE.md
├── CONCURRENCY_AUDIT.md
├── DENORMALIZATION_ANALYSIS.md
├── DEPLOYMENT_CHECKLIST.md
├── IMPROVEMENTS.md
├── PERFORMANCE_ANALYSIS.md
├── REFACTORING_PLAN.md
├── STORAGE_FIELDS_GUIDE.md
├── WASM_THUMBNAIL_OPTIMIZATION.md
└── index.md
```

### After
```
docs/
├── index.md                          # Main documentation homepage
├── user-guide/                       # For end users
│   ├── index.md
│   ├── getting-started.md
│   ├── work-orders.md
│   ├── repair-orders.md
│   ├── customers.md
│   ├── sources.md
│   ├── inventory.md
│   ├── queue.md
│   ├── analytics.md
│   ├── pdf-reports.md
│   └── keyboard-shortcuts.md
├── developer-guide/                  # For developers
│   ├── index.md
│   ├── setup.md
│   ├── project-structure.md
│   ├── database-schema.md
│   ├── api-reference.md
│   ├── testing.md
│   └── contributing.md
├── database/                         # Database & migrations
│   ├── ALEMBIC_GUIDE.md             ✅ Existing
│   ├── STORAGE_FIELDS_GUIDE.md      ✅ Existing
│   └── schema-changes.md
├── deployment/                       # Deployment guides
│   ├── aws-eb.md
│   ├── DEPLOYMENT_CHECKLIST.md      ✅ Existing
│   ├── environment-variables.md
│   ├── monitoring.md
│   └── rollback.md
├── architecture/                     # Technical architecture
│   ├── overview.md
│   ├── ml-system.md
│   ├── CACHING_GUIDE.md             ✅ Existing
│   ├── PERFORMANCE_ANALYSIS.md      ✅ Existing
│   └── CONCURRENCY_AUDIT.md         ✅ Existing
├── planning/                         # Future improvements
│   ├── IMPROVEMENTS.md              ✅ Existing
│   ├── REFACTORING_PLAN.md          ✅ Existing
│   ├── DENORMALIZATION_ANALYSIS.md  ✅ Existing
│   └── WASM_THUMBNAIL_OPTIMIZATION.md ✅ Existing
└── reference/                        # Quick reference
    ├── faq.md
    ├── troubleshooting.md
    └── glossary.md
```

## Step-by-Step Reorganization

### Step 1: Run the Reorganization Script

This moves existing docs to their new locations:

```bash
chmod +x reorganize_docs.sh
./reorganize_docs.sh
```

This will:
- Create the new directory structure
- Move existing .md files to appropriate locations
- Keep your existing documentation intact

### Step 2: Create Placeholder Files

This creates starter content for missing documentation:

```bash
chmod +x create_doc_placeholders.sh
./create_doc_placeholders.sh
```

This creates:
- User guide pages with basic structure
- Developer guide foundations
- Reference materials (FAQ, troubleshooting, glossary)

### Step 3: Preview the Documentation

Install MkDocs and dependencies:

```bash
pip install mkdocs-material
pip install mkdocs-git-revision-date-localized-plugin
```

Serve the documentation locally:

```bash
mkdocs serve
```

Visit `http://127.0.0.1:8000` to preview.

### Step 4: Fill in the Gaps

You now have a skeleton. Fill in content over time:

#### Priority 1: Essential User Docs
- [ ] `user-guide/work-orders.md` - Expand with screenshots
- [ ] `user-guide/repair-orders.md` - Add workflow diagrams
- [ ] `user-guide/queue.md` - Document queue workflows

#### Priority 2: Developer Onboarding
- [ ] `developer-guide/setup.md` - Verify setup steps
- [ ] `developer-guide/database-schema.md` - Add ER diagrams
- [ ] `developer-guide/testing.md` - Document test patterns

#### Priority 3: Operations
- [ ] `deployment/aws-eb.md` - Complete deployment guide
- [ ] `deployment/monitoring.md` - Add monitoring setup
- [ ] `deployment/environment-variables.md` - Document all env vars

#### Priority 4: Architecture
- [ ] `architecture/overview.md` - System architecture diagram
- [ ] `architecture/ml-system.md` - ML pipeline documentation

## Documentation Philosophy

### For Users
- **Task-oriented** - Focus on "how to do X"
- **Screenshots** - Show, don't just tell
- **Examples** - Real-world scenarios
- **Simple language** - Avoid jargon

### For Developers
- **Code examples** - Show actual code
- **Architecture diagrams** - Visualize structure
- **Technical depth** - Don't oversimplify
- **Links to code** - Reference actual files

## Writing Tips

### Good User Documentation
```markdown
## Creating a Work Order

1. Click "New Work Order" in the top menu
2. Select a customer from the dropdown
3. Fill in the date and source
4. Click "Save"

![Screenshot of work order form](../images/work-order-form.png)

!!! tip
    Use Ctrl+N to quickly create a new work order
```

### Good Developer Documentation
```markdown
## Work Order Model

The WorkOrder model represents a cleaning job.

**File:** [models/work_order.py](../../models/work_order.py)

```python
class WorkOrder(db.Model):
    __tablename__ = "tblcustworkorderdetail"
    work_order_no = db.Column("workorderno", db.Integer, primary_key=True)
    # ...
```

**Relationships:**
- Belongs to: Customer (via custid)
- Has many: WorkOrderFiles
```

## MkDocs Features

### Admonitions (Callouts)

```markdown
!!! note
    This is a note

!!! warning
    This is a warning

!!! tip
    This is a helpful tip

!!! danger
    This is critical information
```

### Tabs

```markdown
=== "Python"
    ```python
    def hello():
        print("Hello!")
    ```

=== "JavaScript"
    ```javascript
    function hello() {
        console.log("Hello!");
    }
    ```
```

### Code Blocks with Line Numbers

```markdown
```python linenums="1"
def example():
    return "Hello"
```
```

## Publishing the Docs

### Option 1: GitHub Pages (Recommended)

```bash
# Build the docs
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

This creates a `gh-pages` branch with the built site.

Configure GitHub Pages:
1. Go to repository Settings
2. Pages section
3. Source: Deploy from branch
4. Branch: gh-pages / root
5. Save

Your docs will be at: `https://andrewimpellitteri.github.io/awning_wo/`

### Option 2: Netlify/Vercel

Both support MkDocs. Add a build command:

```bash
mkdocs build
```

And publish directory: `site/`

## Maintenance

### Adding New Documentation

1. Create the .md file in the appropriate directory
2. Add it to `mkdocs.yml` in the `nav:` section
3. Test with `mkdocs serve`
4. Commit and push

### Updating Existing Documentation

1. Edit the .md file
2. Preview with `mkdocs serve`
3. Commit and push
4. Redeploy with `mkdocs gh-deploy` (if using GitHub Pages)

## Next Steps

1. ✅ Run `./reorganize_docs.sh`
2. ✅ Run `./create_doc_placeholders.sh`
3. ✅ Preview with `mkdocs serve`
4. 📝 Fill in user guide content
5. 📝 Add developer documentation
6. 🚀 Deploy to GitHub Pages

## Questions?

- **MkDocs Documentation:** https://www.mkdocs.org/
- **Material Theme:** https://squidfunk.github.io/mkdocs-material/
- **Markdown Guide:** https://www.markdownguide.org/

## File Locations Summary

| Type | Old Location | New Location |
|------|-------------|--------------|
| Database guides | `docs/*.md` | `docs/database/` |
| Deployment | `docs/*.md` | `docs/deployment/` |
| Architecture | `docs/*.md` | `docs/architecture/` |
| Planning | `docs/*.md` | `docs/planning/` |
| User guides | *(new)* | `docs/user-guide/` |
| Developer guides | *(new)* | `docs/developer-guide/` |
| Reference | *(new)* | `docs/reference/` |
