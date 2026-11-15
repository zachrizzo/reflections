"""Small, in-memory checks only; no real mesh, image or temp file is written."""

import io
import math
import unittest
from unittest import mock

import build_merchant_gate_procedural as gate
from audit_merchant_gate import audit_geometry, intersects_clearance


def point_in_xz_triangle(points, x, z):
    """Independent 2-D section check for a wall at a constant Y coordinate."""
    def edge(a,b,p):
        return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    triangle = [(p[0],p[2]) for p in points]
    areas = [edge(a,b,(x,z)) for a,b in zip(triangle,triangle[1:]+triangle[:1])]
    return min(areas) >= -1e-9 or max(areas) <= 1e-9


class GateGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mesh = gate.build_gate('tiny')

    def test_clearance_and_required_solid_bearing(self):
        report = audit_geometry(self.mesh.triangles())
        self.assertEqual(report['status'], 'passed', report['errors'])
        self.assertEqual(report['depth_width_height_m'], [7.0,13.0,8.0])
        self.assertEqual(report['obstructing_triangles'], 0)
        self.assertEqual(report['probes']['upper_lumen']['hit_count'], 0)
        for name in ('left_pier','right_pier','above_arch'):
            low, high = report['probes'][name]['longitudinal_hit_bounds_m']
            self.assertGreaterEqual(high-low, 3.8)

    def test_through_passage_audit_detects_an_inserted_wall(self):
        mesh = gate.Mesh()
        mesh.triangle((0,-.6,.3),(0,.6,.3),(0,0,2.3),'Fieldstone')
        report = audit_geometry((*self.mesh.triangles(),*mesh.triangles()))
        self.assertEqual(report['status'],'failed')
        self.assertGreater(report['obstructing_triangles'],0)
        self.assertIn('Geometry obstructs the continuous passage clearance',report['errors'])

    def test_both_roof_end_gables_fill_the_whole_roof_section(self):
        for side in (-1,1):
            plane = side*6.38
            walls = [(points,normal) for role,points,_,normal in self.mesh.faces
                     if role=='WarmPlaster' and all(abs(p[1]-plane)<1e-9 for p in points)
                     and max(p[2] for p in points)>5.700001]
            self.assertTrue(walls, f'No end gable on side {side}')
            self.assertTrue(all(side*normal[1] > .999 for _,normal in walls))
            for i in range(-32,33,4):
                x=i/10
                roof_z=7.40-1.60*abs(x)/3.50
                for fraction in (.001,.25,.50,.75,.999):
                    z=5.70+(roof_z-5.70)*fraction
                    with self.subTest(side=side,x=x,z=z):
                        self.assertTrue(any(point_in_xz_triangle(points,x,z) for points,_ in walls))
                self.assertFalse(any(point_in_xz_triangle(points,x,roof_z+.02) for points,_ in walls))

    def test_side_elevation_details_stay_outside_the_cart_passage(self):
        side_detail=gate.Mesh()
        gate.make_side_elevations(side_detail)
        for side in (-1,1):
            for role in ('Oak','LeadedGlass'):
                self.assertTrue(any(face_role==role and all(side*p[1] >= 6.35 for p in points)
                                    for face_role,points,_,_ in side_detail.faces),
                                f'Missing {role} on side {side}')
        for _,points,_,_ in side_detail.faces:
            self.assertTrue(all(6.35 <= abs(point[1]) <= 6.50 and abs(point[0]) <= 3.5
                                for point in points))
            low=[min(p[i] for p in points) for i in range(3)]
            high=[max(p[i] for p in points) for i in range(3)]
            self.assertFalse(intersects_clearance(points,low,high))

    def test_obj_readback_keeps_materials_uv_normals_and_winding(self):
        stream = io.StringIO()
        gate.write_obj(stream,self.mesh)
        stream.seek(0)
        reread = gate.read_obj(stream)
        gate.verify_faces(reread,self.mesh.faces)
        self.assertEqual({f[0] for f in reread},set(gate.MATERIALS))
        bad = list(reread)
        role, points, uv, normal = bad[0]
        bad[0] = (role,points,((uv[0][0]+.1,uv[0][1]),*uv[1:]),normal)
        with self.assertRaisesRegex(ValueError,'UV'):
            gate.verify_faces(bad,self.mesh.faces)

    def test_roof_uv_repeat_does_not_scale_chimney_bricks(self):
        mesh = gate.Mesh()
        gate.make_roof(mesh,'tiny')
        roof = mesh.faces[0]
        self.assertEqual(roof[0],'ClayTile')
        for point,uv in zip(roof[1],roof[2]):
            self.assertAlmostEqual(uv[0],point[1]/1.984375)
        brick_caps = [face for face in mesh.faces if face[0]=='ClayTile'
                      and all(-1.45 <= p[0] <= -.83 and 4.04 <= p[1] <= 4.66 for p in face[1])
                      and face[3][2] > .99]
        self.assertTrue(brick_caps)
        for point,uv in zip(brick_caps[0][1],brick_caps[0][2]):
            self.assertAlmostEqual(uv[0],point[0])
            self.assertAlmostEqual(uv[1],point[1])

    def test_mtl_references_only_project_textures(self):
        stream = io.StringIO()
        gate.write_mtl(stream)
        text = stream.getvalue()
        self.assertEqual(text.count('newmtl '),len(gate.MATERIALS))
        for role, (_, path, sha) in gate.MATERIALS.items():
            self.assertIn('newmtl M_GLMedieval_'+role+'\n',text)
            if path:
                self.assertIn('map_Kd Textures/'+path.rsplit('/',1)[1]+'\n',text)
                self.assertRegex(sha,r'^[0-9a-f]{64}$')

    def test_checkpoint_can_stop_a_stage(self):
        calls = []
        def check():
            calls.append(None)
            if len(calls) == 2:
                raise RuntimeError('shared machine became busy')
        with self.assertRaisesRegex(RuntimeError,'busy'):
            gate.build_gate('tiny',check)
        self.assertEqual(len(calls),2)

    def test_no_nonfinite_or_degenerate_triangles(self):
        for role, points, uv, normal in self.mesh.faces:
            self.assertTrue(all(math.isfinite(x) for p in (*points,*uv) for x in p))
            self.assertAlmostEqual(sum(x*x for x in normal),1.0)
            self.assertIn(role,gate.MATERIALS)
        with self.assertRaises(ValueError):
            gate.Mesh().triangle((0,0,0),(0,0,0),(1,1,1),'Fieldstone')


class GuardTests(unittest.TestCase):
    def run_guard(self, physical=gate.MIN_PHYSICAL, commit=gate.MIN_COMMIT,
                  processes=None, train='LOADED'):
        if processes is None:
            processes = {'unrealeditor.exe'}
        records = [{'name':name,'pid':index+100,'parent_pid':1}
                   for index,name in enumerate(sorted(processes))]
        with mock.patch.object(gate,'memory_headroom',return_value=(physical,commit)), \
             mock.patch.object(gate.market_guard,'process_snapshot',return_value=records), \
             mock.patch.object(gate,'train_status',return_value=train):
            return gate.light_work_guard()

    def test_permits_only_safe_guard_values(self):
        self.assertEqual(self.run_guard()['physical_bytes'],gate.MIN_PHYSICAL)
        for physical,commit in ((gate.MIN_PHYSICAL-1,gate.MIN_COMMIT),
                                (gate.MIN_PHYSICAL,gate.MIN_COMMIT-1)):
            with self.assertRaisesRegex(RuntimeError,'Need 4/10'):
                self.run_guard(physical=physical,commit=commit)
        with self.assertRaisesRegex(RuntimeError,'not returned'):
            self.run_guard(processes={'other.exe'})
        for process in gate.BLOCKED_PROCESSES | gate.market_guard.COMPILERS:
            with self.assertRaisesRegex(RuntimeError,'build process'):
                self.run_guard(processes={'unrealeditor.exe',process})
        with self.assertRaisesRegex(RuntimeError,'not LOADED'):
            self.run_guard(train='BUILDING')

    def test_latest_train_wins_and_malformed_header_fails_closed(self):
        queue = '!!! TRAIN #24 BUILDING !!!\n!!! TRAIN #23 LOADED !!!'
        self.assertEqual(gate.current_train_status(queue),'BUILDING')
        with self.assertRaisesRegex(RuntimeError,'malformed'):
            gate.current_train_status('!!! TRAIN #24 !!!\n!!! TRAIN #23 LOADED !!!')
        with self.assertRaisesRegex(RuntimeError,'Cannot determine'):
            gate.current_train_status('queue with no train')

    def test_default_full_build_calls_guard_before_constructing_geometry(self):
        with mock.patch.object(gate,'light_work_guard',side_effect=RuntimeError('blocked')):
            with self.assertRaisesRegex(RuntimeError,'blocked'):
                gate.build_gate()

    def test_gigabyte_exception_never_exempts_separate_gcc(self):
        records = [{'name':'UnrealEditor.exe','pid':100,'parent_pid':1},
                   {'name':'GCC.exe','pid':200,'parent_pid':1},
                   {'name':'GBT_DL_LIB.exe','pid':201,'parent_pid':200}]
        identities = {200:{'path':gate.market_guard.GIGABYTE_GCC,'created':10},
                      201:{'path':r'C:\Program Files\GIGABYTE\Control Center\GBT_DL_LIB.exe','created':11}}
        with mock.patch.object(gate.market_guard,'process_snapshot',return_value=records), \
             mock.patch.object(gate.market_guard,'process_identity',side_effect=lambda pid: identities.get(pid)):
            editor, blockers = gate.process_status()
            self.assertTrue(editor)
            self.assertEqual(blockers,[])
            records.append({'name':'gcc.exe','pid':202,'parent_pid':1})
            self.assertEqual(gate.process_status()[1],['gcc.exe (pid 202)'])

    def test_missing_wrong_or_unreadable_gigabyte_identity_stays_blocked(self):
        app = {'name':'gcc.exe','pid':200,'parent_pid':1}
        child = {'name':'GBT_DL_LIB.exe','pid':201,'parent_pid':200}
        child_id = {'path':r'C:\Program Files\GIGABYTE\Control Center\GBT_DL_LIB.exe','created':11}
        identities = [None, {'path':r'C:\compiler\gcc.exe','created':10},
                      {'path':gate.market_guard.GIGABYTE_GCC,'created':12}]
        for app_id in identities:
            with self.subTest(identity=app_id), \
                 mock.patch.object(gate.market_guard,'process_snapshot',return_value=[app,child]), \
                 mock.patch.object(gate.market_guard,'process_identity',side_effect=lambda pid: app_id if pid==200 else child_id):
                self.assertEqual(gate.process_status()[1],['gcc.exe (pid 200)'])
        with mock.patch.object(gate.market_guard,'process_snapshot',return_value=[app,child]), \
             mock.patch.object(gate.market_guard,'process_identity',side_effect=OSError('unreadable')):
            self.assertEqual(gate.process_status()[1],['gcc.exe (pid 200)'])
        with mock.patch.object(gate.market_guard,'process_snapshot',return_value=[app]):
            self.assertEqual(gate.process_status()[1],['gcc.exe (pid 200)'])
        with mock.patch.object(gate.market_guard,'process_snapshot',return_value=[app,child]), \
             mock.patch.object(gate.market_guard,'process_identity',side_effect=lambda pid: {'path':gate.market_guard.GIGABYTE_GCC,'created':10} if pid==200 else None):
            self.assertEqual(gate.process_status()[1],['gcc.exe (pid 200)'])
        with mock.patch.object(gate.market_guard,'process_snapshot',side_effect=OSError('unreadable snapshot')):
            with self.assertRaisesRegex(OSError,'unreadable snapshot'):
                gate.process_status()
        duplicate = [app,dict(app,name='unrealeditor.exe')]
        with mock.patch.object(gate.market_guard,'process_snapshot',return_value=duplicate):
            with self.assertRaisesRegex(RuntimeError,'duplicate'):
                gate.process_status()

    def test_changed_shared_guard_stops_real_work(self):
        with mock.patch.object(gate,'digest',return_value='changed'):
            with self.assertRaisesRegex(RuntimeError,'process guard changed'):
                gate.light_work_guard()


if __name__ == '__main__':
    unittest.main()
