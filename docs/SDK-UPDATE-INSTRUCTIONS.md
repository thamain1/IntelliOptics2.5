# IntelliOptics SDK Update Instructions

**Purpose**: Add top-level `model` package to SDK for backwards compatibility
**Repository**: https://github.com/thamain1/IntelliOptics-SDK
**Target Version**: 0.2.1

---

## Instructions for Codex/AI Assistant

Execute the following steps to update the IntelliOptics SDK:

---

## STEP 1: Create New Directory

Create a new directory called `model/` at the root of the repository (same level as `intellioptics/`):

```
IntelliOptics-SDK/
├── intellioptics/          # Already exists
├── model/                  # ⭐ CREATE THIS NEW DIRECTORY
├── pyproject.toml          # Already exists
└── README.md              # Already exists
```

---

## STEP 2: Create `model/__init__.py`

Create a new file at `model/__init__.py` with the following exact content:

**File: `model/__init__.py`**

```python
"""
IntelliOptics Model Types - Top-Level Package

This package provides convenient top-level access to all IntelliOptics model types.
Re-exports all model types from intellioptics.models for backwards compatibility.

Usage:
    from model import Detector, ImageQuery, ModeEnum

This is equivalent to:
    from intellioptics.models import Detector, ImageQuery, ModeEnum
"""

from intellioptics.models import (
    # Core Types
    Detector,
    ImageQuery,

    # Enums
    ImageQueryTypeEnum,
    ModeEnum,
    ResultTypeEnum,

    # Result Types
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,

    # Configuration Types
    CountModeConfiguration,
    MultiClassModeConfiguration,

    # Supporting Types
    ROI,
    Label,
    Source,
)

__all__ = [
    # Core
    "Detector",
    "ImageQuery",

    # Enums
    "ImageQueryTypeEnum",
    "ModeEnum",
    "ResultTypeEnum",

    # Results
    "BinaryClassificationResult",
    "MultiClassificationResult",
    "CountingResult",

    # Configuration
    "CountModeConfiguration",
    "MultiClassModeConfiguration",

    # Supporting Types
    "ROI",
    "Label",
    "Source",
]
```

---

## STEP 3: Update `pyproject.toml`

Modify the `pyproject.toml` file to include the new `model` package and increment the version.

### 3a. Update Version Number

**Find this line:**
```toml
version = "0.2.0"
```

**Change to:**
```toml
version = "0.2.1"
```

### 3b. Update Packages List

**Find this section:**
```toml
[tool.poetry.packages]
packages = [
    { include = "intellioptics" },
]
```

**Change to:**
```toml
[tool.poetry.packages]
packages = [
    { include = "intellioptics" },
    { include = "model" },
]
```

**ALTERNATIVE**: If `pyproject.toml` doesn't have a `[tool.poetry.packages]` section, add it:

```toml
[tool.poetry.packages]
packages = [
    { include = "intellioptics" },
    { include = "model" },
]
```

---

## STEP 4: Verify File Structure

After completing steps 1-3, verify the repository structure looks like this:

```
IntelliOptics-SDK/
├── .git/
├── .gitignore
├── intellioptics/
│   ├── __init__.py
│   ├── client.py
│   ├── models.py (or models/ directory)
│   └── ... (other SDK files)
├── model/                      # ✅ NEW
│   └── __init__.py            # ✅ NEW
├── pyproject.toml             # ✅ MODIFIED (version + packages)
├── README.md
└── LICENSE
```

---

## STEP 5: Local Testing (Before Publishing)

Run these commands locally to verify the changes work:

### 5a. Install SDK Locally in Editable Mode

```bash
cd IntelliOptics-SDK
pip install -e .
```

### 5b. Test Imports

```bash
python -c "
# Test 1: Original import style (what edge-api expects)
from model import Detector, ImageQuery, ModeEnum, ROI
print('✅ Test 1 PASSED: from model import works')
print('  Detector:', Detector)
print('  ImageQuery:', ImageQuery)

# Test 2: New import style (also should work)
from intellioptics.models import Detector as D2, ImageQuery as IQ2
print('✅ Test 2 PASSED: from intellioptics.models import works')
print('  Detector:', D2)
print('  ImageQuery:', IQ2)

# Test 3: Verify they're the same classes
assert Detector is D2, 'ERROR: Detector classes do not match!'
assert ImageQuery is IQ2, 'ERROR: ImageQuery classes do not match!'
print('✅ Test 3 PASSED: Both import paths reference same classes')

print('\n🎉 ALL TESTS PASSED - SDK is ready!')
"
```

**Expected Output:**
```
✅ Test 1 PASSED: from model import works
  Detector: <class 'intellioptics.models.Detector'>
  ImageQuery: <class 'intellioptics.models.ImageQuery'>
✅ Test 2 PASSED: from intellioptics.models import works
  Detector: <class 'intellioptics.models.Detector'>
  ImageQuery: <class 'intellioptics.models.ImageQuery'>
✅ Test 3 PASSED: Both import paths reference same classes

🎉 ALL TESTS PASSED - SDK is ready!
```

---

## STEP 6: Commit and Push Changes

If all tests pass, commit and push to GitHub:

```bash
git add model/
git add pyproject.toml
git commit -m "Add top-level model package for backwards compatibility (v0.2.1)

- Created model/__init__.py to re-export intellioptics.models types
- Updated pyproject.toml to include model package
- Bumped version to 0.2.1
- Supports both import styles:
  * from model import Detector (backwards compatible)
  * from intellioptics.models import Detector (new style)
"
git push origin main
```

---

## STEP 7: Verify GitHub Installation

After pushing, test that the SDK installs correctly from GitHub:

```bash
# Uninstall local version
pip uninstall intellioptics -y

# Install from GitHub
pip install git+https://github.com/thamain1/IntelliOptics-SDK@main

# Test imports again
python -c "
from model import Detector, ImageQuery
from intellioptics.models import ModeEnum, ROI
print('✅ GitHub installation successful!')
print('Detector:', Detector)
print('ImageQuery:', ImageQuery)
"
```

---

## Summary of Changes

### Files Created:
- ✅ `model/__init__.py` (new top-level package)

### Files Modified:
- ✅ `pyproject.toml` (added `model` package, bumped version to 0.2.1)

### Files Unchanged:
- `intellioptics/` directory (no changes needed)
- `README.md` (optional: could document both import styles)
- All other existing files

---

## What This Achieves

After this update, users can import model types using **either** style:

**Style 1 (Top-level):**
```python
from model import Detector, ImageQuery, ModeEnum, ROI
```

**Style 2 (Namespaced):**
```python
from intellioptics.models import Detector, ImageQuery, ModeEnum, ROI
```

Both styles work and reference the exact same classes. This provides backwards compatibility for existing edge-api code while supporting the more explicit namespaced imports.

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'intellioptics.models'"

**Solution**: The SDK's `intellioptics` package is missing the `models` module. Check that:
1. `intellioptics/models.py` exists OR
2. `intellioptics/models/__init__.py` exists

### Issue: "Cannot import name 'Detector' from 'model'"

**Solution**: The `model/__init__.py` file was not created correctly or the package wasn't included in `pyproject.toml`. Verify:
1. `model/__init__.py` exists and contains the import statements
2. `pyproject.toml` includes `{ include = "model" }` in the packages list

### Issue: "ImportError: cannot import name 'X' from 'intellioptics.models'"

**Solution**: The class `X` doesn't exist in `intellioptics.models`. Check what classes are actually available:

```python
import intellioptics.models
print(dir(intellioptics.models))
```

Adjust the `model/__init__.py` imports to only include classes that actually exist.

---

## Next Steps After Publishing

Once you've pushed version 0.2.1 to GitHub:

1. ✅ Notify the edge-api team that SDK is updated
2. ✅ Edge-api can now use original imports: `from model import Detector`
3. ✅ Test full integration with edge deployment
4. ✅ Update SDK documentation to show both import styles

---

## Contact

For questions or issues with this update:
- Repository: https://github.com/thamain1/IntelliOptics-SDK
- Issues: https://github.com/thamain1/IntelliOptics-SDK/issues
