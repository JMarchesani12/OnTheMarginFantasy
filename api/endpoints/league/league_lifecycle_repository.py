"""Legacy module alias; implementation lives in lifecycle/repository.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.lifecycle.repository', __package__)
