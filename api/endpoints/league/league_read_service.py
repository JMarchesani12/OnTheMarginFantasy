"""Legacy module alias; implementation lives in reads/service.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.reads.service', __package__)
