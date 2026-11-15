"""Hosted QA guard tests only; no local geometry, image or asset output."""
import contextlib
import io
import unittest
from unittest import mock

import qa_merchant_gate_hosted as qa


def environment():
    return {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
            'GITHUB_REPOSITORY':qa.REPO,'GITHUB_REPOSITORY_ID':'1457160414',
            'GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW_REF':qa.WORKFLOW_REF,
            'GITHUB_SERVER_URL':'https://github.com','GITHUB_SHA':'a'*40,
            'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1',
            'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_WORKSPACE':str(qa.ROOT)}


class HostedQAGuardTests(unittest.TestCase):
    def test_expected_context_is_accepted_without_running_qa(self):
        with mock.patch.object(qa.sys,'platform','linux'),mock.patch.dict(qa.os.environ,environment(),clear=True), \
             mock.patch.object(qa,'run') as run:
            context=qa.hosted_context()
            self.assertEqual(context['repository'],qa.REPO)
            self.assertEqual(context['commit'],'a'*40)
            self.assertEqual(context['runner_environment'],'github-hosted')
            run.assert_not_called()

    def test_rejects_missing_or_wrong_host_identity(self):
        invalid={'GITHUB_ACTIONS':'false','RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Windows',
                 'GITHUB_REPOSITORY':'other/repo','GITHUB_REPOSITORY_ID':'1',
                 'GITHUB_REF':'refs/heads/other','GITHUB_WORKFLOW_REF':'other',
                 'GITHUB_SERVER_URL':'https://example.invalid','GITHUB_SHA':'bad',
                 'GITHUB_RUN_ID':'0','GITHUB_RUN_ATTEMPT':'0','GITHUB_EVENT_NAME':'pull_request',
                 'GITHUB_WORKSPACE':''}
        with mock.patch.object(qa.sys,'platform','win32'),mock.patch.dict(qa.os.environ,environment(),clear=True):
            with self.assertRaisesRegex(RuntimeError,'designated'):
                qa.hosted_context()
        for key,value in invalid.items():
            for candidate in (value,None):
                env=environment()
                if candidate is None: del env[key]
                else: env[key]=candidate
                with self.subTest(field=key,candidate=candidate),mock.patch.object(qa.sys,'platform','linux'), \
                     mock.patch.dict(qa.os.environ,env,clear=True),self.assertRaises((RuntimeError,OSError)):
                    qa.hosted_context()

    def test_local_command_refuses_before_qa(self):
        with mock.patch.object(qa.sys,'platform','win32'),mock.patch.object(qa.sys,'argv',['qa_merchant_gate_hosted.py']), \
             mock.patch.object(qa,'run') as run,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(qa.main(),1)
            run.assert_not_called()

    def test_resource_floor_and_ceiling_fail_closed(self):
        safe=(1,2**30,128*2**20,qa.MAX_RSS)
        invalid=((qa.MAX_SECONDS+1,*safe[1:]),(safe[0],2**30-1,*safe[2:]),
                 (safe[0],safe[1],128*2**20-1,safe[3]),(*safe[:3],qa.MAX_RSS+1),
                 (float('nan'),*safe[1:]))
        for values in invalid:
            with self.subTest(values=values),self.assertRaisesRegex(RuntimeError,'resource guard'):
                qa.validate_resources(*values)

    def test_preview_warning_glyphs_exist(self):
        self.assertFalse(set('FLAT SOURCE - NOT IN GAME')-set(qa.FONT))

    def test_baseline_hash_and_new_manifest_must_both_match(self):
        self.assertEqual(set(qa.BASELINE_HASHES),qa.GENERATED)
        for name,digest in qa.BASELINE_HASHES.items():
            recorded={'sha256':digest,'bytes':42}
            qa.verify_output_info(name,dict(recorded),recorded)
            with self.subTest(name=name,problem='changed file'),self.assertRaisesRegex(RuntimeError,'hash differs'):
                qa.verify_output_info(name,{'sha256':'0'*64,'bytes':42},recorded)
            with self.subTest(name=name,problem='self-consistent drift'),self.assertRaisesRegex(RuntimeError,'hash differs'):
                qa.verify_output_info(name,{'sha256':'0'*64,'bytes':42},{'sha256':'0'*64,'bytes':42})


@unittest.skipUnless(qa.sys.platform=='linux' and qa.os.environ.get('GITHUB_ACTIONS')=='true'
                     and qa.os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted',
                     'Synthetic geometry runs only on the hosted runner')
class HostedCorridorRegressions(unittest.TestCase):
    def test_triangle_crossing_with_no_vertex_inside_is_blocked(self):
        self.assertTrue(qa.intersects_passage([(-2,-2,1),(0,2,1),(2,0,4)]))

    def test_triangle_outside_corridor_is_clear(self):
        self.assertFalse(qa.intersects_passage([(0,1.4,1),(1,2,1),(-1,1.4,2)]))

    def test_boundary_contact_is_blocked(self):
        self.assertTrue(qa.intersects_passage([(0,1.25,1),(1,1.6,1),(-1,1.6,2)]))

    def test_ignored_floor_band_and_its_boundary(self):
        self.assertFalse(qa.intersects_passage([(0,-.5,.02),(1,.5,.03),(-1,0,.059)]))
        self.assertTrue(qa.intersects_passage([(0,-.5,.06),(1,.5,.06),(-1,0,.06)]))


if __name__=='__main__':
    unittest.main()
