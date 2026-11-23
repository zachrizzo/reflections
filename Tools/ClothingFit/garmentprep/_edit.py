p = 'Tools/ClothingFit/garmentprep/editor/capture_poses.py'
s = open(p, encoding='utf-8').read()
s = s.replace("unreal.AutomationLibrary.take_high_res_screenshot(820, 940, str(path), delay=.05, force_game_view=True)", "unreal.AutomationLibrary.take_high_res_screenshot(*P.get(\"shot_size\", [820, 940]), str(path), delay=.05, force_game_view=True)")
open(p, 'w', encoding='utf-8').write(s)
