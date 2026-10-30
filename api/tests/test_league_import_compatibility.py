"""Legacy imports retain identity and dependency patch behavior after grouping."""
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
    def test_legacy_and_canonical_imports_share_module_identity(self):
        for old,new in PAIRS:
            with self.subTest(module=old):
                legacy=importlib.import_module('endpoints.league.'+old)
                canonical=importlib.import_module('endpoints.league.'+new)
                self.assertIs(legacy,canonical)
    def test_legacy_repository_patch_changes_canonical_service_composition(self):
        legacy=importlib.import_module('endpoints.league.admission_service')
        canonical=importlib.import_module('endpoints.league.admission.service')
        class ReplacementRepository:pass
        with patch.object(legacy,'AdmissionRepository',ReplacementRepository):
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
