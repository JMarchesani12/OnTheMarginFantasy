"""Legacy module alias; implementation lives in admission/contracts.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.admission.contracts', __package__)
