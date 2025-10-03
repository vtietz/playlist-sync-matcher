# Development & Releases

## Local Setup
```
run.bat sync   # Windows
./run.sh sync  # *nix
```
Creates `.venv`, installs deps, runs command.

## Tests
```
run.bat test -q
```
Run individual:
```
run.bat test tests\test_hashing.py -q
```

## Building Executables
```
pip install pyinstaller
pyinstaller spx.spec
```
Outputs: `dist/`.

## Versioning & Release
1. (If adding a formal version constant later, update it in a dedicated version module; current prototype prints a static string.)
2. Commit & push.
3. Tag & push tag:
```
git tag vX.Y.Z
git push origin vX.Y.Z
```
4. GitHub Actions builds & attaches binaries.

## Coding Guidelines
- Keep CLI thin; move logic to services. All commands live in `spx/cli/` submodules; avoid reintroducing logic into the top-level shim.
- Return data from services (no prints) for testability.
- Provider additions: follow `docs/providers.md` and minimal interface.
- Maintain consistent defaults across `config.py` and docs.

## Adding Dependencies
- Update `requirements.txt`.
- Favor widely-used libs; justify additions.

## Style
- Type hints encouraged.
- Avoid premature abstraction; add only when a second implementation exists.
