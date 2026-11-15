"""Exercise complete-roof profile constraints without Blender or file output."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

from whole_building_ridge_variation import vary_ridges
import whole_building_roof_review_hosted as hosted


ROOT=Path(__file__).resolve().parents[2]
FOLLOW=ROOT/'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115'


class RidgeVariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real roof-profile function with inert Blender API stubs, no mesh.
        import preflight_north_market_details as preflight
        with mock.patch.dict(sys.modules,{'whole_building_ridge_variation':None}):
            cls.generator=preflight.load_generator()

    def test_all_four_surveyed_roof_profiles(self):
        seen=set()
        manifest=json.loads((ROOT/'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/'
                             'NorthMarketDetailedObj/detailed_obj_manifest.json').read_text())
        for side in ('east','west'):
            plan=json.loads((FOLLOW/f'north_market_{side}_plan_20261115.json').read_text())
            overrides=json.loads((FOLLOW/'north_market_east_style_override_20261115.json').read_text())['styles'] if side=='east' else {}
            self.assertFalse(plan['party_walls'])
            for building in plan['buildings']:
                before=self.generator.roof_profile(building['footprint_local_m'],building,
                                                   plan['styles'][building['id']])
                row=manifest['buildings'][building['id']]
                style=self.generator.styles_for(building,plan['styles'][building['id']],set(),overrides.get(building['id']))
                self.assertEqual(style.name,row['style'])
                self.assertTrue(all(abs(a-b)<2e-5 for p,q in zip(before,row['roof_profile_local_y_z_m'])
                                    for a,b in zip(p,q)))
                original=deepcopy(before)
                first=vary_ridges(before,building['id'],building['source_max_height_m'])
                self.assertEqual(first,vary_ridges(before,building['id'],building['source_max_height_m']))
                self.assertEqual(before,original)
                self.assertTrue(all(first[i]==tuple(before[i]) for i in range(0,len(first),2)))
                self.assertTrue(all(first[i][1]==before[i][1] for i in range(1,len(first),2)))
                self.assertTrue(all(first[i-1][0]<first[i][0]<first[i+1][0]
                                    for i in range(1,len(first),2)))
                self.assertTrue(all(abs(first[i][0]-before[i][0])>.25 for i in range(1,len(first),2)))
                self.assertLessEqual(max(z for _,z in first)+.089,building['source_max_height_m'])
                seen.add(building['id'])
        self.assertEqual(len(seen),4)

    def test_party_walls_are_rejected(self):
        profile=[(0,4),(4,7),(8,4)]
        with self.assertRaises(ValueError): vary_ridges(profile,'plot-a',10,{1})

    def test_report_pair_rejects_footprint_or_ridge_changes(self):
        bid='plot-a'; profile=[(0,4),(4,7),(8,4)]
        plan={'source_tile':'tile-a','buildings':[{'id':bid,'source_max_height_m':10,
              'origin_m':[0,0,0],'rotation_yaw_deg':0,
              'footprint_local_m':[[0,0],[1,0],[0,1]],'entry':{'edge':0}}]}
        row={'world_pivot_m':[0,0,0],'yaw_deg':0,'axis_x_world_xy':[1,0],
             'axis_y_world_xy':[0,1],'footprint_local_m':[[0,0],[1,0],[0,1]],
             'entry':{'edge':0},'party_wall_edges':[],'collision':False,'style':'Workshop','source_height_cm':1000,
             'roof_profile_local_y_z_m':profile}
        before={'source_tile':'tile-a','buildings':{bid:deepcopy(row)}}
        after=deepcopy(before); after['roof_variation']='asymmetric-ridges-v1'
        after['buildings'][bid]['roof_profile_local_y_z_m']=vary_ridges(profile,bid,10)
        source_manifest={'buildings':{bid:{'style':'Workshop','roof_profile_local_y_z_m':profile}}}
        self.assertEqual(hosted.report_pair(before,after,plan,source_manifest),{bid})
        wrong=deepcopy(after); wrong['buildings'][bid]['footprint_local_m'][0][0]=.1
        with self.assertRaises(ValueError): hosted.report_pair(before,wrong,plan,source_manifest)
        wrong=deepcopy(after); wrong['buildings'][bid]['roof_profile_local_y_z_m'][1]=(1.,7.)
        with self.assertRaises(ValueError): hosted.report_pair(before,wrong,plan,source_manifest)
        wrong=deepcopy(source_manifest); wrong['buildings'][bid]['style']='TradingRange'
        with self.assertRaises(ValueError): hosted.report_pair(before,after,plan,wrong)
        wrong=deepcopy(source_manifest); wrong['buildings'][bid]['roof_profile_local_y_z_m'][1]=(3.,7.)
        with self.assertRaises(ValueError): hosted.report_pair(before,after,plan,wrong)

    def test_text_hashing_accepts_only_lf_or_crlf(self):
        self.assertEqual(hosted.canonical(b'one\r\ntwo\n'),b'one\ntwo\n')
        with self.assertRaises(ValueError): hosted.canonical(b'one\rtwo')

    def test_fbx_must_contain_reported_ridge_vertices(self):
        material=SimpleNamespace(name='M_GLMedieval_ClayTile')
        polygon=SimpleNamespace(material_index=0,normal=SimpleNamespace(z=.8),vertices=[0])
        obj=SimpleNamespace(data=SimpleNamespace(vertices=[SimpleNamespace(co=SimpleNamespace(y=4,z=7.089))],
                                                materials=[material],polygons=[polygon]))
        self.assertEqual(hosted.roof_vertex_evidence(obj,[(0,4),(4,7),(8,4)]),[1])
        with self.assertRaises(ValueError):
            hosted.roof_vertex_evidence(obj,[(0,4),(3,7),(8,4)])
        material.name='M_GLMedieval_Oak'
        with self.assertRaises(ValueError):
            hosted.roof_vertex_evidence(obj,[(0,4),(4,7),(8,4)])
        material.name='M_GLMedieval_ClayTile'; polygon.normal.z=1
        with self.assertRaises(ValueError):
            hosted.roof_vertex_evidence(obj,[(0,4),(4,7),(8,4)])

    def test_fresh_fbx_channel_mismatch_is_rejected(self):
        expected={'bounds_cm':[[0,0,0],[100,100,100]],'materials':['Oak'],
                  'uv_layers':['UV0'],'triangles':12,
                  'pre_export_channels':{'vertices':8,'edges':12,'polygons':6,'color_attributes':0}}
        hosted.check_reimport_facts(expected,deepcopy(expected))
        changed=deepcopy(expected); changed['pre_export_channels']['vertices']=9
        with self.assertRaises(ValueError): hosted.check_reimport_facts(expected,changed)
        changed=deepcopy(expected); changed['materials']=['Wrong']
        with self.assertRaises(ValueError): hosted.check_reimport_facts(expected,changed)

    def test_packed_fbx_texture_hash_is_checked(self):
        data=b'\x89PNG\r\n\x1a\nreview-source'
        image=SimpleNamespace(packed_file=SimpleNamespace(size=len(data),data=data))
        node=SimpleNamespace(type='TEX_IMAGE',image=image)
        color_link=SimpleNamespace(from_node=node,from_socket=SimpleNamespace(name='Color'))
        shader=SimpleNamespace(type='BSDF_PRINCIPLED',inputs={'Base Color':SimpleNamespace(links=[color_link])})
        output=SimpleNamespace(type='OUTPUT_MATERIAL',is_active_output=True,
                               inputs={'Surface':SimpleNamespace(links=[SimpleNamespace(from_node=shader)])})
        mat=SimpleNamespace(name='M_GLMedieval_ClayTile',use_nodes=True,
                            node_tree=SimpleNamespace(nodes=[node,output]))
        obj=SimpleNamespace(data=SimpleNamespace(materials=[mat]))
        textures={'ClayTile':{'sha256':hashlib.sha256(data).hexdigest()}}
        self.assertEqual(hosted.check_fbx_textures(None,obj,textures,ROOT)['ClayTile']['storage'],'packed')
        shader.inputs['Base Color'].links=[]
        with self.assertRaises(ValueError): hosted.check_fbx_textures(None,obj,textures,ROOT)
        shader.inputs['Base Color'].links=[color_link]
        image.packed_file.data=data+b'changed'; image.packed_file.size=len(image.packed_file.data)
        with self.assertRaises(ValueError): hosted.check_fbx_textures(None,obj,textures,ROOT)

    def test_nonfinite_uv_is_rejected_above_comparison_cutoff(self):
        class Point(tuple):
            @property
            def z(self): return self[2]
        class Layers(list): pass
        lower=[Point((0,0,1)),Point((1,0,1)),Point((0,1,1))]
        upper=[Point((0,0,5)),Point((1,0,5)),Point((0,1,5))]
        uv=[SimpleNamespace(uv=(0.,0.)) for _ in range(6)]
        uv[4]=SimpleNamespace(uv=(float('nan'),0.))
        layers=Layers([object()]); layers.active=SimpleNamespace(data=uv)
        mesh=SimpleNamespace(uv_layers=layers,vertices=[SimpleNamespace(co=v) for v in lower+upper],
            loops=[SimpleNamespace(vertex_index=i) for i in range(6)],materials=[SimpleNamespace(name='Oak')],
            polygons=[SimpleNamespace(loop_indices=[0,1,2],material_index=0),
                      SimpleNamespace(loop_indices=[3,4,5],material_index=0)])
        with self.assertRaises(ValueError): hosted.lower_signature(SimpleNamespace(data=mesh),4.)

    def test_malformed_or_unsupported_ranges_are_rejected(self):
        cases=([(0,4),(1,7),(2,4)],[(0,4),(3,7),(8,4)],[(0,4),(4,7),(8,5)],
               [(0,4),(4,5),(8,4)],[(0,4),(4,math.nan),(8,4)],[(0,4),(4,12),(8,4)])
        for profile in cases:
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                vary_ridges(profile,'plot-a',10)

    def test_full_generator_shares_one_changed_profile_without_changing_default(self):
        # This imports the real generator with inert Blender API stubs. Only
        # the construction sinks are mocked, so no mesh or editor is started.
        generator=self.generator
        outline=[(0.,0.),(8.,0.),(8.,8.),(0.,8.)]
        profile=[(0.,4.),(4.,7.),(8.,4.)]
        record={'origin_m':[0,0,0],'entry':{'edge':0}}
        planned={'id':'surveyed-plot','origin_m':[0,0,0],'footprint_local_m':outline,
                 'rotation_yaw_deg':0,'source_max_height_m':10,
                 'entry':{'edge':0,'center_local_xy_m':[4,0],
                          'recessed_closed_opening_width_height_m':[1.35,2.3]}}
        sinks=('shell','tiled_roof','dress_gables','entrance_wall','elevation',
               'move_elevation','add_chimneys','verify_envelope')
        with mock.patch.object(generator,'local_frame',return_value=(outline,(1,0),(0,1))), \
             mock.patch.object(generator,'styles_for',return_value=SimpleNamespace()), \
             mock.patch.object(generator,'inset',side_effect=lambda points,*args:points), \
             mock.patch.object(generator,'roof_profile',return_value=profile), \
             mock.patch.object(generator,'Bay',return_value=object()), \
             mock.patch.multiple(generator,**{name:mock.DEFAULT for name in sinks}) as calls:
            calls['add_chimneys'].return_value=[]
            # Existing default callers need not stage the opt-in helper.
            with mock.patch.dict(sys.modules,{'whole_building_ridge_variation':None}):
                default=generator.from_plan(record,planned,{},set())
            self.assertEqual(default[2],profile)
            varied=generator.from_plan(record,planned,{},set(),roof_variation='asymmetric-ridges-v1')
            self.assertEqual(varied[2],vary_ridges(profile,planned['id'],10))
            self.assertNotEqual(varied[2],profile)
            for name,index in (('shell',4),('tiled_roof',2),('dress_gables',2),('add_chimneys',2)):
                self.assertIs(calls[name].call_args.args[index],varied[2],name)


if __name__=='__main__': unittest.main()
