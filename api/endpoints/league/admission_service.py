"""Legacy module alias; implementation lives in admission/service.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.admission.service', __package__)
