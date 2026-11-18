"""Compatibility for serialized league exceptions."""
import importlib
import io
import pickle
import unittest

class LeagueImportCompatibilityTests(unittest.TestCase):
    def test_legacy_exception_resolution_and_cross_path_catch(self):
        legacy=importlib.import_module('endpoints.league.contracts')
        canonical=importlib.import_module('endpoints.league.admission.contracts')
        unpickler=pickle.Unpickler(io.BytesIO())
        for name in ('AdmissionDenied','AdmissionRejected'):
            old=getattr(legacy,name);new=getattr(canonical,name)
            self.assertIs(unpickler.find_class('endpoints.league.contracts',name),new)
            with self.assertRaises(old):raise new('domain failure')
            self.assertIsInstance(pickle.loads(pickle.dumps(new('domain failure'))),old)
