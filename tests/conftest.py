import os
import sys

# Modules use `try: from .x / except ImportError: from x` - put the repo root on
# sys.path so the flat imports resolve when run under pytest.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
