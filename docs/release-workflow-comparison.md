# Release Workflow Comparison

## Current vs Enhanced Workflows

### **Current: `release.yml`**

✅ **What it does well:**
- Simple, straightforward configuration
- Builds all 6 executables (CLI + GUI for Win/Linux/Mac)
- Creates GitHub releases on tag push
- Manual trigger option via workflow_dispatch
- Smoke tests verify builds work

⚠️ **Limitations:**
- No version validation (can release with wrong version.py)
- No pre-build testing (wastes time if tests would fail)
- No changelog automation
- Manual runs don't create releases (artifacts only)
- No draft release option

### **Enhanced: `release-enhanced.yml`** ⭐

✅ **All features from current, PLUS:**
- ✅ **Version validation** - Tag must match psm/version.py
- ✅ **Pre-build testing** - Full test suite runs first
- ✅ **Auto-generated changelog** - From commit history
- ✅ **Draft releases** - Manual runs create drafts for review
- ✅ **Pre-release detection** - Alpha/beta tags auto-marked
- ✅ **Better artifact retention** - 7-day cleanup
- ✅ **Conditional job execution** - Smarter dependency logic

## Side-by-Side Feature Matrix

| Feature | release.yml | release-enhanced.yml |
|---------|-------------|---------------------|
| **Triggers** |
| Tag push (`v*`) | ✅ | ✅ |
| Manual workflow dispatch | ✅ | ✅ |
| **Builds** |
| CLI executables (3 platforms) | ✅ | ✅ |
| GUI executables (3 platforms) | ✅ | ✅ |
| Smoke tests | ✅ | ✅ |
| **Quality Gates** |
| Version validation | ❌ | ✅ |
| Pre-build tests | ❌ | ✅ |
| **Release Features** |
| Auto-create release | ✅ (tags only) | ✅ |
| Manual run creates release | ❌ | ✅ (draft) |
| Auto-generated changelog | ❌ | ✅ |
| Draft release option | ❌ | ✅ |
| Pre-release detection | ❌ | ✅ |
| Custom release notes | ❌ | ✅ |
| **Build Time** |
| Average duration | ~15 min | ~20 min* |

*Additional 5 min for test suite, but fails faster on errors

## Recommended Migration Path

### Option 1: Replace Entirely (Recommended)
```bash
# Rename current to backup
mv .github/workflows/release.yml .github/workflows/release-old.yml.bak

# Use enhanced as primary
mv .github/workflows/release-enhanced.yml .github/workflows/release.yml

# Commit
git add .github/workflows/
git commit -m "Upgrade to enhanced release workflow"
```

### Option 2: Keep Both (Testing)
Keep both workflows temporarily to test enhanced version:
- `release.yml` - Production releases (tag-based)
- `release-enhanced.yml` - Test with manual runs

Once confident, remove `release.yml`.

### Option 3: Hybrid Approach
- Use `release.yml` for quick hotfix releases (skip tests)
- Use `release-enhanced.yml` for major releases (full validation)
- Rename workflows to reflect purpose:
  - `release-quick.yml`
  - `release-full.yml`

## When to Use Each Workflow

### Use **Current** (`release.yml`) if:
- You want the simplest possible workflow
- You manually test before tagging
- You don't need automated changelogs
- Build time is critical (skip test suite)

### Use **Enhanced** (`release-enhanced.yml`) if:
- You want automated quality gates
- You need version validation
- You want auto-generated changelogs
- You create draft releases for review
- You use alpha/beta pre-releases

## Migration Checklist

- [ ] Review enhanced workflow features
- [ ] Test enhanced workflow with manual run
- [ ] Verify version validation works (intentional mismatch test)
- [ ] Check changelog generation quality
- [ ] Decide: replace or keep both
- [ ] Update documentation to reference chosen workflow
- [ ] Delete old workflow file (if replacing)

## Conclusion

**Recommendation**: Migrate to `release-enhanced.yml` as your primary workflow.

**Why:**
- ✅ Prevents common mistakes (version mismatches)
- ✅ Saves time by failing fast (tests before builds)
- ✅ Better user experience (changelogs, release notes)
- ✅ More flexible (draft releases, pre-releases)
- ✅ Minimal downside (~5 min extra build time)

**Transition Plan:**
1. Test enhanced workflow with manual run (no tag)
2. Verify draft release creation works
3. Intentionally mismatch version.py to test validation
4. Once confident, replace `release.yml` with enhanced version
5. Update `docs/release-process.md` to reference new workflow
