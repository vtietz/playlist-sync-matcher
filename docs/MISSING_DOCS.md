# Missing Documentation - To Consider Creating

This file lists documentation that was referenced but doesn't exist yet. Consider creating these if they would add value to the project.

## Removed/Outdated References

These were removed during link cleanup (2025-01-27):

- ❌ `docs/ai-assessment.md` - Deleted (outdated AI analysis with 106 broken links to old file structure)
- ❌ `psm/gui/docs/DEVELOPMENT.MD` - Deleted (outdated GUI dev doc with 32 broken line-specific links)
- ❌ `separate-executables-summary.md` - Never existed, reference removed
- ❌ `docs/gui-performance.md` - Referenced multiple times but never created
- ❌ `docs/manual-match-feature.md` - Referenced in v0.1.1 release notes but never created

## Potentially Useful Documentation to Create

### High Priority

1. **`docs/gui-performance.md`** - GUI Performance Optimization Guide
   - Was referenced in multiple places (README, development.md, gui/README.md)
   - Should document:
     - Fast-path filter optimization (90% CPU reduction)
     - Direct data access patterns (avoiding Qt overhead)
     - Chunked async loading for 60fps UI
     - Reusable patterns for Qt table applications
     - Handling large datasets (50k+ tracks)

### Medium Priority

2. **`docs/manual-match-feature.md`** - Manual Match Feature Documentation  
   - Was referenced in v0.1.1 release notes
   - Should document:
     - How to use manual match in CLI and GUI
     - When to use manual matches (wrong file location, metadata mismatch, etc.)
     - How matches are stored in the database
     - How to remove manual matches

3. **Updated Architecture Doc** - Refresh `docs/architecture.md`
   - Current arch doc may be outdated
   - Should reflect:
     - Service layer pattern (psm/services/)
     - GUI architecture (MVC pattern)
     - Database schema and models
     - Provider registry system

### Low Priority

4. **`docs/testing.md`** - Testing Guide
   - How to run tests
   - How to write new tests
   - Test organization (unit vs integration)
   - Mocking Spotify API for tests

5. **`docs/troubleshooting.md`** - Enhanced Troubleshooting
   - Common issues and solutions
   - OAuth/authentication problems
   - Build failures on different platforms
   - Database corruption recovery

## Notes

- Don't create docs just for completeness - only create if they add real value
- Keep documentation DRY - don't duplicate what's already in code comments or other docs
- Consider if information belongs in README vs separate doc
- Update this file when creating any of these docs

## Last Updated

2025-01-27 - Initial list created during link cleanup
