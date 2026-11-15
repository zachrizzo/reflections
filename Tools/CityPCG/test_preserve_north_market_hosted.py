"""Small mocked preservation checks; no network, asset processing or Git writes."""
from pathlib import Path
import io
import stat
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import preserve_north_market_hosted as p


def environment():
    return {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
            'GITHUB_REPOSITORY':p.REPO,'GITHUB_REPOSITORY_ID':'1457160414',
            'GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW_REF':p.WORKFLOW_REF,
            'GITHUB_SERVER_URL':'https://github.com','GITHUB_API_URL':'https://api.github.com',
            'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1',
            'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_WORKSPACE':str(p.ROOT),
            'RUNNER_TEMP':str(Path(p.ROOT.anchor)),'GH_TOKEN':'mock-token'}


class PreservationTests(unittest.TestCase):
    def test_artifact_pins_and_metadata(self):
        self.assertEqual(len(p.ARTIFACTS),4)
        self.assertEqual(len({item['id'] for item in p.ARTIFACTS}),4)
        self.assertEqual(len({item['sha256'] for item in p.ARTIFACTS}),4)
        for item in p.ARTIFACTS:
            data={'id':item['id'],'expired':False,'name':'north-market-fbx-review-'+item['key'].replace('_','-'),
                  'size_in_bytes':item['size'],'digest':'sha256:'+item['sha256'],
                  'workflow_run':{'id':item['run']}}
            p.validate_metadata(data,item)
            for key,value in (('id',0),('expired',True),('name','other'),('size_in_bytes',1),
                              ('digest','sha256:'+'0'*64),('workflow_run',{'id':1})):
                changed=dict(data); changed[key]=value
                with self.subTest(item=item['key'],field=key),self.assertRaises(RuntimeError):
                    p.validate_metadata(changed,item)

    def test_storage_host_and_redirect_boundaries(self):
        self.assertTrue(p.storage_url('https://x.blob.core.windows.net/a?sig=abc'))
        self.assertTrue(p.storage_url('https://results.actions.githubusercontent.com/a?sig=abc'))
        for value in ('http://x.blob.core.windows.net/a','https://x.blob.core.windows.net.evil.invalid/a',
                      'https://user:pass@x.blob.core.windows.net/a','https://x.blob.core.windows.net:444/a',
                      'https://x.blob.core.windows.net/a#fragment','https://evil.invalid/a'):
            with self.subTest(value=value): self.assertFalse(p.storage_url(value))
        self.assertIsNone(p.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid/'))

    def test_lfs_pointer_requires_exact_oid_and_size(self):
        item=p.ARTIFACTS[0]
        good=(f"version https://git-lfs.github.com/spec/v1\noid sha256:{item['sha256']}\nsize {item['size']}\n").encode()
        p.check_pointer(good,item)
        for value in (good.replace(item['sha256'].encode(),b'0'*64),good.replace(str(item['size']).encode(),b'1'),good[:-1]):
            with self.assertRaisesRegex(RuntimeError,'lfs-pointer'): p.check_pointer(value,item)

    def test_readback_is_isolated_and_environment_is_strict(self):
        original={'GIT_LFS_SKIP_SMUDGE':'1','GIT_LFS_SKIP_DOWNLOAD_ERRORS':'1',
                  'GIT_ALTERNATE_OBJECT_DIRECTORIES':'bad','GH_TOKEN':'mock-token'}
        scoped=p.readback_environment(original)
        self.assertEqual(original['GIT_LFS_SKIP_SMUDGE'],'1')
        for key in ('GIT_LFS_SKIP_SMUDGE','GIT_LFS_SKIP_DOWNLOAD_ERRORS','GIT_ALTERNATE_OBJECT_DIRECTORIES'):
            self.assertNotIn(key,scoped)
        self.assertEqual(scoped['GIT_CONFIG_NOSYSTEM'],'1')
        self.assertEqual(scoped['GIT_CONFIG_GLOBAL'],'/dev/null')
        store=Path('/private/readback')
        options=p.readback_options(store)
        for option in ('lfs.fetchinclude=','lfs.fetchexclude=','lfs.skipdownloaderrors=false',
                       'lfs.basictransfersonly=true','lfs.remote.autodetect=false','lfs.remote.searchall=false'):
            self.assertIn(option,options)
        good=('LocalReferenceDirs=\nLocalMediaDir='+str(store/'objects')+'\nLfsStorageDir='+str(store)
              +'\nSkipDownloadErrors=false\nBasicTransfersOnly=true\n').encode()
        p.check_readback_environment(good,store)
        for bad in (good.replace(b'LocalReferenceDirs=',b'LocalReferenceDirs=/other'),
                    good.replace(b'SkipDownloadErrors=false',b'SkipDownloadErrors=true'),
                    good+b'FetchExclude=*.zip\n',good+b'GIT_ALTERNATE_OBJECT_DIRECTORIES=bad\n'):
            with self.assertRaisesRegex(RuntimeError,'lfs-readback-environment'):
                p.check_readback_environment(bad,store)

    def test_child_limit_covers_each_file(self):
        resource=SimpleNamespace(RLIMIT_FSIZE=17,setrlimit=mock.Mock())
        with mock.patch.dict(sys.modules,{'resource':resource}): p.limit_child_files(1234)
        resource.setrlimit.assert_called_once_with(17,(1234,1234))

    def test_smudge_receives_only_checked_pointer_and_capped_sink(self):
        item=p.ARTIFACTS[0]; pointer=p.pointer_bytes(item)
        process=SimpleNamespace(pid=321,returncode=0,communicate=mock.Mock(),wait=mock.Mock())
        with mock.patch.object(p.Path,'open',return_value=io.BytesIO()) as opened, \
             mock.patch.object(p.subprocess,'Popen',return_value=process) as spawn:
            p.smudge_to_file({'GH_TOKEN':'mock-token'},Path('/store'),item,pointer,Path('/output'))
        opened.assert_called_once_with('xb')
        args,kwargs=spawn.call_args
        self.assertEqual(args[0][-2:],['smudge',(p.TARGET_REL/(item['key']+'.zip')).as_posix()])
        self.assertEqual(kwargs['stderr'],subprocess.DEVNULL)
        self.assertTrue(kwargs['start_new_session'])
        self.assertTrue(callable(kwargs['preexec_fn']))
        process.communicate.assert_called_once_with(input=pointer,timeout=60)
        with self.assertRaisesRegex(RuntimeError,'lfs-pointer'):
            p.smudge_to_file({},Path('/store'),item,b'bad pointer',Path('/output'))

    def test_smudge_timeout_and_failure_kill_process_group(self):
        item=p.ARTIFACTS[0]; pointer=p.pointer_bytes(item)
        cases=((subprocess.TimeoutExpired('mock',60),0),(TimeoutError('overall-timeout'),0),(None,3))
        for exception,code in cases:
            process=SimpleNamespace(pid=321,returncode=code,communicate=mock.Mock(side_effect=exception),wait=mock.Mock())
            with self.subTest(code=code),mock.patch.object(p.Path,'open',return_value=io.BytesIO()), \
                 mock.patch.object(p.subprocess,'Popen',return_value=process), \
                 mock.patch.object(p.os,'killpg',create=True) as kill, \
                 mock.patch.object(p.signal,'SIGKILL',9,create=True):
                with self.assertRaises((RuntimeError,subprocess.TimeoutExpired,TimeoutError)):
                    p.smudge_to_file({},Path('/store'),item,pointer,Path('/output'))
                kill.assert_called_once_with(321,9)
                process.wait.assert_called_once_with(timeout=5)

    def test_overall_deadline_raises_for_child_cleanup(self):
        with self.assertRaisesRegex(TimeoutError,'overall-timeout'):
            p.overall_timeout(None,None)

    def test_streamed_hash_rejects_wrong_or_oversized_output(self):
        data=b'small synthetic output'
        with mock.patch.object(p.Path,'open',return_value=io.BytesIO(data)):
            size,digest=p.sha_file(Path('/output'),len(data))
        self.assertEqual(size,len(data))
        self.assertEqual(digest,p.hashlib.sha256(data).hexdigest())
        with mock.patch.object(p.Path,'open',return_value=io.BytesIO(data)):
            with self.assertRaisesRegex(RuntimeError,'file-size'): p.sha_file(Path('/output'),len(data)-1)

    def test_readback_requires_both_output_and_fresh_cache_to_match(self):
        item=p.ARTIFACTS[0]; expected=(item['size'],item['sha256'])
        store=Path('/stage')/('lfs-readback-'+item['key'])
        report=('LocalReferenceDirs=\nLocalMediaDir='+str(store/'objects')+'\nLfsStorageDir='+str(store)
                +'\nSkipDownloadErrors=false\nBasicTransfersOnly=true\n').encode()
        for values,ok in (((expected,expected),True),(((1,'bad'),expected),False),((expected,(1,'bad')),False)):
            replies=[SimpleNamespace(stdout=report),SimpleNamespace(stdout=p.pointer_bytes(item))]
            with self.subTest(ok=ok,values=values),mock.patch.object(p.Path,'mkdir'), \
                 mock.patch.object(p.Path,'exists',return_value=False), \
                 mock.patch.object(p.Path,'is_symlink',return_value=False), \
                 mock.patch.object(p,'git',side_effect=replies), \
                 mock.patch.object(p,'smudge_to_file'),mock.patch.object(p,'sha_file',side_effect=values):
                if ok: p.verify_lfs_readback({},Path('/stage'),'a'*40,item)
                else:
                    with self.assertRaisesRegex(RuntimeError,'lfs-readback'):
                        p.verify_lfs_readback({},Path('/stage'),'a'*40,item)

    def test_no_readback_alternates_or_custom_agents(self):
        def response(data=b'',code=0): return SimpleNamespace(stdout=data,returncode=code)
        for alternate,agent,lfsconfig,expected in ((False,False,False,None),(True,False,False,'git-alternates'),
                (False,True,False,'lfs-standalone-agent'),(False,False,True,'lfsconfig')):
            outputs=[response(b'.git\n'),response(b'lfs.standalonetransferagent=bad\n' if agent else b'',0 if agent else 1),
                     response(b'.lfsconfig\n' if lfsconfig else b'')]
            with self.subTest(alternate=alternate,agent=agent,lfsconfig=lfsconfig), \
                 mock.patch.object(p,'git',side_effect=outputs), \
                 mock.patch.object(p.Path,'resolve',return_value=Path('/repo/.git')), \
                 mock.patch.object(p.Path,'exists',return_value=alternate), \
                 mock.patch.object(p.Path,'is_symlink',return_value=False):
                if expected:
                    with self.assertRaisesRegex(RuntimeError,expected): p.check_no_readback_alternates({},'a'*40)
                else:
                    p.check_no_readback_alternates({},'a'*40)

    def test_only_canonical_fetch_and_push_origins_are_accepted(self):
        sha='a'*40
        ctx={'sha':sha,'event':'workflow_dispatch'}
        def check(origins,push_origins):
            outputs=[SimpleNamespace(stdout=(sha+'\n').encode(),returncode=0),
                     SimpleNamespace(stdout=b'',returncode=0),
                     SimpleNamespace(stdout=('\n'.join(origins)+'\n').encode(),returncode=0),
                     SimpleNamespace(stdout=('\n'.join(push_origins)+'\n').encode(),returncode=0),
                     SimpleNamespace(stdout=b'',returncode=1)]
            with mock.patch.object(p,'git',side_effect=outputs): p.verify_revision(ctx,{})
        for good in sorted(p.CANONICAL_ORIGINS): check([good],[good])
        for fetch,push in ((['https://evil.invalid/r'],[next(iter(p.CANONICAL_ORIGINS))]),
                           ([next(iter(p.CANONICAL_ORIGINS))],['https://evil.invalid/r']),
                           ([next(iter(p.CANONICAL_ORIGINS))],[*p.CANONICAL_ORIGINS])):
            with self.subTest(fetch=fetch,push=push),self.assertRaisesRegex(RuntimeError,'unexpected-origin'):
                check(fetch,push)

    def test_git_pins_endpoint_and_disables_redirects_and_helpers(self):
        result=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
        with mock.patch.object(p.subprocess,'run',return_value=result) as call:
            p.git({'GH_TOKEN':'mock-token'},'status')
        command=call.call_args.args[0]
        for option in ('credential.helper=','core.hooksPath=/dev/null','http.followRedirects=false',
                       'lfs.url='+p.LFS_ENDPOINT,'lfs.pushurl='+p.LFS_ENDPOINT,
                       'remote.origin.lfsurl='+p.LFS_ENDPOINT,'remote.origin.lfspushurl='+p.LFS_ENDPOINT):
            self.assertIn(option,command)
        self.assertNotIn('mock-token',' '.join(command))

    def test_workflow_push_must_be_single_parent_and_only_this_file(self):
        sha,before='a'*40,'b'*40
        payload={'before':before,'after':sha,'ref':'refs/heads/main','forced':False,'created':False,
                 'deleted':False,'repository':{'full_name':p.REPO}}
        self.assertEqual(p.push_before(payload,sha),before)
        p.check_push_shape(sha,before,(sha+' '+before+'\n').encode(),p.WORKFLOW.encode()+b'\0')
        for key,value in (('forced',True),('deleted',True),('created',True),('before','0'*40),('after','c'*40)):
            bad=dict(payload); bad[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError): p.push_before(bad,sha)
        with self.assertRaises(RuntimeError): p.check_push_shape(sha,before,(sha+' '+before+' '+'c'*40).encode(),p.WORKFLOW.encode()+b'\0')
        with self.assertRaises(RuntimeError): p.check_push_shape(sha,before,(sha+' '+before).encode(),p.WORKFLOW.encode()+b'\0extra\0')

    def test_preview_members_reject_links_duplicates_and_oversize(self):
        entry=zipfile.ZipInfo('preview/eye_level.png'); entry.file_size=20
        archive=SimpleNamespace(infolist=lambda:[entry])
        self.assertIs(p.safe_member(archive,entry.filename,100),entry)
        with self.assertRaises(RuntimeError): p.safe_member(SimpleNamespace(infolist=lambda:[entry,entry]),entry.filename,100)
        entry.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(RuntimeError): p.safe_member(archive,entry.filename,100)
        entry.external_attr=stat.S_IFREG<<16; entry.file_size=101
        with self.assertRaises(RuntimeError): p.safe_member(archive,entry.filename,100)

    def test_host_context_rejects_local_and_changed_identity(self):
        with mock.patch.object(p.sys,'platform','win32'),mock.patch.dict(p.os.environ,environment(),clear=True):
            with self.assertRaisesRegex(RuntimeError,'host-context'): p.context()
        for key in ('GITHUB_ACTIONS','RUNNER_ENVIRONMENT','RUNNER_OS','GITHUB_REPOSITORY',
                    'GITHUB_REPOSITORY_ID','GITHUB_REF','GITHUB_WORKFLOW_REF','GITHUB_API_URL'):
            env=environment(); env[key]='wrong'
            with self.subTest(key=key),mock.patch.object(p.sys,'platform','linux'), \
                 mock.patch.dict(p.os.environ,env,clear=True),self.assertRaises(RuntimeError): p.context()


if __name__=='__main__':
    unittest.main()
