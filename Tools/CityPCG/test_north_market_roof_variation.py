"""Small in-memory tests; never launch Blender or emit assets."""
import json
import math
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import north_market_roof_variation as v
import north_market_roof_variation_hosted as hosted
import north_market_tenancies as tenancy


ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'ArtDirection/CityPCG/MedievalOpening'


class VariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ART/'FollowOn20261115/north_market_east_plan_20261115.json').read_text())
        cls.manifest=json.loads((ART/'WholeBuildings/NorthMarketDetailedObj/detailed_obj_manifest.json').read_text())

    def test_real_survey_profiles_and_height_envelopes(self):
        expected={'east_0a73564b':3,'east_31c9ff1a':2}
        seen=set()
        for name,(bid,style) in v.MODELS.items():
            building=next(x for x in self.plan['buildings'] if x['id']==bid)
            row=self.manifest['buildings'][bid]
            mesh,report=v.make_variation(building,row,style)
            self.assertEqual(len(report['dormers']),expected[name])
            self.assertTrue(report['shutters'])
            self.assertEqual(len(report['source_chimneys_m']),row['chimney_count'])
            self.assertTrue(all(0<=p[2]<=building['source_max_height_m'] and
                                tenancy.contains(p[:2],mesh.plot) for p in mesh.vertices))
            self.assertGreater(min(p[2] for p in mesh.vertices),3.1)
            for dormer in report['dormers']:
                rect=dormer['rect_xy_m']
                envelope=dormer['checked_envelope_xy_m']
                component=mesh.vertices[dormer['vertex_start']:dormer['vertex_start']+dormer['vertex_count']]
                self.assertTrue(component)
                self.assertTrue(v.safe_rectangle(envelope,mesh.plot,set()))
                self.assertTrue(all(envelope[0][0]<=p[0]<=envelope[2][0] and
                                    envelope[0][1]<=p[1]<=envelope[2][1] for p in component))
                seen.add(dormer['variant'])
                self.assertAlmostEqual(dormer['roof_bottom_m'][0],
                    v.roof_height(rect[0][1],row['roof_profile_local_y_z_m'])-.035)
                self.assertAlmostEqual(dormer['roof_bottom_m'][1],
                    v.roof_height(rect[2][1],row['roof_profile_local_y_z_m'])-.035)
                self.assertLessEqual(dormer['ridge_m'],building['source_max_height_m']-.1)
                self.assertTrue(v.safe_rectangle(rect,mesh.plot,set()))
            for shutter in report['shutters']:
                self.assertEqual(shutter['edge'],building['entry']['edge'])
                self.assertGreater(shutter['height_m'][0],3.1)
            self.assertEqual(len(mesh.faces),len(mesh.roles))
            self.assertTrue(all(role in v.TILES for role in mesh.roles))
            self.assertTrue(all(math.isfinite(c) for p in mesh.vertices for c in p))
        self.assertEqual(seen,{'tall_gable','shed','offset_gable'})

    def test_caption_is_bounded_and_refuses_oversized_text(self):
        frame=(-.529,.529,-.298,.298)
        position,rectangle=v.fit_caption(frame,(-.01,.70,-.005,.025))
        self.assertTrue(frame[0]<rectangle[0]<rectangle[1]<frame[1])
        self.assertTrue(frame[2]<rectangle[2]<rectangle[3]<frame[3])
        self.assertTrue(all(math.isfinite(x) for x in position))
        with self.assertRaises(ValueError): v.fit_caption(frame,(-.01,1.1,-.005,.025))

    def test_front_and_cheek_timber_faces_point_outwards(self):
        for axis in ('front','cheek'):
            for end in ((2.,3.),(2.,4.)):
                mesh=tenancy.Mesh([(-10,-10),(10,-10),(10,10),(-10,10)],20)
                v.timber(mesh,axis,.5,.7,(1.,3.),end,.1)
                center=tuple(sum(point[i] for point in mesh.vertices)/len(mesh.vertices) for i in range(3))
                self.assertEqual(len(mesh.faces),6)
                for indices in mesh.faces:
                    points=[mesh.vertices[i] for i in indices]
                    normal,_=tenancy.normal_and_uv(points,.8)
                    midpoint=tuple(sum(point[i] for point in points)/len(points) for i in range(3))
                    self.assertGreater(sum(normal[i]*(midpoint[i]-center[i]) for i in range(3)),1e-5)

    def test_actual_slope_and_roof_skin(self):
        profile=[(0.,4.),(2.,6.),(4.,4.)]
        self.assertAlmostEqual(v.roof_height(1.,profile),5.089)
        self.assertAlmostEqual(v.roof_height(3.,profile),5.089)
        with self.assertRaises(ValueError): v.roof_height(-.01,profile)
        with self.assertRaises(ValueError): v.roof_height(1,[(0,4),(0,6),(4,4)])

    def test_concave_footprint_and_party_wall_are_protected(self):
        plot=[(0,0),(5,0),(5,2),(2,2),(2,5),(0,5)]
        crossing=[(.5,1.5),(3,1.5),(3,3),(.5,3)]
        inside=[(.4,.4),(1.6,.4),(1.6,1.6),(.4,1.6)]
        self.assertFalse(v.safe_rectangle(crossing,plot,set()))
        self.assertTrue(v.safe_rectangle(inside,plot,set()))
        self.assertFalse(v.safe_rectangle(inside,plot,{0}))

    def test_party_entry_and_source_chimney_mismatch_fail_closed(self):
        bid,style=v.MODELS['east_0a73564b']
        building=next(x for x in self.plan['buildings'] if x['id']==bid)
        row=self.manifest['buildings'][bid]
        with self.assertRaises(ValueError): v.make_variation(building,row,style,{building['entry']['edge']})
        altered=dict(row,chimney_count=999)
        with self.assertRaises(ValueError): v.make_variation(building,altered,style)

    def test_low_ceiling_rejects_dormer(self):
        mesh=tenancy.Mesh([(0,0),(6,0),(6,6),(0,6)],3)
        with self.assertRaises(ValueError):
            v.dormer(mesh,[(1,1),(2,1),(2,2),(1,2)],[(0,3),(3,4),(6,3)],0)

    def test_local_execution_rejected(self):
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError): hosted.context()

    def test_expected_hosted_context_and_checkout_mismatch(self):
        sha='a'*40
        env={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
             'GITHUB_REPOSITORY':hosted.REPO,'GITHUB_REPOSITORY_ID':'1457160414',
             'GITHUB_REF':'refs/heads/main',
             'GITHUB_WORKFLOW_REF':f'{hosted.REPO}/{hosted.WORKFLOW}@refs/heads/main',
             'GITHUB_SHA':sha,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'42',
             'GITHUB_RUN_ATTEMPT':'1','GITHUB_WORKSPACE':str(hosted.ROOT),
             'RUNNER_TEMP':str(hosted.ROOT.parent)}
        good=SimpleNamespace(returncode=0,stdout=(sha+'\n').encode())
        with mock.patch.object(hosted.sys,'platform','linux'), mock.patch.dict(os.environ,env,clear=True), \
             mock.patch.object(hosted.subprocess,'run',return_value=good) as run, \
             mock.patch.object(hosted.shutil,'disk_usage',return_value=SimpleNamespace(free=3*2**30)), \
             mock.patch('builtins.open',mock.mock_open(read_data='MemAvailable:    2000000 kB\n')):
            self.assertEqual(hosted.context(),hosted.ROOT.parent/'north-market-roof-42-1')
            run.return_value=SimpleNamespace(returncode=0,stdout=('b'*40+'\n').encode())
            with self.assertRaises(RuntimeError): hosted.context()

    def test_baseline_zip_member_rejections(self):
        good=zipfile.ZipInfo('north_market_street_review.blend')
        good.file_size=100; good.compress_type=zipfile.ZIP_DEFLATED
        self.assertIs(hosted.blend_entry([good]),good)
        with self.assertRaises(ValueError): hosted.blend_entry([good,good])
        link=zipfile.ZipInfo('north_market_street_review.blend')
        link.file_size=100; link.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ValueError): hosted.blend_entry([link])
        big=zipfile.ZipInfo('north_market_street_review.blend'); big.file_size=160*2**20+1
        with self.assertRaises(ValueError): hosted.blend_entry([big])
        wrong=zipfile.ZipInfo('../north_market_street_review.blend'); wrong.file_size=100
        with self.assertRaises(ValueError): hosted.blend_entry([wrong])


if __name__=='__main__': unittest.main()
