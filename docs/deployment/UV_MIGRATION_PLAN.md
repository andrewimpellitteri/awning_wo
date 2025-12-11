# uv Package Manager Migration Plan

## Overview

This document outlines the plan for migrating from `pip` to `uv` for Python package management across all environments: local development, GitHub Actions CI/CD, and AWS Elastic Beanstalk production deployment.

**uv** is an extremely fast Python package installer and resolver written in Rust, created by Astral (the team behind Ruff). It's 10-100x faster than pip and provides better dependency resolution.

**Status:** Planning phase - no changes implemented yet

## Benefits of Migration

1. **Speed**: 10-100x faster than pip for package installation
2. **Better dependency resolution**: More reliable conflict detection and resolution
3. **Reproducible builds**: Improved lock file support with `uv.lock`
4. **Drop-in replacement**: Compatible with `requirements.txt` files
5. **Unified tooling**: Can also manage Python versions (via `uv python`)
6. **CI/CD optimization**: Dramatically faster build times in GitHub Actions
7. **Disk space efficiency**: Shared package cache across virtual environments

## Current State

### Package Management
- **Tool**: pip
- **Requirements**: `requirements.txt` (production) + `requirements-dev.txt` (development)
- **Known issues**:
  - Recent dependency conflict: Flask-Caching 2.0.0 incompatible with Flask 2.3.3 (resolved)
  - No lock file for reproducible builds
  - Slow CI/CD builds (dependencies install takes ~2-3 minutes)

### Environment Setup
- Local: Manual venv + pip install
- CI/CD: GitHub Actions with pip
- Production: AWS EB with pip via `.ebextensions`

## Migration Strategy

### Phase 1: Local Development (Low Risk)

**Goal**: Enable developers to use uv locally while maintaining pip compatibility

#### Steps:
1. Install uv globally
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or
   brew install uv
   ```

2. Generate uv lock file
   ```bash
   uv pip compile requirements.txt requirements-dev.txt -o uv.lock
   ```

3. Create `.python-version` file
   ```bash
   echo "3.11" > .python-version
   ```

4. Update developer documentation
   - Add uv installation instructions to CLAUDE.md
   - Provide migration guide for existing developers
   - Document both pip and uv workflows during transition

5. Test local development workflow
   ```bash
   # Using uv
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   uv pip sync uv.lock

   # Traditional pip still works
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

#### Rollback Plan:
- No changes to production systems
- Developers can continue using pip
- Simply delete `uv.lock` and `.python-version` if issues arise

#### Success Criteria:
- [ ] uv lock file generated without conflicts
- [ ] All dependencies install successfully via uv
- [ ] Application runs correctly with uv-installed packages
- [ ] At least one developer successfully migrates to uv locally
- [ ] Development documentation updated

---

### Phase 2: GitHub Actions CI/CD (Medium Risk)

**Goal**: Speed up CI/CD pipeline by using uv for dependency installation

#### Current CI Configuration:
Location: `.github/workflows/python-ci.yml`

```yaml
- name: Install Python dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt -r requirements-dev.txt
```

#### Proposed Changes:

1. Add uv installation step
   ```yaml
   - name: Install uv
     run: curl -LsSf https://astral.sh/uv/install.sh | sh

   - name: Add uv to PATH
     run: echo "$HOME/.cargo/bin" >> $GITHUB_PATH
   ```

2. Replace pip installation with uv
   ```yaml
   - name: Install Python dependencies with uv
     run: |
       uv venv
       source .venv/bin/activate
       uv pip sync uv.lock
   ```

   Or, using uv directly without venv activation:
   ```yaml
   - name: Install Python dependencies with uv
     run: |
       uv venv
       uv pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Update cache strategy
   ```yaml
   - name: Cache uv packages
     uses: actions/cache@v3
     with:
       path: ~/.cache/uv
       key: ${{ runner.os }}-uv-${{ hashFiles('uv.lock') }}
       restore-keys: |
         ${{ runner.os }}-uv-
   ```

#### Testing Strategy:
1. Create a feature branch `feature/uv-ci-migration`
2. Update workflow to use uv
3. Open PR and verify all tests pass
4. Compare CI runtime before/after
5. Merge if successful

#### Rollback Plan:
```yaml
# Keep commented-out pip installation as backup
# - name: Install Python dependencies (pip - fallback)
#   run: |
#     python -m pip install --upgrade pip
#     pip install -r requirements.txt -r requirements-dev.txt
```

#### Expected Improvements:
- Dependency installation time: ~2-3 minutes → ~10-30 seconds
- Total CI time reduction: ~20-40%
- More reliable dependency resolution

#### Success Criteria:
- [ ] All CI tests pass with uv
- [ ] CI runtime reduced by at least 30%
- [ ] No dependency resolution errors
- [ ] Cache strategy working correctly
- [ ] Multiple successful CI runs on different PRs

---

### Phase 3: AWS Elastic Beanstalk Production (High Risk)

**Goal**: Deploy to production using uv for faster deployments and better dependency management

⚠️ **IMPORTANT**: This phase has the highest risk and requires careful testing and rollback planning.

#### Current EB Configuration:

**Platform**: Python 3.11 on Amazon Linux 2023

**Deployment process**:
1. EB runs `pip install -r requirements.txt`
2. Custom configuration in `.ebextensions/01_flask.config`

#### Proposed Changes:

##### Option A: Install uv in EB environment (Recommended)

Create `.ebextensions/00_install_uv.config`:
```yaml
commands:
  01_install_uv:
    command: |
      curl -LsSf https://astral.sh/uv/install.sh | sh
      export PATH="$HOME/.cargo/bin:$PATH"
    test: '[ ! -f $HOME/.cargo/bin/uv ]'

  02_add_uv_to_path:
    command: |
      echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> /etc/profile.d/uv.sh
```

Modify `.ebextensions/01_flask.config` to use uv:
```yaml
container_commands:
  01_install_dependencies:
    command: |
      source $HOME/.cargo/env
      uv pip install -r requirements.txt --system
    leader_only: false
```

##### Option B: Pre-bundle dependencies (Alternative)

Use uv locally to create a vendor directory:
```bash
uv pip install -r requirements.txt --target ./vendor
```

Update `app.py` to use vendored packages:
```python
import sys
sys.path.insert(0, './vendor')
```

Pros:
- No uv installation needed on EB
- Faster deployments (no pip/uv install step)

Cons:
- Larger deployment bundle
- Harder to maintain

##### Option C: Use EB Buildfile (Most EB-native)

Create `Buildfile` in project root:
```bash
#!/bin/bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
uv pip install -r requirements.txt --system
```

#### Testing Strategy:

1. **Test environment first**
   ```bash
   # Create test EB environment
   eb create awning-test --database.engine postgres --database.username postgres

   # Deploy with uv changes
   eb deploy awning-test

   # Monitor logs
   eb logs awning-test --stream

   # Verify application
   eb open awning-test
   ```

2. **Blue/Green Deployment**
   - Keep current production environment running
   - Deploy to new environment with uv
   - Swap CNAMEs only after verification
   - Can swap back immediately if issues

3. **Staged rollout**
   - Week 1: Deploy to test environment, monitor
   - Week 2: Deploy to staging (if exists), run full test suite
   - Week 3: Deploy to production during low-traffic window
   - Have database backups ready

#### Rollback Plan:

**Immediate rollback** (if deployment fails):
```bash
# Option 1: Redeploy previous version
eb deploy --version <previous-version-label>

# Option 2: Swap environment back (if using blue/green)
eb swap awning-prod awning-prod-old

# Option 3: Restore .ebextensions to use pip
git revert <commit-hash>
eb deploy
```

**Monitoring checklist** (first 24 hours):
- [ ] Application health: `eb health`
- [ ] Error logs: `eb logs --stream | grep ERROR`
- [ ] Database connections working
- [ ] File uploads to S3 working
- [ ] ML model training cron job working
- [ ] Response times acceptable
- [ ] No dependency import errors

#### Success Criteria:
- [ ] Successful deployment to test environment
- [ ] All functionality verified in test environment
- [ ] Deployment time reduced (measure before/after)
- [ ] Application health checks passing for 24 hours
- [ ] No increase in error rates
- [ ] All cron jobs running successfully
- [ ] Rollback procedure tested and documented

---

## Migration Timeline

### Conservative Approach (Recommended)

**Week 1-2: Planning & Local Development**
- Review this plan with team
- Install uv locally
- Generate and test lock file
- Update documentation

**Week 3-4: CI/CD Migration**
- Create feature branch with uv changes
- Test in PR workflows
- Measure performance improvements
- Merge if successful

**Week 5-6: EB Test Environment**
- Create test EB environment
- Deploy with uv configuration
- Run comprehensive tests
- Load testing and monitoring

**Week 7-8: Production Deployment**
- Schedule deployment during maintenance window
- Blue/Green deployment to production
- Monitor for 48 hours before considering complete
- Document any issues and resolutions

### Aggressive Approach (Higher Risk)

**Week 1: All phases in parallel**
- Deploy to local, CI, and EB test simultaneously
- Fast iteration and testing

**Week 2: Production deployment**
- Deploy to production if all tests pass

**Risk**: Less time to identify edge cases and environment-specific issues

## Potential Issues & Mitigation

### Issue 1: uv not available in EB environment
**Mitigation**: Install during EB deployment phase via `.ebextensions` or use pre-bundled dependencies

### Issue 2: Lock file conflicts with EB platform packages
**Mitigation**: Use `--system` flag to install into system Python, or create separate lock files for different environments

### Issue 3: Dependency resolution differences between pip and uv
**Mitigation**: Thoroughly test in non-production environments first. Keep `requirements.txt` as source of truth.

### Issue 4: Build size limits on EB
**Mitigation**: uv installations are smaller than pip due to better caching. Monitor deployment bundle size.

### Issue 5: CI cache invalidation
**Mitigation**: Use content-based cache keys with `hashFiles('uv.lock')`

### Issue 6: Team onboarding
**Mitigation**: Provide clear documentation, support both pip and uv during transition period

## File Changes Summary

### New Files to Create:
```
uv.lock                              # Generated lock file
.python-version                      # Python version specification
.ebextensions/00_install_uv.config   # EB uv installation (if Option A)
Buildfile                            # EB build script (if Option C)
docs/deployment/UV_MIGRATION_PLAN.md # This file
```

### Files to Modify:
```
.github/workflows/python-ci.yml      # CI/CD workflow
.ebextensions/01_flask.config        # EB configuration (potentially)
CLAUDE.md                            # Development setup instructions
README.md                            # Quick start guide (potentially)
```

### Files to Keep:
```
requirements.txt                     # Keep as source of truth
requirements-dev.txt                 # Keep for development dependencies
```

## Open Questions

1. **Python version management**: Should we use `uv python` to manage Python versions, or continue with system Python?

2. **Lock file strategy**: Single `uv.lock` or separate locks for production vs. development?

3. **EB platform**: Does Amazon Linux 2023 have any conflicts with uv installation?

4. **Database migrations**: Any impact on Alembic migrations during deployment?

5. **Existing cron jobs**: Will ML retraining cron job work with uv-installed packages?

6. **Team preference**: Does the team prefer the speed of uv or familiarity of pip?

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-11 | Created migration plan | Address recent dependency conflicts and slow CI |
| TBD | Phase 1 approved/rejected | - |
| TBD | Phase 2 approved/rejected | - |
| TBD | Phase 3 approach selected | - |

## Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [uv vs pip Benchmark](https://github.com/astral-sh/uv#benchmarks)
- [AWS EB Python Platform](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-apps.html)
- [GitHub Actions uv Setup](https://github.com/astral-sh/setup-uv)

## Next Steps

1. **Review this plan** with the development team
2. **Get approval** for Phase 1 (local development)
3. **Install uv locally** and test with current codebase
4. **Generate lock file** and verify no dependency conflicts
5. **Update CLAUDE.md** with uv setup instructions
6. **Proceed to Phase 2** only after Phase 1 success

---

**Author**: Claude Code
**Created**: 2025-12-11
**Last Updated**: 2025-12-11
**Status**: Draft - Awaiting Review