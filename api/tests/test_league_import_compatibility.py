"""Retired forwarding paths, canonical patching and retained exception pickle shim."""
import importlib
import io
import pickle
import unittest
from unittest.mock import patch

PAIRS=(('admission_service','admission.service'),('admission_repository','admission.repository'),
       ('contracts','admission.contracts'),('member_service','members.service'),('member_repository','members.repository'),
       ('league_admin_service','administration.service'),('league_admin_repository','administration.repository'),
       ('league_read_service','reads.service'),('league_read_repository','reads.repository'),
       ('league_lifecycle_service','lifecycle.service'),('league_lifecycle_repository','lifecycle.repository'))


class LeagueImportCompatibilityTests(unittest.TestCase):
    def test_retired_forwarding_imports_are_unavailable(self):
        for old,new in PAIRS:
            if old == 'contracts':
                continue
            with self.subTest(module=old):
                name = 'endpoints.league.'+old
                with self.assertRaises(ModuleNotFoundError) as raised:
                    importlib.import_module(name)
                self.assertEqual(raised.exception.name,name)
    def test_canonical_repository_patch_controls_service_composition(self):
        service_module=importlib.import_module('endpoints.league.admission.service')
        canonical=importlib.import_module('endpoints.league.admission.service')
        class ReplacementRepository:pass
        with patch.object(service_module,'AdmissionRepository',ReplacementRepository):
            self.assertIsInstance(canonical.AdmissionService(object()).repository,ReplacementRepository)
    def test_legacy_exception_resolution_and_cross_path_catch(self):
        legacy=importlib.import_module('endpoints.league.contracts')
        canonical=importlib.import_module('endpoints.league.admission.contracts')
        unpickler=pickle.Unpickler(io.BytesIO())
        for name in ('AdmissionDenied','AdmissionRejected'):
            old=getattr(legacy,name);new=getattr(canonical,name)
            self.assertIs(unpickler.find_class('endpoints.league.contracts',name),new)
            with self.assertRaises(old):raise new('domain failure')
            self.assertIsInstance(pickle.loads(pickle.dumps(new('domain failure'))),old)
