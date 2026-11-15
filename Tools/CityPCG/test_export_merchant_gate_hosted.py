"""Local guard-rejection and tiny geometry tests; never exports an asset."""

import contextlib
import io
import unittest
from unittest import mock

import build_merchant_gate_procedural as gate
import export_merchant_gate_hosted as hosted
from audit_merchant_gate import audit_geometry


def example_environment():
    return {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted',
            'RUNNER_OS':'Linux','GITHUB_REPOSITORY':hosted.REPOSITORY,
            'GITHUB_REPOSITORY_ID':hosted.REPOSITORY_ID,'GITHUB_REF':hosted.BRANCH,
            'GITHUB_SERVER_URL':'https://github.com','GITHUB_WORKFLOW_REF':hosted.WORKFLOW_REF,
            'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_SHA':'a'*40,
            'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_WORKSPACE':str(hosted.PROJECT)}


class HostedRejectionTests(unittest.TestCase):
    def test_expected_hosted_context_is_accepted_without_generating(self):
        with mock.patch.object(hosted.sys,'platform','linux'), \
             mock.patch.dict(hosted.os.environ,example_environment(),clear=True), \
             mock.patch.object(hosted,'generate') as generate:
            context = hosted.hosted_context()
            self.assertEqual(context['repository'],hosted.REPOSITORY)
            self.assertEqual(context['commit'],'a'*40)
            self.assertEqual(context['runner_environment'],'github-hosted')
            generate.assert_not_called()

    def test_rejects_non_linux_and_every_bad_identity_field(self):
        with mock.patch.object(hosted.sys,'platform','win32'), \
             mock.patch.dict(hosted.os.environ,example_environment(),clear=True):
            with self.assertRaisesRegex(RuntimeError,'designated'):
                hosted.hosted_context()
        invalid = {'GITHUB_ACTIONS':'false','RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Windows',
                   'GITHUB_REPOSITORY':'someone/else','GITHUB_REPOSITORY_ID':'99',
                   'GITHUB_REF':'refs/heads/other','GITHUB_SERVER_URL':'https://example.com',
                   'GITHUB_WORKFLOW_REF':'other','GITHUB_EVENT_NAME':'pull_request',
                   'GITHUB_SHA':'not-a-sha','GITHUB_RUN_ID':'0','GITHUB_RUN_ATTEMPT':'0',
                   'GITHUB_WORKSPACE':''}
        for key,value in invalid.items():
            env = example_environment()
            env[key] = value
            with self.subTest(field=key),mock.patch.object(hosted.sys,'platform','linux'), \
                 mock.patch.dict(hosted.os.environ,env,clear=True):
                with self.assertRaises(RuntimeError):
                    hosted.hosted_context()

    def test_missing_fields_fail_closed(self):
        for key in example_environment():
            env = example_environment()
            del env[key]
            with self.subTest(field=key),mock.patch.object(hosted.sys,'platform','linux'), \
                 mock.patch.dict(hosted.os.environ,env,clear=True):
                with self.assertRaises(RuntimeError):
                    hosted.hosted_context()

    def test_local_cli_refuses_before_generation(self):
        with mock.patch.object(hosted.sys,'platform','win32'), \
             mock.patch.object(hosted.sys,'argv',['export_merchant_gate_hosted.py']), \
             mock.patch.object(hosted,'generate') as generate, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(hosted.main(),1)
            generate.assert_not_called()

    def test_push_rejects_wrong_event_or_changed_paths(self):
        sha,before = 'a'*40,'b'*40
        base = {'before':before,'after':sha,'ref':hosted.BRANCH,'forced':False,
                'created':False,'deleted':False,'repository':{'full_name':hosted.REPOSITORY}}
        for key,value in (('forced',True),('created',True),('deleted',True),
                          ('before','0'*40),('after','c'*40),('ref','refs/heads/other'),
                          ('repository',{'full_name':'other/repo'})):
            payload=dict(base)
            payload[key]=value
            with self.subTest(field=key),mock.patch.object(hosted,'git') as run_git:
                with self.assertRaises(RuntimeError):
                    hosted.validate_push_payload(payload,sha)
                run_git.assert_not_called()
        with mock.patch.object(hosted,'git',side_effect=[f'{sha} {before}\n'.encode(),
                                                        (hosted.WORKFLOW+'\0other.py\0').encode()]):
            with self.assertRaisesRegex(RuntimeError,'only the hosted workflow'):
                hosted.validate_push_payload(base,sha)
        with mock.patch.object(hosted,'git',return_value=f'{sha} {before} {"c"*40}\n'.encode()):
            with self.assertRaisesRegex(RuntimeError,'single-parent'):
                hosted.validate_push_payload(base,sha)

    def test_single_parent_workflow_only_push_is_accepted(self):
        sha,before = 'a'*40,'b'*40
        payload = {'before':before,'after':sha,'ref':hosted.BRANCH,'forced':False,
                   'created':False,'deleted':False,'repository':{'full_name':hosted.REPOSITORY}}
        with mock.patch.object(hosted,'git',side_effect=[f'{sha} {before}\n'.encode(),
                                                        (hosted.WORKFLOW+'\0').encode()]) as run_git, \
             mock.patch.object(hosted,'generate') as generate:
            hosted.validate_push_payload(payload,sha)
            self.assertEqual(run_git.call_count,2)
            generate.assert_not_called()

    def test_resource_limits_reject_excess_or_low_capacity(self):
        safe=(1,hosted.MIN_AVAILABLE_RAM,hosted.MIN_FREE_DISK,hosted.MAX_RSS)
        bad=((hosted.MAX_WALL_SECONDS+1,*safe[1:]),
             (safe[0],hosted.MIN_AVAILABLE_RAM-1,*safe[2:]),
             (safe[0],safe[1],hosted.MIN_FREE_DISK-1,safe[3]),
             (*safe[:3],hosted.MAX_RSS+1),
             (float('nan'),*safe[1:]))
        for values in bad:
            with self.subTest(values=values),self.assertRaisesRegex(RuntimeError,'resource guard'):
                hosted.validate_resource_state(*values)

    def test_existing_coarse_mesh_still_has_open_cart_passage(self):
        mesh=gate.build_gate('tiny')
        report=audit_geometry(mesh.triangles())
        self.assertEqual(report['status'],'passed',report['errors'])
        self.assertEqual(report['obstructing_triangles'],0)
        self.assertEqual((report['clear_width_m'],report['clear_height_m']),(2.5,2.7))


if __name__=='__main__':
    unittest.main()
