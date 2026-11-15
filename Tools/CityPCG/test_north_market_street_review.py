"""Lightweight tests; no Blender, Unreal, geometry output or network."""
import math
import hashlib
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import north_market_street_review_common as c


class StreetReviewTests(unittest.TestCase):
    def test_surveyed_building_pose(self):
        origin=[3310.546,522.412,.2]; other=[3339.404,540.64,.2]
        point,yaw=c.relative_pose(origin,24.35984172,other,-155.94767953)
        self.assertAlmostEqual(point[0],33.807289,places=5)
        self.assertAlmostEqual(point[1],4.702271,places=5)
        self.assertAlmostEqual(point[2],0,places=7)
        self.assertAlmostEqual(yaw,-180.30752125,places=7)
        with self.assertRaises(ValueError): c.relative_pose(origin,math.nan,other,0)

    def test_building_pose_rejects_hidden_scale_rotation_or_nonfinite_values(self):
        identity=[[1.0 if i==j else 0.0 for j in range(4)] for i in range(4)]
        c.check_identity(identity)
        for i,j,value in ((0,0,1.2),(0,3,.01),(1,2,.01),(2,2,math.nan)):
            bad=[row[:] for row in identity]; bad[i][j]=value
            with self.subTest(i=i,j=j),self.assertRaises(ValueError): c.check_identity(bad)
        pose=[[0.,-1.,0.,3.],[1.,0.,0.,4.],[0.,0.,1.,.2],[0.,0.,0.,1.]]
        c.check_pose(pose,[3.,4.,.2],90.)
        pose[0][3]=3.01
        with self.assertRaises(ValueError): c.check_pose(pose,[3.,4.,.2],90.)

    def test_scene_recipe_uses_surveyed_entry_and_flags_props_illustrative(self):
        a,b=(c.MODELS[k]['name'] for k in ('east_0a73564b','east_31c9ff1a'))
        manifest={'buildings':{
            'a':{'source_artifact':{'file':a+'.obj'},'world_pivot_m':[3310.546,522.412,.2],'yaw_deg':24.35984172},
            'b':{'source_artifact':{'file':b+'.obj'},'world_pivot_m':[3339.404,540.64,.2],'yaw_deg':-155.94767953}}}
        entry={'id':'Tile_p03_p01_roof_0a73564b5b0ed26a','entry':{'edge':21,'center_local_xy_m':[25.89503,-21.055861]}}
        recipe=c.scene_recipe(manifest,{'buildings':[entry]})
        self.assertIn('illustrative',recipe['prop_placements'])
        self.assertEqual(recipe['entry_local_m'],[25.89503,-21.055861])
        self.assertIn('market_stall',recipe['props'])
        entry['entry']['edge']=1
        with self.assertRaises(ValueError): c.scene_recipe(manifest,{'buildings':[entry]})

    def test_archive_names_reject_traversal_redirects_and_links(self):
        for name in ('../outside','/absolute','a/../b','a/./b','a//b','a\\b','C:/b'):
            info=SimpleNamespace(filename=name,external_attr=0,flag_bits=0)
            with self.subTest(name=name): self.assertFalse(c.safe_archive_name(info))
        normal=zipfile.ZipInfo('model/model.fbx'); normal.external_attr=(stat.S_IFREG|0o644)<<16
        self.assertTrue(c.safe_archive_name(normal))
        normal.external_attr=(stat.S_IFLNK|0o777)<<16
        self.assertFalse(c.safe_archive_name(normal))
        normal.external_attr=(stat.S_IFREG|0o644)<<16; normal.flag_bits=1
        self.assertFalse(c.safe_archive_name(normal))

    def test_inputs_and_prop_layout_are_bounded_and_pinned(self):
        self.assertEqual(len(c.MODELS),2)
        self.assertEqual(len(c.PROP_LAYOUT),9)
        for path,sha in c.INPUTS.items():
            self.assertFalse(Path(path).is_absolute())
            self.assertEqual(len(sha),64)
            int(sha,16)
        for position,yaw in c.PROP_LAYOUT.values():
            self.assertEqual(len(position),3)
            self.assertTrue(all(math.isfinite(x) for x in (*position,yaw)))

    def test_plan_lf_and_crlf_match_but_content_changes_fail(self):
        lf=b'{\n  "sample": 1\n}\n'; crlf=lf.replace(b'\n',b'\r\n')
        pin=hashlib.sha256(lf).hexdigest()
        c.verify_plan_bytes(lf,pin); c.verify_plan_bytes(crlf,pin)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            c.verify_plan_bytes(lf.replace(b'1',b'2'),pin)
        with self.assertRaisesRegex(ValueError,'line ending'):
            c.verify_plan_bytes(b'{\r}',pin)
        with self.assertRaises(ValueError): c.canonical_plan_digest(b'x'*(1024*1024+1))
        self.assertEqual(c.INPUTS[c.PLAN],
            '88ea66f0292864f8f6b9924d654a323edb37da9ce307754f7f9f57fc77fbc32f')

    def test_tenancy_must_match_the_successful_hosted_overlay(self):
        report={'status':'review_only_not_unreal_validated',
                'building':'Tile_p03_p01_roof_0a73564b5b0ed26a',
                'source_obj_sha256':'5ca906f6b995d50cd956d89c9382856ba464366c23db6b93f0a886dfaec1a57f',
                'source_plan_lf_sha256':c.INPUTS[c.PLAN], 'units':[{}]*7,
                'added_vertices':1704,'added_faces':1278,
                'overlay_sha256':c.TENANCY_OVERLAY_SHA,'combined_sha256':c.TENANCY_COMBINED_SHA}
        c.check_tenancy_report(report,c.TENANCY_OVERLAY_SHA,c.TENANCY_COMBINED_SHA)
        for field,value in (('status','approved'),('added_faces',1279),('units',[{}]*6),
                            ('source_plan_lf_sha256','0'*64),('overlay_sha256','0'*64)):
            changed=dict(report); changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                c.check_tenancy_report(changed,c.TENANCY_OVERLAY_SHA,c.TENANCY_COMBINED_SHA)
        with self.assertRaises(ValueError): c.check_tenancy_report(report,'0'*64,c.TENANCY_COMBINED_SHA)
        with self.assertRaises(ValueError): c.check_tenancy_report(report,c.TENANCY_OVERLAY_SHA,'0'*64)

    def test_local_or_unrelated_context_is_rejected(self):
        with mock.patch.object(c.sys,'platform','win32'),mock.patch.dict(c.os.environ,{},clear=True):
            with self.assertRaises(RuntimeError): c.hosted_context()
        with mock.patch.object(c.sys,'platform','linux'),mock.patch.dict(c.os.environ,{'GITHUB_ACTIONS':'true'},clear=True):
            with self.assertRaises(RuntimeError): c.hosted_context()

    def test_hosted_context_requires_exact_checked_out_commit(self):
        sha='a'*40
        env={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
             'GITHUB_REPOSITORY':c.REPO,'GITHUB_REF':'refs/heads/main',
             'GITHUB_WORKFLOW_REF':f'{c.REPO}/{c.WORKFLOW}@refs/heads/main',
             'GITHUB_SHA':sha,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1',
             'GITHUB_WORKSPACE':str(c.ROOT),'RUNNER_TEMP':str(c.ROOT.parent)}
        with mock.patch.object(c.sys,'platform','linux'),mock.patch.dict(c.os.environ,env,clear=True), \
             mock.patch.object(c.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=(sha+'\n').encode())):
            root,scratch=c.hosted_context(); self.assertEqual(root,c.ROOT)
            self.assertTrue(scratch.name.endswith('123-1'))
        with mock.patch.object(c.sys,'platform','linux'),mock.patch.dict(c.os.environ,env,clear=True), \
             mock.patch.object(c.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=('b'*40+'\n').encode())):
            with self.assertRaisesRegex(RuntimeError,'checkout does not match'): c.hosted_context()


if __name__=='__main__': unittest.main()
