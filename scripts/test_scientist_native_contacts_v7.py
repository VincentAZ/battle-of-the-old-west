"""CPU regression checks for the corrected overlay; synthetic rows are not play evidence."""
import math
import tempfile
from pathlib import Path
import unittest

import audit_scientist_native_contacts as base
import audit_scientist_native_contacts_v7 as v7
import test_scientist_native_contacts as original


class CorrectedContactAuditorTests(original.ContactAuditorTests):
    @classmethod
    def setUpClass(cls):
        cls.ref = v7.V7Reference()
        cls.raw = base.read(base.read(base.AUDIT)['dense_native_pose_report']['path'])
        cls.original_raw = {name:cls.raw[base.asset(name)] for name in v7.NAMES}
        cls.quarters = base.read(base.read(v7.READBACK)['dense_native_pose_report']['path'])
        for name in v7.NAMES:
            cls.raw[base.asset(name)] = cls.quarters[base.asset(name)][::4]

    def test_observed_native_half_frame_at_original_intersection(self):
        # The old visual defect existed between integer keys12 and13. Feed
        # actual independently readback quarter-frame bones into the synthetic
        # world fixture rather than generating expected bones with the auditor.
        for phase,quarter in [('holster',46),('unholster',314)]:
            name = phase.title(); seconds = quarter/120
            index = round(seconds*30); rows = self.raw[base.asset(name)]
            saved = rows[index]
            try:
                rows[index] = self.quarters[base.asset(name)][quarter]
                row = self.fixture(phase,seconds,0 if phase == 'unholster' else -2)
            finally:
                rows[index] = saved
            result = self.audit([row])
            self.assertTrue(result['ok'],result['failures'][:3])

    def test_old_holster_poses_cannot_pass_v7_reference(self):
        rows = self.raw[base.asset('Holster')]; saved = rows[12]
        try:
            rows[12] = self.original_raw['Holster'][12]
            old = self.fixture('holster',.4)
        finally:
            rows[12] = saved
        result = self.audit([old])
        self.assertFalse(result['ok'])
        self.assertTrue(any('bone' in f['check'] for f in result['failures']))

    def test_original_rifle_timing_is_not_quarter_frame_indexed(self):
        old = base.Reference()
        for name in v7.NAMES:
            self.assertEqual(len(self.ref.times[name]),91)
            for q in (1,46,105,253,359):
                errors = base.distance(self.ref.rifle(name,q/120),old.rifle(name,q/120))
                self.assertLess(errors[0],1e-9)
                self.assertLess(errors[1],1e-5)
                self.assertLess(errors[2],1e-9)

    def test_changed_observation_file_fails_audit_result(self):
        audit = base.Auditor(self.ref)
        audit.observe(self.fixture())
        with tempfile.TemporaryDirectory(prefix='scientist-immutability-') as folder:
            path = Path(folder)/'observations.jsonl'; path.write_text('original\n')
            before = [{'path':str(path),'sha256':base.sha(path)}]
            path.write_text('changed\n')
            self.assertFalse(v7.check_immutable_inputs(audit,before))
        self.assertFalse(audit.report()['ok'])


if __name__ == '__main__':
    unittest.main()
