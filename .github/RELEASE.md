# netpicker-cli Release Runbook

Bi-weekly release process. Target cadence: every two weeks on a Monday.

---

## Pre-flight checklist

Before cutting a release, confirm:

- [ ] All intended PRs / commits are merged to `main`
- [ ] `CHANGELOG.md` is updated with release notes under the new version heading
- [ ] Tests pass locally (see step 2 below)

---

## Step-by-step release

### 1. Determine the next version

We follow [SemVer](https://semver.org/):

| Change type | Bump |
|---|---|
| Bug fixes, small improvements | `patch` (0.2.0 → 0.2.1) |
| New features, backward-compatible | `minor` (0.2.0 → 0.3.0) |
| Breaking changes | `major` (0.2.0 → 1.0.0) |

Current version: check `pyproject.toml` → `version = "..."` or run:

```bash
grep '^version' pyproject.toml
```

### 2. Run the test suite

```bash
source venv/bin/activate
pytest tests/unit/ -q
```

Fix any failures before proceeding.

### 3. Update `pyproject.toml`

Edit the `version` field:

```toml
version = "0.2.1"   # ← new version
```

### 4. Update `CHANGELOG.md`

Add a new section at the top (below the `# Changelog` heading):

```markdown
## 0.2.1 — YYYY-MM-DD

### Fixed / Changed / Added
- ...
```

### 5. Commit and tag

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v0.2.1"
git tag v0.2.1
git push origin main --tags
```

---

## Stage 1 — Publish to TestPyPI (validate first)

```bash
source venv/bin/activate

# Clean previous build artefacts (no sudo needed)
rm -rf dist/ build/ src/netpicker_cli.egg-info/

# Build source distribution + wheel
python3 -m build

# Upload to TestPyPI
twine upload --repository testpypi dist/*
```

> **Credentials**: `twine` reads `~/.pypirc`. If not set up yet, see [Appendix A](#appendix-a--pypirc-setup).

### Validate on TestPyPI inside Docker

```bash
docker run -it --rm python:3.11-slim bash
```

Inside the container:

```bash
# Replace 0.2.1 with the version you just uploaded
pip install --no-cache-dir \
    -i https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple \
    netpicker-cli==0.2.1

# Smoke test
netpicker --version
netpicker --help
```

If anything looks wrong, fix it, bump the version again (e.g. 0.2.1 → 0.2.2), and repeat from step 3.

---

## Stage 2 — Publish to PyPI (production)

Only proceed after TestPyPI validation passes.

```bash
cd /home/sanps/gits/netpicker-cli
source venv/bin/activate

# The dist/ artefacts from Stage 1 are reused — no need to rebuild.
# If you rebuilt for any reason, clean first:
# rm -rf dist/ build/ src/netpicker_cli.egg-info/ && python3 -m build

twine upload dist/*
```

### Validate from PyPI

```bash
docker run -it --rm python:3.11-slim bash
```

Inside the container:

```bash
pip install --no-cache-dir netpicker-cli==0.2.1
netpicker --version
netpicker --help
```

---

## Post-release

- [ ] Verify the release appears on https://pypi.org/project/netpicker-cli/
- [ ] Create a GitHub Release at https://github.com/netpicker/netpicker-cli/releases/new
  - Tag: `v0.2.1`
  - Title: `v0.2.1 — <short description>`
  - Body: paste the relevant `CHANGELOG.md` section
- [ ] Announce in Slack / email / wherever your users are

---

## Quick reference — full command sequence (copy-paste)

```bash
# ---- set this before starting ----
VERSION="0.2.1"
source venv/bin/activate
# -----------------------------------

# Update version manually in pyproject.toml first, then:
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v${VERSION}"
git tag "v${VERSION}"
git push origin main --tags

rm -rf dist/ build/ src/netpicker_cli.egg-info/
python3 -m build

# Stage 1: TestPyPI
twine upload --repository testpypi dist/*

# (validate in Docker, then:)

# Stage 2: PyPI
twine upload dist/*
```

---

## Appendix A — `~/.pypirc` setup

Create `~/.pypirc` with the following (replace tokens with API tokens from pypi.org / test.pypi.org):

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-<your-pypi-api-token>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-<your-testpypi-api-token>
```

Set permissions so only you can read it:

```bash
chmod 600 ~/.pypirc
```

---

## Appendix B — Bi-weekly calendar suggestion

| Release | Target date |
|---|---|
| v0.2.1 | 2026-03-16 |
| v0.2.2 | 2026-03-30 |
| v0.2.3 | 2026-04-13 |
| v0.3.0 | 2026-04-27 |

Adjust minor/major bumps as features warrant.

---

## What's different from your original steps

| Original | Corrected / improved |
|---|---|
| `sudo rm -rf dist/ ...` | No `sudo` needed — you own the directory |
| `rm -rf *.egg-info` | Should be `src/netpicker_cli.egg-info/` (glob won't match inside `src/`) |
| No git tag | Tag every release so you can `git checkout v0.2.1` any time |
| No test run | Run `pytest tests/unit/` before building |
| Rebuild before PyPI upload | Reuse the same artefacts you validated on TestPyPI — identical bits |
| No `CHANGELOG.md` update step | Update changelog before committing |
