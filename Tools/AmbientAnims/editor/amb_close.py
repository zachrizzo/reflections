# Close Sequencer if it shows one of the library's sequences (its spawnable would otherwise join PIE).
cur = L.get_current_level_sequence()
if cur is not None and cur.get_path_name().startswith(AC.ROOT):
    L.close_level_sequence()
'closed' if cur is not None else 'none open'
