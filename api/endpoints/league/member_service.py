"""Legacy module alias; implementation lives in members/service.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.members.service', __package__)
