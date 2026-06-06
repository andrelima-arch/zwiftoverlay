#!/usr/bin/env python3
"""Check source code for accidentally committed sensitive data.

Run this before committing to ensure no real API keys, passwords, or
credentials have been hardcoded into the codebase.

Usage:
    python scripts/check-sensitive-data.py

Exit codes:
    0 - No sensitive data detected
    1 - Potential sensitive data found
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Directories to scan
SCAN_DIRS = ["app", "tests"]

# File patterns to check
INCLUDE_PATTERNS = ["*.py"]

# Known safe placeholder values used in tests
SAFE_PLACEHOLDERS = {
    "api-key",
    "api_key",
    "apikey",
    "secret",
    "test-secret",
    "test-key",
    "testkey",
    "password",
    "test-password",
    "testpass",
    "athlete-id",
    "athlete_id",
    "athleteid",
}

# Patterns that look like real API keys / tokens
SENSITIVE_PATTERNS = [
    # Intervals.icu API keys: 32+ hex or alphanumeric
    (r'["\']([a-f0-9]{32,})["\']', "hex token (possible API key)"),
    # Generic high-entropy strings that look like keys
    (r'["\']([A-Za-z0-9_\-]{40,})["\']', "long alphanumeric string (possible token)"),
    # Explicit password assignments (not placeholders)
    (r'password\s*=\s*["\']([^"\']{8,})["\']', "password assignment"),
    # Private keys
    (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', "private key block"),
]

# Keys that should only contain safe values in test files
TEST_ONLY_KEYS = [
    "intervals_api_key",
    "api_key",
    "password",
    "secret",
    "token",
]


def _is_placeholder(value: str) -> bool:
    """Check if a value is a known safe placeholder."""
    normalized = value.lower().strip().replace("_", "-").replace(" ", "-")
    return normalized in SAFE_PLACEHOLDERS or "test" in normalized or "fake" in normalized or "mock" in normalized


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Scan a single file for sensitive data. Returns list of (line_no, match, reason)."""
    issues: list[tuple[int, str, str]] = []
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for line_no, line in enumerate(lines, start=1):
        # Skip comments that mention 'placeholder', 'example', 'test'
        stripped = line.strip()
        if stripped.startswith("#") and any(w in stripped.lower() for w in ("placeholder", "example", "test", "fake", "mock")):
            continue

        for pattern, reason in SENSITIVE_PATTERNS:
            for match in re.finditer(pattern, line):
                groups = match.groups()
                if not groups:
                    issues.append((line_no, match.group(0), reason))
                    continue
                value = groups[0]
                if _is_placeholder(value):
                    continue
                # Skip if the line is clearly a comment or docstring
                if stripped.startswith(("\"\"\"", "'''", "#", '"', "'")):
                    # But still catch actual assignments inside docstrings? No, skip docstrings
                    if stripped.startswith(("\"\"\"", "'''")):
                        continue
                issues.append((line_no, value[:40], reason))

    return issues


def _check_test_files_only_use_placeholders(root: Path) -> list[tuple[Path, int, str]]:
    """Ensure test files only use placeholder credentials."""
    issues: list[tuple[Path, int, str]] = []
    test_dirs = [root / "tests"]

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        for path in test_dir.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), start=1):
                for key in TEST_ONLY_KEYS:
                    if key not in line.lower():
                        continue
                    # Extract the value after the key
                    match = re.search(rf'{key}[^\n]*[=:]\s*["\']([^"\']+)["\']', line, re.IGNORECASE)
                    if not match:
                        continue
                    value = match.group(1)
                    if not _is_placeholder(value) and len(value) > 4:
                        issues.append((path, line_no, f"Test file uses non-placeholder {key}: '{value[:30]}...'"))

    return issues


def main() -> int:
    root = Path(__file__).parent.parent / "cycling_overlay"
    if not root.exists():
        root = Path(__file__).parent.parent

    all_issues: list[tuple[Path, int, str, str]] = []

    # Scan source files
    for scan_dir_name in SCAN_DIRS:
        scan_dir = root / scan_dir_name
        if not scan_dir.exists():
            continue
        for pattern in INCLUDE_PATTERNS:
            for path in scan_dir.rglob(pattern):
                issues = _scan_file(path)
                for line_no, match, reason in issues:
                    all_issues.append((path.relative_to(root.parent if "cycling_overlay" in str(root) else root), line_no, match, reason))

    # Check test files use only placeholders
    test_issues = _check_test_files_only_use_placeholders(root)
    for path, line_no, reason in test_issues:
        all_issues.append((path.relative_to(root.parent if "cycling_overlay" in str(root) else root), line_no, "", reason))

    if not all_issues:
        print("✅ No sensitive data detected in source code.")
        return 0

    print(f"⚠️  Found {len(all_issues)} potential issue(s) with sensitive data:\n")
    for path, line_no, match, reason in all_issues:
        match_str = f" (match: '{match}')" if match else ""
        print(f"  {path}:{line_no} — {reason}{match_str}")

    print("\nIf these are intentional (e.g., test fixtures), add the value to SAFE_PLACEHOLDERS")
    print("in scripts/check-sensitive-data.py or mark the line with a # placeholder comment.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
