"""Legacy module alias; implementation lives in reads/repository.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.reads.repository', __package__)
