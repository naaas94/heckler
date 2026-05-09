"""Test-only shims when optional native deps are missing (e.g. Kokoro on Python 3.14)."""

import sys
import types

try:
    import kokoro  # noqa: F401
except ImportError:
    _kokoro = types.ModuleType("kokoro")
    _kokoro.KPipeline = type("KPipeline", (), {})
    sys.modules["kokoro"] = _kokoro
