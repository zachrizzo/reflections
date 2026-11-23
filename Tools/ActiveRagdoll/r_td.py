TD = globals().get('TD', 0.35)
unreal.GameplayStatics.set_global_time_dilation(AR.world(), TD)
'time dilation %.2f' % unreal.GameplayStatics.get_global_time_dilation(AR.world())
