"""Legacy module alias; implementation lives in lifecycle/service.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.lifecycle.service', __package__)
