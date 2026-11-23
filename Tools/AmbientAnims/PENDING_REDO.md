# Pending redo pass (on hold)

Kimodo batches are on hold until the orchestrator session clears them (from 2026-11-22 17:44). The six clips below
still fail review after the first redo pass. Their new prompts are **not** in `ambient_catalog.py` yet. For each clip,
replace its catalog entry with the one below (`rev` sets a fresh seed), then run:

    bash Tools/AmbientAnims/redo.sh 0:WeightShift 1:TalkCasual 4:InspectBlade 7:HandOverLoad 9:DanceJig 10:SitDoze
    python Tools/AmbientAnims/run_in_editor.py amb_finish 10

After `redo.sh`, `amb_finish` cancels the last category's leftover generation run and saves what it touched.
Generate always regenerates a whole category, not just the changed clips.

## 01 Idle / WeightShift (FROZEN?: barely moves; rev 1 also held the arms oddly away from the body)

    C('WeightShift', 'A person stands with the arms hanging loosely at the sides and slowly shifts the hips onto the left leg.',
      'A person, arms loose at the sides, slowly shifts the hips across onto the right leg.',
      'A person, arms loose at the sides, slowly shifts the hips back onto the left leg.', jobs=ANY, rev=2),

## 02 Social / TalkCasual (FROZEN?: two passes came out static; TalkAnimated's wide gestures worked)

    C('TalkCasual', 'A person chats with someone in front of them, raising the right hand to chest height, palm up, while speaking.',
      'A person keeps chatting, tapping the right hand into the left palm to make a point.',
      'A person chats, lowers both hands, then lifts the left hand to gesture.', jobs=ANY, rev=2),

## 05 Smithing / InspectBlade (FROZEN?: energy 3, hand 18)

    C('InspectBlade', (0, 'A person raises a sword up in front of the face with both hands and looks along the edge.'),
      (80, 'A person flips the sword over and tilts it from side to side, checking it.'),
      (150, 'A person lowers the sword and runs the left hand along the blade.'),
      (200, 'A person stands relaxed holding the sword down at the side.'), kind='action', props=('sword',),
      jobs=('smith', 'guard', 'customer'), rev=1),

## 08 Hauling / HandOverLoad (FROZEN?: the arms never hold a box)

    C('HandOverLoad', (0, 'A person stands with both forearms raised in front of the stomach, carrying a heavy box.'),
      (90, 'A person extends both arms straight forward at chest height, handing the box over.'),
      (170, 'A person lowers both arms to the sides.'), kind='action', props=('box',),
      jobs=('porter', 'carter'), rev=2),

## 10 Tavern / DanceJig (SLIDE: a planted foot moves at 36 cm/s)

    C('DanceJig', 'A person dances a lively jig on the spot, hopping from one foot to the other and kicking the free foot forward.',
      'A person keeps dancing on the spot, arms swinging, landing each hop in the same place.',
      jobs=('reveller', 'musician'), rev=1),

## 11 Seated / SitDoze (slumps down the seat by the end: seam 17 cm, slide 18)

    C('SitDoze', (0, 'A person sits upright on a bench and the head slowly nods forward as they doze.'),
      (120, 'A person sits upright and jerks the head back up, waking.'),
      (180, 'A person sits upright and the head starts to nod forward again.'), jobs=('guard', 'anyone'), rev=2),
