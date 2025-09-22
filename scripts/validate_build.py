#!/usr/bin/env python3
"""
Build artifact validation script.
Validates wheel and source distribution files in the dist/ directory.
"""

import sys
import tarfile
import zipfile
from pathlib import Path


def main():
    """Validate build artifacts in dist/ directory."""
    print("Validating package contents and metadata...")

    dist_path = Path("dist")
    if not dist_path.exists():
        print("✗ No dist/ directory found")
        sys.exit(1)

    # Check for wheel file
    wheel_files = list(dist_path.glob("*.whl"))
    if wheel_files:
        wheel_file = wheel_files[0]
        print(f"✓ Wheel file: {wheel_file.name}")

        # Basic validation that wheel can be opened
        try:
            with zipfile.ZipFile(wheel_file, "r") as zf:
                files = zf.namelist()
                has_metadata = any("METADATA" in f for f in files)
                has_py_files = any(f.endswith(".py") for f in files)
                print(f"✓ Wheel contains {len(files)} files")
                print(f"✓ Has metadata: {has_metadata}")
                print(f"✓ Has Python files: {has_py_files}")
        except Exception as e:
            print(f"✗ Wheel validation failed: {e}")
            sys.exit(1)
    else:
        print("✗ No wheel file found")
        sys.exit(1)

    # Check for source distribution
    sdist_files = list(dist_path.glob("*.tar.gz"))
    if sdist_files:
        sdist_file = sdist_files[0]
        print(f"✓ Source distribution: {sdist_file.name}")

        # Basic validation that sdist can be opened
        try:
            with tarfile.open(sdist_file, "r:gz") as tf:
                files = tf.getnames()
                has_setup_files = any(
                    f.endswith(("pyproject.toml", "setup.py", "setup.cfg"))
                    for f in files
                )
                has_src = any("src/" in f for f in files)
                print(f"✓ Source dist contains {len(files)} files")
                print(f"✓ Has setup files: {has_setup_files}")
                print(f"✓ Has source code: {has_src}")
        except Exception as e:
            print(f"✗ Source distribution validation failed: {e}")
            sys.exit(1)
    else:
        print("✗ No source distribution found")
        sys.exit(1)

    print("✅ Package validation completed successfully")


if __name__ == "__main__":
    main()
