import asyncio, statistics
unreal.GameplayStatics.set_global_time_dilation(AR.world(), 1.0)
KEYS = {'pcc': 'PhysicsControlComponent/', 'solver': 'FPhysicsSolverAdvanceTask', 'body_anim': 'SKM_MHC_Hero_BodyMesh',
        'endframe': 'STAT_Scene_EndFrame', 'gt_frame': None}
async def sample(n=30):
    acc = {k: [] for k in ['pcc', 'solver', 'body', 'endframe', 'gt', 'world_tick', 'stall']}
    for i in range(n):
        r = await call_tool('PerfToolset.StatsToolset.GetFrameTree', minInclusiveMs=0.0, maxDepth=40, pathFilter='')
        rv = r['returnValue'] if isinstance(r, dict) and 'returnValue' in r else r
        tot = {k: 0.0 for k in acc}
        def walk(nd, under_body=False):
            nm = nd['Name']
            inc = nd['InclusiveMs']
            if nm.startswith('PhysicsControlComponent/'): tot['pcc'] += inc; return
            if nm == 'FPhysicsSolverAdvanceTask': tot['solver'] += inc; return
            if nm.startswith('SkeletalMesh/Game/Characters/Hero/Assembled/Hero/Body/'): tot['body'] += inc; return
            if nm == 'STAT_Scene_EndFrame': tot['endframe'] += inc
            if nm == 'STAT_WorldTickTime': tot['world_tick'] += inc
            if nm == 'STAT_TaskGraph_GameStalls': tot['stall'] += inc
            for c in nd.get('Children', []) or []: walk(c)
        for root in rv:
            if root['Name'] == 'GameThread': tot['gt'] += root['InclusiveMs']
            walk(root)
        for k in acc: acc[k].append(tot[k])
        await asyncio.sleep(0.03)
    return {k: [round(statistics.median(v), 3), round(statistics.mean(v), 3), round(max(v), 3)] for k, v in acc.items()}
MODE = globals().get('MODE', 'stand')
res = {}
if MODE == 'all':
    AR.P['down_max'] = 1000.0; AR.P['down_min'] = 1000.0
    res['stand'] = await sample()
    AR.set_movement(AR.LIMBS, True); await asyncio.sleep(0.3)
    res['all_kinematic'] = await sample()
    AR.enter_stand(); await asyncio.sleep(0.5)
    AR.knockdown('spine_04', AR.mesh_dir(-1.0), 1.0); await asyncio.sleep(4.0)
    res['ragdoll_down(' + AR.S['state'] + ')'] = await sample()
    AR.teardown(destroy=True); await asyncio.sleep(0.5)
    res['no_hero'] = await sample()
if MODE == 'dorm':
    res['stand'] = await sample()
    AR.dormant(True); await asyncio.sleep(0.5)
    res['dormant'] = await sample()
    AR.dormant(False); await asyncio.sleep(0.5)
    res['stand_again'] = await sample(15)
json.dumps(res)
