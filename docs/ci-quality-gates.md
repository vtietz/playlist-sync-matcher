# CI Quality Gates

## Overview

The release workflow now includes a **CI quality gate** that ensures all tests and quality checks pass before building release executables. This prevents broken releases from being published.

## How It Works

### Workflow Structure

```
Tag pushed (v*) → CI Quality Gate → Build Executables → Create Release
                       ↓
                  ❌ If fails: Build stops
                  ✅ If passes: Build continues
```

### Quality Checks Performed

Before any release build starts, the following checks must pass:

1. **Tests** (Ubuntu, Windows, macOS × Python 3.11, 3.12)
   - All unit tests
   - All integration tests
   - All GUI tests

2. **Code Quality**
   - Link validation (all documentation links must be valid)
   - Code complexity analysis (Lizard)
   - Style checking (flake8)
   - Formatting (Black)

3. **Smoke Tests**
   - CLI `--version` works
   - All imports succeed

### Implementation

**`.github/workflows/release.yml`:**
```yaml
jobs:
  # Run CI checks before building
  ci-check:
    name: CI Quality Gate
    uses: ./.github/workflows/ci.yml
    
  build-cli:
    needs: ci-check  # Wait for CI to pass
    # ... build steps
    
  build-gui:
    needs: ci-check  # Wait for CI to pass
    # ... build steps
```

**`.github/workflows/ci.yml`:**
```yaml
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_call:  # Allow other workflows to call this
```

## Benefits

### 🛡️ Prevents Broken Releases
- No more releasing executables that fail tests
- Catches formatting issues before build
- Validates all platforms (Ubuntu, Windows, macOS)

### ⚡ Fast Failure
- If CI fails, build stops immediately
- No wasted time building broken code
- Clear error messages in workflow logs

### 📊 Visibility
- GitHub Actions UI shows CI gate clearly
- Easy to see what failed (tests, formatting, etc.)
- Can re-run failed jobs individually

## What Happens When CI Fails

### During Release Tag Push

1. Tag is pushed: `git push origin v0.1.3`
2. Release workflow starts
3. CI quality gate runs
4. **If CI fails:**
   - ❌ Build jobs don't start
   - ❌ No release is created
   - ❌ No executables are built
   - 📧 You get a notification (if configured)

5. **To fix:**
   - Check CI logs to see what failed
   - Fix the issue locally
   - Delete the tag: `git tag -d v0.1.3 && git push origin :v0.1.3`
   - Commit the fix
   - Tag again: `git tag -a v0.1.3 -m "..." && git push origin v0.1.3`

### Example: Formatting Failure

```
CI Quality Gate → ❌ Black formatting check failed
                  → Build stops
                  → No release created

Fix:
  1. run.bat cleanup changed
  2. git commit -m "style: Apply Black formatting"
  3. git push
  4. git tag -f v0.1.3 -m "Release v0.1.3"
  5. git push --force origin v0.1.3
```

## Best Practices

### Before Creating a Release Tag

✅ **Always run locally first:**
```bash
# Run all checks locally
run.bat test              # All tests
run.bat analyze changed   # Code quality + link checking
run.bat cleanup changed   # Format code

# If all pass, create release tag
git tag -a v0.1.3 -m "Release v0.1.3"
git push origin v0.1.3
```

✅ **Use RC tags for testing:**
```bash
# Test build with pre-release tag
git tag -a v0.1.3-rc.1 -m "Release Candidate 1"
git push origin v0.1.3-rc.1

# If RC succeeds, create final release
git tag -a v0.1.3 -m "Release v0.1.3"
git push origin v0.1.3
```

✅ **Watch CI on main branch:**
- Ensure CI is green on main before tagging
- Don't tag from commits with failing CI

### If Release Build Fails

1. **Check which gate failed:**
   - Go to Actions tab
   - Click on failed workflow
   - Check CI Quality Gate job logs

2. **Common failures:**
   - **Tests failed** → Fix tests, commit, re-tag
   - **Formatting** → Run `run.bat cleanup all`, commit, re-tag
   - **Link check** → Fix broken links, commit, re-tag
   - **Platform-specific** → Check macOS/Windows-specific issues

3. **Delete and re-tag:**
   ```bash
   # Delete local tag
   git tag -d v0.1.3
   
   # Delete remote tag
   git push origin :v0.1.3
   
   # Make fixes, commit, push
   git add -A
   git commit -m "fix: ..."
   git push
   
   # Create tag again
   git tag -a v0.1.3 -m "Release v0.1.3"
   git push origin v0.1.3
   ```

## Monitoring

### GitHub Actions

- **URL**: https://github.com/vtietz/playlist-sync-matcher/actions
- **Filter by event**: Click "release" to see only release workflows
- **Check status**: 
  - 🟢 Green = CI passed, build succeeded
  - 🔴 Red = CI or build failed
  - 🟡 Yellow = In progress

### Notifications

Configure GitHub notifications for workflow failures:
1. Go to: https://github.com/settings/notifications
2. Enable: "Actions - Workflow run failures"
3. Choose: Email or GitHub notifications

## Testing the Quality Gate

### Test CI Integration

1. **Create a test branch with broken code:**
   ```bash
   git checkout -b test-ci-gate
   # Intentionally break a test
   git commit -am "test: Intentionally break test"
   git push -u origin test-ci-gate
   ```

2. **Check CI fails:**
   - PR CI should fail
   - Merge should be blocked (if branch protection enabled)

3. **Clean up:**
   ```bash
   git checkout main
   git branch -D test-ci-gate
   git push origin --delete test-ci-gate
   ```

### Test Release Gate

1. **Create RC with broken code:**
   ```bash
   # Intentionally break something
   git commit -am "test: Break formatting"
   git tag -a v0.1.3-rc.99 -m "Test CI gate"
   git push && git push origin v0.1.3-rc.99
   ```

2. **Verify build stops:**
   - Release workflow starts
   - CI gate fails
   - Build jobs never start
   - No release created

3. **Clean up:**
   ```bash
   git reset --hard HEAD~1
   git push --force
   git tag -d v0.1.3-rc.99
   git push origin :v0.1.3-rc.99
   ```

## Additional Safeguards

### Branch Protection (Recommended)

Add these rules for the `main` branch:

1. **Require status checks:**
   - ✅ Require "test" to pass
   - ✅ Require branches to be up to date

2. **Require pull request reviews:**
   - At least 1 approval for major changes

3. **Settings location:**
   - https://github.com/vtietz/playlist-sync-matcher/settings/branches

### Pre-commit Hooks (Optional)

Install local hooks to catch issues before commit:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
# Add Black, flake8, etc.

# Install hooks
pre-commit install
```

## Troubleshooting

### "CI gate failed but I can't see why"

1. Go to Actions tab
2. Click failed workflow
3. Click "CI Quality Gate" job
4. Expand failed steps
5. Read error messages

### "I need to bypass CI for emergency hotfix"

**Don't do this!** Instead:

1. Fix the issue properly
2. Ensure CI passes
3. Release normally

Emergency hotfixes that skip CI often introduce more problems than they solve.

### "CI passes locally but fails in GitHub Actions"

Common causes:
- **Platform differences** - Test on all platforms (Ubuntu, Windows, macOS)
- **Missing dependencies** - Check requirements.txt/requirements-dev.txt
- **File paths** - Use Path() for cross-platform paths
- **Line endings** - Configure git autocrlf correctly

## Summary

✅ **CI Quality Gate ensures:**
- All tests pass before release
- Code is properly formatted
- Documentation links are valid
- All platforms work (Ubuntu, Windows, macOS)

✅ **Result:**
- Higher quality releases
- Fewer "oops" moments
- More confidence in releases
- Better user experience
