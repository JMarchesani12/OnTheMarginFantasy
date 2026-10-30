"""Legacy module alias; implementation lives in admission/repository.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.admission.repository', __package__)
