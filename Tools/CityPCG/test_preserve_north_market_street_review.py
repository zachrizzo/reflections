"""Synthetic preservation checks; no network, Git writes or archive output."""
import hashlib
import io
import json
import stat
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import preserve_north_market_street_review as p


class Sink(io.BytesIO):
    def __init__(self,outputs,name): super().__init__(); self.outputs=outputs; self.name=name
    def close(self):
        if not self.closed: self.outputs[self.name]=self.getvalue()
        super().close()
    def __exit__(self,*args): self.close()


class Stage:
    def __init__(self): self.outputs={}
    def __truediv__(self,name):
        stage=self
        class Target:
            def open(self,mode):
                if mode!='xb' or name in stage.outputs: raise ValueError('unexpected output')
                return Sink(stage.outputs,name)
        return Target()


def reports(files):
    report={'status':'illustrative review only; not a playable or map-approved scene',
            'commit':p.SOURCE_COMMIT,'files':files}
    raw=(json.dumps(report,sort_keys=True)+'\n').encode()
    manifest={'status':'review-only; no Unreal placement or gameplay validation','commit':p.SOURCE_COMMIT,
              'build_report_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':dict(files),
              'independent_glb_reimport':{'meshes':12,'triangles':12345}}
    return manifest,report,raw


def fake_zip_info(name,size=10):
    value=zipfile.ZipInfo(name); value.file_size=size; return value


def fake_helper():
    return SimpleNamespace(readback_environment=mock.Mock(return_value={}),readback_options=mock.Mock(return_value=()),
        check_readback_environment=mock.Mock(),git=mock.Mock(side_effect=[SimpleNamespace(stdout=b'env'),
            SimpleNamespace(stdout=b'pointer')]),check_pointer=mock.Mock(),git_command=mock.Mock(return_value=['git']),
        limit_child_files=mock.Mock(),smudge_file_ceiling=mock.Mock(return_value=64*2**20),
        report_smudge_error=mock.Mock(),SMUDGE_FILE_CEILING=64*2**20)


class PreserveStreetTests(unittest.TestCase):
    def test_artifact_metadata_requires_exact_pin(self):
        data={'id':p.ARTIFACT['id'],'name':p.ARTIFACT['name'],'size_in_bytes':p.ARTIFACT['size'],
              'digest':'sha256:'+p.ARTIFACT['sha256'],'expired':False,
              'workflow_run':{'id':p.ARTIFACT['run'],'repository_id':1457160414,
                              'head_repository_id':1457160414,'head_branch':'main','head_sha':p.SOURCE_COMMIT}}
        p.check_metadata(data)
        for field,value in (('id',1),('name','other'),('size_in_bytes',1),('digest','sha256:'+'0'*64),
                            ('expired',True),('workflow_run',{'id':1})):
            changed=dict(data); changed[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError): p.check_metadata(changed)
        for field,value in (('repository_id',1),('head_repository_id',1),('head_branch','other'),('head_sha','0'*40)):
            changed=dict(data); changed['workflow_run']=dict(data['workflow_run']); changed['workflow_run'][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError): p.check_metadata(changed)

    def test_exact_inventory_rejects_unknown_duplicate_links_and_size(self):
        base=[fake_zip_info(name) for name in sorted(p.MEMBERS)]
        self.assertEqual(set(p.validate_members(base)),p.MEMBERS)
        for extra in (fake_zip_info('../bad'),fake_zip_info('unknown.txt'),base[0]):
            with self.assertRaises(ValueError): p.validate_members(base+[extra])
        link=fake_zip_info(sorted(p.MEMBERS)[0]); link.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError): p.validate_members([link,*base[1:]])
        huge=fake_zip_info(sorted(p.MEMBERS)[0],160*2**20+1)
        with self.assertRaises(ValueError): p.validate_members([huge,*base[1:]])

    def test_reports_are_cross_bound_and_require_glb_reimport(self):
        files={name:'a'*64 for name in p.OUTPUTS}; manifest,report,raw=reports(files)
        sha=hashlib.sha256(raw).hexdigest(); p.check_reports(manifest,report,sha)
        for field,value in (('commit','0'*40),('status','approved'),('build_report_sha256','0'*64),
                            ('independent_glb_reimport',{'meshes':0,'triangles':0})):
            altered=dict(manifest); altered[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): p.check_reports(altered,report,sha)
        changed=dict(report); changed['files']=dict(files); changed['files'].pop('street_eye_level.png')
        with self.assertRaises(ValueError): p.check_reports(manifest,changed,sha)

    def test_png_header_and_dimensions(self):
        valid=b'\x89PNG\r\n\x1a\n'+b'\0\0\0\rIHDR'+struct.pack('>II',1024,576)
        p.check_png_header(valid)
        for bad in (b'not png',valid[:16]+struct.pack('>II',720,480),valid[:12]+b'NOPE'+valid[16:]):
            with self.assertRaises(ValueError): p.check_png_header(bad)

    def test_synthetic_archive_streams_only_approved_images_and_reports(self):
        png=b'\x89PNG\r\n\x1a\n'+b'\0\0\0\rIHDR'+struct.pack('>II',1024,576)+b'preview'
        payload={name:(png if name in ('street_eye_level.png','street_trestle.png') else ('test:'+name).encode())
                 for name in p.OUTPUTS}
        files={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
        manifest,_,report_raw=reports(files)
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,value in payload.items(): archive.writestr(name,value)
            archive.writestr('build.report.json',report_raw)
            archive.writestr('manifest.json',(json.dumps(manifest)+'\n').encode())
        data.seek(0); stage=Stage(); result=p.inspect_archive(data,stage)
        self.assertEqual(set(stage.outputs),set(p.COPIES))
        self.assertEqual(set(result),set(p.COPIES))
        self.assertEqual(stage.outputs['street_eye_level.png'],png)

    def test_push_must_be_single_parent_and_workflow_only(self):
        sha,before='a'*40,'b'*40
        p.check_push_shape(sha,before,[sha,before],p.WORKFLOW.encode()+b'\0')
        with self.assertRaises(RuntimeError): p.check_push_shape(sha,before,[sha,before,'c'*40],p.WORKFLOW.encode()+b'\0')
        with self.assertRaises(RuntimeError): p.check_push_shape(sha,before,[sha,before],p.WORKFLOW.encode()+b'\0other\0')

    def test_local_context_rejected(self):
        with mock.patch.object(p.sys,'platform','win32'),mock.patch.dict(p.os.environ,{},clear=True):
            with self.assertRaises(RuntimeError): p.context()

    def test_isolated_readback_requires_exact_output_and_cache(self):
        expected=(p.ARTIFACT['size'],p.ARTIFACT['sha256'])
        for values,ok in (((expected,expected),True),(((1,'bad'),expected),False),
                          ((expected,(1,'bad')),False),(((expected[0]+1,expected[1]),expected),False),
                          ((expected,(expected[0]+1,expected[1])),False)):
            h=fake_helper(); process=SimpleNamespace(pid=321,returncode=0,communicate=mock.Mock(),wait=mock.Mock())
            with self.subTest(values=values),mock.patch.object(p.Path,'mkdir'), \
                 mock.patch.object(p.Path,'exists',return_value=False),mock.patch.object(p.Path,'is_symlink',return_value=False), \
                 mock.patch.object(p.Path,'open',return_value=io.BytesIO()),mock.patch.object(p.os,'open',return_value=42), \
                 mock.patch.object(p.os,'fdopen',return_value=io.BytesIO()), \
                 mock.patch.object(p.subprocess,'Popen',return_value=process) as spawn, \
                 mock.patch.object(p,'digest',side_effect=values):
                if ok: p.isolated_readback(h,{},Path('/stage'),'a'*40,'exact.zip')
                else:
                    with self.assertRaisesRegex(RuntimeError,'lfs-readback'):
                        p.isolated_readback(h,{},Path('/stage'),'a'*40,'exact.zip')
                process.communicate.assert_called_once_with(input=b'pointer',timeout=120)
                self.assertTrue(spawn.call_args.kwargs['start_new_session'])

    def test_isolated_readback_timeout_or_error_kills_process_group(self):
        for exception,code in ((subprocess.TimeoutExpired('mock',120),0),(None,3)):
            h=fake_helper(); process=SimpleNamespace(pid=321,returncode=code,
                communicate=mock.Mock(side_effect=exception),wait=mock.Mock())
            with self.subTest(code=code),mock.patch.object(p.Path,'mkdir'), \
                 mock.patch.object(p.Path,'exists',return_value=False),mock.patch.object(p.Path,'is_symlink',return_value=False), \
                 mock.patch.object(p.Path,'open',return_value=io.BytesIO()),mock.patch.object(p.os,'open',return_value=42), \
                 mock.patch.object(p.os,'fdopen',return_value=io.BytesIO()), \
                 mock.patch.object(p.subprocess,'Popen',return_value=process), \
                 mock.patch.object(p.os,'killpg',create=True) as kill, \
                 mock.patch.object(p.signal,'SIGKILL',9,create=True):
                with self.assertRaises((RuntimeError,subprocess.TimeoutExpired)):
                    p.isolated_readback(h,{},Path('/stage'),'a'*40,'exact.zip')
                kill.assert_called_once_with(321,9); process.wait.assert_called_once_with(timeout=5)
                h.report_smudge_error.assert_called_once()


if __name__=='__main__': unittest.main()
