"""Legacy module alias; implementation lives in administration/repository.py."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('.administration.repository', __package__)
