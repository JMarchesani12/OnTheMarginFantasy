"""Legacy module alias; implementation lives in members/repository.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.members.repository', __package__)
