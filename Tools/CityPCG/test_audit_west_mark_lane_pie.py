"""Lightweight, no-editor regression checks for pilot navigation acceptance."""

import unittest
from unittest import mock
import sys
from types import SimpleNamespace

import audit_west_mark_lane_pie as qa


def fake_unreal(*, building=False):
    return SimpleNamespace(
        GameplayStatics=SimpleNamespace(get_all_actors_of_class=lambda *args: []),
        NavigationData=object,
        NavigationSystemV1=SimpleNamespace(is_navigation_being_built=lambda world: building),
        RuntimeGenerationType=SimpleNamespace(DYNAMIC='Dynamic'),
    )


def road_report(*, navigation=True):
    routes = {}
    for name, points in qa.ROADS_CM.items():
        samples = [{'xy_cm': point, 'nav_cm': [point[0], point[1], 28.] if navigation else None}
                   for point in points]
        routes[name] = {'samples': samples,
                        'nav_path': {'success': True, 'length_cm': 200.} if navigation else None}
    return {'routes': routes}


def baseline(*, navigation=True):
    roads = road_report(navigation=navigation)
    failures = []
    nav = qa.compare_navigation(fake_unreal(), None, roads, None, navigation, failures)
    return {'phase': 'baseline', 'status': qa.result_status(failures, navigation),
            'navigation_required': navigation, 'roads': roads, 'navigation': nav}


class NavigationAcceptanceTests(unittest.TestCase):
    def test_zero_projected_points_and_paths_fail_acceptance(self):
        roads = road_report(navigation=False)
        failures = []
        result = qa.compare_navigation(fake_unreal(), None, roads, None, True, failures)
        self.assertEqual((result['projected'], result['complete_paths']), (0, 0))
        self.assertEqual(qa.result_status(failures, True), 'fail')
        self.assertEqual(sum('No complete navigation path' in item for item in failures), 2)
        self.assertEqual(sum('navigation projection' in item for item in failures), 6)

    def test_complete_routes_pass_and_compare_to_baseline(self):
        old = baseline()
        qa.validate_request('active', old, True)
        failures = []
        nav = qa.compare_navigation(fake_unreal(), None, road_report(), old, True, failures)
        self.assertEqual((nav['projected'], nav['samples'], nav['complete_paths']), (6, 6, 2))
        self.assertEqual(failures, [])
        self.assertEqual(qa.result_status(failures, True), 'pass')

    def test_missing_route_and_rebuilding_navigation_cannot_pass(self):
        roads = road_report()
        roads['routes'].pop(next(iter(roads['routes'])))
        failures = []
        qa.compare_navigation(fake_unreal(building=True), None, roads, None, True, failures)
        self.assertTrue(any('missing a required road route' in item for item in failures))
        self.assertTrue(any('rebuilding' in item for item in failures))
        self.assertEqual(qa.result_status(failures, True), 'fail')

    def test_nonfinite_navigation_evidence_cannot_pass(self):
        roads = road_report()
        route = next(iter(roads['routes'].values()))
        route['samples'][0]['nav_cm'][0] = float('nan')
        route['nav_path']['length_cm'] = float('inf')
        failures = []
        nav = qa.compare_navigation(fake_unreal(), None, roads, None, True, failures)
        self.assertEqual((nav['projected'], nav['complete_paths']), (5, 1))
        self.assertEqual(qa.result_status(failures, True), 'fail')

    def test_diagnostic_opt_out_never_counts_as_accepted_baseline(self):
        old = baseline(navigation=False)
        self.assertEqual(old['status'], 'diagnostic_only')
        qa.validate_request('active', old, False)
        with self.assertRaises(ValueError):
            qa.validate_request('active', old, True)

    def test_active_acceptance_requires_complete_passing_baseline(self):
        with self.assertRaises(ValueError):
            qa.audit('active')  # rejected before importing unreal
        old = baseline()
        old['navigation']['complete_paths'] = 0
        with self.assertRaisesRegex(ValueError, 'complete, settled'):
            qa.validate_request('active', old, True)

    def test_missing_baseline_route_is_not_hidden_by_summary_counts(self):
        old = baseline()
        old['roads']['routes'].pop('north_merchant_street')
        with self.assertRaisesRegex(ValueError, 'complete, settled'):
            qa.validate_request('active', old, True)
        failures = []
        qa.compare_navigation(fake_unreal(), None, road_report(), old, True, failures)
        self.assertTrue(any('baseline is missing complete per-route evidence' in item for item in failures))
        self.assertEqual(qa.result_status(failures, True), 'fail')

    def test_incomplete_or_nonfinite_baseline_route_rejected(self):
        for kind in ('missing_sample', 'bad_point', 'bad_path', 'wrong_xy'):
            old = baseline()
            route = old['roads']['routes']['north_merchant_street']
            if kind == 'missing_sample':
                route['samples'].pop()
            elif kind == 'bad_point':
                route['samples'][0]['nav_cm'][0] = float('nan')
            elif kind == 'bad_path':
                route['nav_path']['length_cm'] = float('inf')
            else:
                route['samples'][0]['xy_cm'] = [0, 0]
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'complete, settled'):
                qa.validate_request('active', old, True)

    def test_cycle_cannot_accept_diagnostic_samples(self):
        first = {'world': 'PIE', 'seconds': 1, 'phase': 'active', 'status': 'pass',
                 'navigation_required': True, 'navigation_observed': True, 'player_capsule_observed': True,
                 'player_clearance_contract_verified': True}
        away = {'world': 'PIE', 'seconds': 2, 'phase': 'away', 'status': 'diagnostic_only',
                'navigation_required': False, 'navigation_observed': False, 'acceptance_scope': 'streaming_only',
                'source': None, 'group': None}
        last = {'world': 'PIE', 'seconds': 3, 'phase': 'active', 'status': 'pass',
                'navigation_required': True, 'navigation_observed': True, 'player_capsule_observed': True,
                'player_clearance_contract_verified': True}
        self.assertFalse(qa.assess_cycle(first, away, last)['pass'])
        away.update(status='pass', navigation_required=True)
        cycle = qa.assess_cycle(first, away, last)
        self.assertTrue(cycle['sample_sequence_consistent'])
        self.assertFalse(cycle['pass'])
        self.assertEqual(cycle['status'], 'pending_same_session_verification')
        self.assertFalse(cycle['same_pie_session_verified'])
        last['navigation_observed'] = False
        self.assertEqual(qa.assess_cycle(first, away, last)['status'], 'fail')
        last['navigation_observed'] = True
        last['player_capsule_observed'] = False
        self.assertEqual(qa.assess_cycle(first, away, last)['status'], 'fail')
        last.update(player_capsule_observed=True, player_clearance_contract_verified=False,
                    status='pending_player_clearance_verification')
        cycle = qa.assess_cycle(first, away, last)
        self.assertEqual(cycle['status'], 'pending_player_clearance_and_same_session')
        self.assertFalse(cycle['pass'])

    def test_away_without_loaded_tile_reports_streaming_scope(self):
        world = SimpleNamespace(get_path_name=lambda: qa.LEVEL + '.GrayLondon_Geodata')
        editor = SimpleNamespace(get_game_world=lambda: world)
        unreal = SimpleNamespace(
            UnrealEditorSubsystem=object, StaticMeshActor=object,
            ReflectionsCityTileReplacement=object, WorldPartitionSubsystem=object,
            get_editor_subsystem=lambda _: editor,
            get_world_subsystem=lambda *_: SimpleNamespace(is_all_streaming_completed=lambda: True),
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=lambda _: [world]),
            GameplayStatics=SimpleNamespace(get_all_actors_of_class=lambda *_: [],
                                           get_player_pawn=lambda *_: None,
                                           get_real_time_seconds=lambda _: 1.),
            Paths=SimpleNamespace(project_dir=lambda: '.'),
        )
        with mock.patch.dict(sys.modules, {'unreal': unreal}), \
             mock.patch.object(qa, 'require_lease'), mock.patch.object(qa, 'checked_plan', return_value=[]):
            result = qa.audit('away')
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['acceptance_scope'], 'streaming_only')
        self.assertFalse(result['navigation_observed'])
        self.assertNotIn('navigation', result)


class FakeCapsule:
    def __init__(self, radius=33., half_height=88., profile='Pawn', static='Block', dynamic='Block',
                 collision='QueryAndPhysics', object_type='Pawn'):
        self.radius, self.half_height, self.profile = radius, half_height, profile
        self.responses = {'WorldStatic': static, 'WorldDynamic': dynamic}
        self.collision, self.object_type, self.owner = collision, object_type, None

    def get_owner(self): return self.owner
    def get_scaled_capsule_radius(self): return self.radius
    def get_scaled_capsule_half_height(self): return self.half_height
    def get_collision_profile_name(self): return self.profile
    def get_collision_enabled(self): return self.collision
    def get_collision_object_type(self): return self.object_type
    def get_collision_response_to_channel(self, channel): return self.responses[channel]


class FakeCharacter:
    def __init__(self, capsule, updated=None):
        self.capsule = capsule
        if capsule:
            capsule.owner = self
        self.movement = SimpleNamespace(get_editor_property=lambda _: capsule if updated is None else updated)

    def get_editor_property(self, name):
        return {'capsule_component': self.capsule, 'character_movement': self.movement}[name]


def fake_capsule_unreal():
    return SimpleNamespace(Character=FakeCharacter, CapsuleComponent=FakeCapsule,
                           CollisionChannel=SimpleNamespace(ECC_WORLD_STATIC='WorldStatic',
                                                            ECC_WORLD_DYNAMIC='WorldDynamic', ECC_PAWN='Pawn'),
                           CollisionEnabled=SimpleNamespace(QUERY_AND_PHYSICS='QueryAndPhysics'),
                           CollisionResponseType=SimpleNamespace(ECR_BLOCK='Block'))


class PlayerCapsuleTests(unittest.TestCase):
    def test_active_acceptance_rejects_missing_or_invalid_player_capsule(self):
        unreal = fake_capsule_unreal()
        for capsule in (None, FakeCapsule(radius=float('nan')), FakeCapsule(radius=50., half_height=40.),
                        FakeCapsule(profile='Custom'), FakeCapsule(static='Ignore'),
                        FakeCapsule(dynamic='Ignore'), FakeCapsule(collision='NoCollision'),
                        FakeCapsule(object_type='WorldDynamic')):
            pawn = FakeCharacter(capsule) if capsule else None
            failures = []
            settings = qa.capsule_settings(unreal, pawn, require_player_capsule=True,
                                           diagnostic_fallback=False, failures=failures)
            with self.subTest(capsule=capsule):
                self.assertFalse(settings['capsule_from_player'])
                self.assertIsNone(settings['capsule_radius_cm'])
                self.assertEqual(settings['capsule_source'], 'not_observed')
                self.assertEqual(qa.result_status(failures, True), 'fail')

    def test_fallback_is_diagnostic_and_real_player_capsule_is_used(self):
        unreal = fake_capsule_unreal()
        failures = []
        settings = qa.capsule_settings(unreal, None, require_player_capsule=False,
                                       diagnostic_fallback=True, failures=failures)
        self.assertEqual((settings['capsule_radius_cm'], settings['capsule_half_height_cm']), (42., 96.))
        self.assertEqual(settings['capsule_source'], 'diagnostic_fallback')
        self.assertEqual(qa.result_status(failures, False), 'diagnostic_only')
        capsule = FakeCapsule()
        pawn = FakeCharacter(capsule)
        settings = qa.capsule_settings(unreal, pawn, require_player_capsule=True,
                                       diagnostic_fallback=False, failures=failures)
        self.assertEqual(settings['capsule_source'], 'character_movement_capsule')
        self.assertEqual((settings['capsule_radius_cm'], settings['capsule_half_height_cm']), (33., 88.))
        self.assertFalse(settings['clearance_contract_verified'])
        self.assertEqual(qa.sample_status(failures, True, 'active', settings['clearance_contract_verified']),
                         'pending_player_clearance_verification')
        self.assertEqual(failures, [])

    def test_wrong_pawn_or_movement_component_is_rejected(self):
        unreal = fake_capsule_unreal()
        for pawn in (SimpleNamespace(), FakeCharacter(FakeCapsule(), updated=object())):
            failures = []
            result = qa.capsule_settings(unreal, pawn, require_player_capsule=True,
                                         diagnostic_fallback=False, failures=failures)
            self.assertFalse(result['capsule_from_player'])
            self.assertTrue(failures)

    def test_acceptance_does_not_trace_with_a_fallback(self):
        capsule_trace = mock.Mock(return_value=None)
        unreal = SimpleNamespace(
            Vector=lambda *args: args, CapsuleComponent=object,
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY='Visibility'),
            DrawDebugTrace=SimpleNamespace(NONE='None'),
            SystemLibrary=SimpleNamespace(line_trace_single=lambda *args: None,
                                          capsule_trace_single_by_profile=capsule_trace),
            NavigationSystemV1=SimpleNamespace(project_point_to_navigation=lambda *args: None),
        )
        failures = []
        result = qa.road_report(unreal, None, 'tile', None, failures,
                                require_player_capsule=True, diagnostic_fallback=False)
        self.assertFalse(result['capsule_clearance_observed'])
        self.assertEqual(result['capsule_source'], 'not_observed')
        self.assertTrue(any('requires the Character movement capsule' in item for item in failures))
        capsule_trace.assert_not_called()
        result = qa.road_report(unreal, None, 'tile', None, [], diagnostic_fallback=True)
        self.assertTrue(result['capsule_clearance_observed'])
        self.assertEqual(result['capsule_source'], 'diagnostic_fallback')
        self.assertEqual(capsule_trace.call_count, 4)

    def test_nonfinite_navigation_endpoint_never_reaches_path_query(self):
        path_query = mock.Mock(return_value=('Success', 200.))
        projection = mock.Mock(return_value=SimpleNamespace(x=float('nan'), y=2., z=3.))
        unreal = SimpleNamespace(
            Vector=lambda *args: args, CapsuleComponent=object,
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY='Visibility'),
            DrawDebugTrace=SimpleNamespace(NONE='None'),
            NavigationQueryResult=SimpleNamespace(SUCCESS='Success'),
            SystemLibrary=SimpleNamespace(line_trace_single=lambda *args: None),
            NavigationSystemV1=SimpleNamespace(project_point_to_navigation=projection, get_path_length=path_query),
        )
        report = qa.road_report(unreal, None, 'tile', None, [])
        path_query.assert_not_called()
        self.assertTrue(all(route['nav_path'] is None for route in report['routes'].values()))
        projection.return_value = SimpleNamespace(x=1., y=2., z=3.)
        report = qa.road_report(unreal, None, 'tile', None, [])
        self.assertEqual(path_query.call_count, 2)
        self.assertTrue(all(route['nav_path']['success'] for route in report['routes'].values()))


if __name__ == '__main__':
    unittest.main()
