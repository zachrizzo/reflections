"""Cutscene definitions for build_cutscene.py (cameras, cast, lines) and kimodo_takes.py (body takes).
Source script: ArtDirection/Story/cutscenes.md (story session). Positions are in ANCHOR SPACE (cm): X = anchor forward
(Wren's facing when there is no marker), Y = right, Z = up from the anchor's feet. Wren's eyes are about 168 cm up.

Shot:   {'label', 'start', 'end', 'focal' (mm), 'aperture' (f-stop), 'focus' (cm, omit = no depth of field),
         'keys': [{'t', 'pos': (x, y, z), 'look': (x, y, z) or 'rot': (roll, pitch, yaw)}]}
Cast:   {'role', 'hero', 'tag', 'mark': (x, y, z, yaw), 'place', 'restore', 'hidden', 'nearest' (+ 'radius',
         'prefer_infected'), 'infect', 'stand_in_archetype', 'stand_in' (look class), 'keep'}
Takes:  {'id', 'role', 't', 'frames', 'prompt', 'seed', 'anim' (an existing clip instead of a Kimodo take),
         'full_body', 'rate', 'loops', 'blend_in', 'blend_out', 'face' (role)}
Lines:  {'id', 't', 'dur' (0 = voice length), 'speaker', 'text', 'role' (3D from that role's head),
         'only_with' / 'only_without' (role found by its tag or not), 'side' (Gray/Red/White)}
Cards:  {'t', 'dur', 'style': title | caption | location, 'text', 'sub', 'side'}
Fades:  {'t', 'dur', 'from', 'to'} (0 clear .. 1 black)
Cues:   {'t', 'cue', 'attacker'/'victim'/'hold_at'/'fallback_take' (villain conversion)}
Lights: {'label', 'pos', 'color', 'intensity' (cd), 'radius', 'start', 'end'}
"""

VO = '/Game/Audio/Jam/Voice/Cues/SCue_VO_'
THEME = ('Lanthorne was cut into three reflections, and only one is the version its maker meant. '
         'The Tarnish wants the final cut.')

WREN, JORY, GOLDIE, PIM, ILSE, TARNISH = 'WREN', 'JORY', 'GOLDIE', 'PIM', 'ILSE', 'THE TARNISH'


def K(t, pos, look=None, rot=None):
    key = {'t': t, 'pos': pos}
    if rot is not None:
        key['rot'] = rot
    else:
        key['look'] = look
    return key


def S(label, start, end, focal, keys, aperture=8.0, focus=None):
    shot = {'label': label, 'start': start, 'end': end, 'focal': focal, 'aperture': aperture, 'keys': keys}
    if focus:
        shot['focus'] = focus
    return shot


def T(cutscene, role, t, frames, prompt, seed, **extra):
    take = {'id': 'AS_%s_%s_%02d' % (cutscene, role, int(t)), 'role': role, 't': t, 'frames': frames,
            'prompt': prompt, 'seed': seed}
    take.update(extra)
    return take


def L(line_id, t, speaker, text, role=None, **extra):
    line = {'id': line_id, 't': t, 'speaker': speaker, 'text': text, 'voice': VO + line_id}
    if role:
        line['role'] = role
    line.update(extra)
    return line


HERO = {'role': 'Hero', 'hero': True, 'place': True}

CUTSCENES = {
    # ---- CS01 Lantern Law: new game ------------------------------------------------------------------------
    'Intro': {
        'length': 48.0,
        'hand_off_blend_seconds': 1.4,
        'cast': [
            HERO,
            {'role': 'Jory', 'tag': 'Person_jory_pell', 'person': 'jory_pell', 'mark': (220.0, -160.0, 0.0, 150.0), 'place': True,
             'restore': True, 'stand_in_archetype': 'Civilian'},
            {'role': 'Goldie', 'tag': 'Person_goldie_fairweather', 'person': 'goldie_fairweather', 'mark': (-200.0, 230.0, 0.0, -60.0), 'place': True,
             'restore': True},
        ],
        'shots': [
            S('Lanthorne at dusk', 0.0, 7.0, 24.0, [
                K(0.0, (-6000.0, -4200.0, 4200.0), (1500.0, 800.0, 600.0)),
                K(7.0, (-4600.0, -3000.0, 3500.0), (1500.0, 800.0, 600.0))]),
            S('Over the rooftops', 7.0, 15.0, 28.0, [
                K(7.0, (4200.0, 3600.0, 2600.0), (0.0, 0.0, 300.0)),
                K(11.0, (2600.0, 2600.0, 1500.0), (0.0, 0.0, 220.0)),
                K(15.0, (1200.0, 1300.0, 700.0), (0.0, 0.0, 150.0))]),
            S('Low on the street', 15.0, 21.0, 35.0, [
                K(15.0, (420.0, -60.0, 40.0), (0.0, 0.0, 150.0)),
                K(21.0, (390.0, -20.0, 48.0), (0.0, 0.0, 150.0))]),
            S('Wren, Goldie off left', 21.0, 27.0, 50.0, [
                K(21.0, (180.0, 260.0, 165.0), (0.0, 0.0, 160.0)),
                K(27.0, (170.0, 245.0, 165.0), (0.0, 0.0, 160.0))], aperture=2.8, focus=315.0),
            S('Over Wren onto Jory', 27.0, 33.0, 40.0, [
                K(27.0, (-260.0, -220.0, 170.0), (220.0, -160.0, 150.0)),
                K(33.0, (-240.0, -230.0, 170.0), (220.0, -160.0, 150.0))], aperture=4.0, focus=480.0),
            S('The whisper', 33.0, 40.0, 85.0, [
                K(33.0, (90.0, 40.0, 170.0), (0.0, 0.0, 165.0)),
                K(40.0, (68.0, 30.0, 169.0), (0.0, 0.0, 165.0))], aperture=2.0, focus=88.0),
            # cutscenes.md puts this camera at (260, -180), inside Jory; moved between them, onto his face.
            S('Jory uncertain', 40.0, 44.0, 45.0, [
                K(40.0, (60.0, -40.0, 165.0), (220.0, -160.0, 160.0)),
                K(44.0, (70.0, -50.0, 165.0), (220.0, -160.0, 160.0))], aperture=2.8, focus=190.0),
            S('Behind Wren', 44.0, 48.0, 32.0, [
                K(44.0, (-120.0, 240.0, 185.0), (300.0, 20.0, 150.0)),
                K(48.0, (-330.0, 60.0, 190.0), (600.0, 0.0, 140.0))], aperture=5.6),
        ],
        'takes': [
            T('Intro', 'Jory', 15.0, 180, 'A person stands and plays an invisible fiddle under their chin, bowing with '
              'the right arm in long strokes, swaying from the hips and tapping one foot in rhythm.', 81001),
            T('Intro', 'Hero', 15.0, 150, 'A person stands relaxed with arms folded across the chest, weight on one leg, '
              'nodding slowly along to music and smiling.', 81002),
            T('Intro', 'Hero', 24.0, 90, 'A person unfolds their arms and raises both open hands to shoulder height in a '
              'playful shrug, then lets them drop.', 81003),
            T('Intro', 'Jory', 27.0, 120, 'A person stops playing, throws their head back laughing, then points at '
              'someone in front of them with the bowing hand.', 81004),
            T('Intro', 'Hero', 33.0, 180, 'A person stands still, then turns the head sharply to the right as if they '
              'heard a whisper close to the ear, holds, and slowly turns the whole upper body to look back over the '
              'right shoulder.', 81005),
            T('Intro', 'Jory', 40.0, 90, 'A person lowers both arms slowly and takes a small step back, shoulders '
              'hunched, looking around uneasily.', 81006),
            T('Intro', 'Hero', 41.0, 90, 'A person turns to face someone beside them and points firmly with the right '
              'hand toward a doorway behind them, then lowers the arm.', 81007),
        ],
        'lines': [
            {'id': 'Narrator_Intro', 't': 4.4, 'speaker': '', 'text': '', 'voice': VO + 'Narrator_Intro'},  # 10.6 s (new narrator)
            L('CS01_01', 16.0, JORY, "Ren! They've doubled the curfew bell. Twice a night now.", 'Jory'),
            L('CS01_02', 19.5, WREN, 'Then play twice as loud.', 'Hero'),
            L('CS01_03', 21.5, GOLDIE, "Wren Hale. Your rent's late and your supper's going cold.", 'Goldie'),
            L('CS01_04', 24.5, WREN, 'Put it on my tab, Goldie.', 'Hero'),
            L('CS01_05', 26.5, GOLDIE, 'Sweetling, you ARE my tab.', 'Goldie'),
            L('CS01_06', 34.0, TARNISH, "Silverer. We've been watching you in every window."),
            L('CS01_07', 39.0, JORY, 'Did you hear something just now? Ren?', 'Jory'),
            L('CS01_08', 41.0, WREN, 'Go inside, Jory. Stay by the lamps.', 'Hero'),
        ],
        'cards': [
            {'t': 0.8, 'dur': 3.8, 'style': 'title', 'text': 'REFLECTIONS'},
            {'t': 4.6, 'dur': 10.6, 'style': 'caption', 'text': THEME},  # follows the 10.6 s narrator read
            {'t': 44.0, 'dur': 4.0, 'style': 'location', 'text': 'GILTSIDE', 'sub': 'Lanthorne'},
        ],
        'fades': [{'t': 0.0, 'dur': 2.2, 'from': 1.0, 'to': 0.0}],
        'cues': [{'t': 47.9, 'cue': 'IntroDone'}],
    },

    # ---- CS02 Burning Eyes: Jory is turned --------------------------------------------------------------------
    'BurningEyes': {
        'length': 30.0,
        'cast': [
            HERO,
            # Jory isn't restored: he stays tarnished for the fight. Without him, the nearest clean citizen plays
            # the part and the variant-B lines play.
            {'role': 'Jory', 'tag': 'Person_jory_pell', 'person': 'jory_pell', 'mark': (600.0, 0.0, 0.0, 180.0), 'place': True,
             'nearest': True, 'radius': 4000.0, 'stand_in_archetype': 'Civilian', 'keep': True},
            {'role': 'Tarnished', 'tag': 'CutsceneTarnished', 'mark': (900.0, 450.0, 0.0, -150.0), 'place': True,
             'nearest': True, 'radius': 4000.0, 'prefer_infected': True, 'infect': True,
             'stand_in_archetype': 'Civilian', 'keep': True},
        ],
        'shots': [
            S('Over Wren onto Jory', 0.0, 5.0, 50.0, [
                K(0.0, (-250.0, 180.0, 170.0), (600.0, 0.0, 150.0)),
                K(5.0, (-230.0, 170.0, 170.0), (600.0, 0.0, 150.0))], aperture=2.8, focus=860.0),
            S('The figure', 5.0, 9.0, 70.0, [
                K(5.0, (700.0, -260.0, 150.0), (900.0, 450.0, 165.0)),
                K(9.0, (690.0, -250.0, 152.0), (840.0, 300.0, 160.0))], aperture=2.8, focus=700.0),
            S('It runs', 9.0, 11.0, 35.0, [
                K(9.0, (450.0, -500.0, 160.0), (650.0, 150.0, 120.0)),
                K(11.0, (440.0, -520.0, 165.0), (650.0, 100.0, 110.0))]),
            # Arcs behind Wren around the conversion so both bodies stay in frame wherever the clip lands them.
            S('The conversion, held wide', 11.0, 19.0, 28.0, [
                K(11.0, (300.0, -650.0, 260.0), (650.0, 100.0, 60.0)),
                K(15.0, (-150.0, -20.0, 330.0), (650.0, 50.0, 60.0)),
                K(19.0, (250.0, 600.0, 300.0), (650.0, 0.0, 60.0))]),
            S('Wren', 19.0, 24.0, 85.0, [
                K(19.0, (120.0, 60.0, 165.0), (0.0, 0.0, 160.0)),
                K(24.0, (105.0, 52.0, 166.0), (0.0, 0.0, 160.0))], aperture=2.0, focus=130.0),
            S('Jory gets up wrong', 24.0, 28.0, 50.0, [
                K(24.0, (300.0, 40.0, 150.0), (650.0, 0.0, 165.0)),
                K(28.0, (320.0, 35.0, 152.0), (650.0, 0.0, 165.0))], aperture=2.8, focus=350.0),
            S('Behind Wren, facing Jory', 28.0, 30.0, 35.0, [
                K(28.0, (-200.0, 160.0, 180.0), (600.0, 0.0, 150.0)),
                K(30.0, (-300.0, 70.0, 185.0), (600.0, 0.0, 145.0))], aperture=5.6),
        ],
        'takes': [
            T('BurningEyes', 'Jory', 0.0, 150, 'A person plays an invisible fiddle with big showy bow strokes, then sees '
              'someone ahead, grins and lifts the bow arm in a wave.', 82001),
            T('BurningEyes', 'Tarnished', 5.0, 120, 'A person walks forward slowly and stiffly, head tilted far to one '
              'side, arms hanging limp, feet dragging slightly.', 82002),
            T('BurningEyes', 'Hero', 19.0, 120, 'A person stands frozen with both hands half raised, then slowly lowers '
              'them, clenches the fists and squares the shoulders.', 82003),
            T('BurningEyes', 'Hero', 26.0, 90, 'A person drops into a ready stance, right arm extended forward with the '
              'palm open, left arm drawn back.', 82004),
        ],
        'lines': [
            L('CS02_01', 1.0, JORY, "Ren! Here's one for you. I'm calling it 'Curfew Waltz'.", 'Jory', only_with='Jory'),
            L('CS02_02', 6.5, JORY, 'Evening, friend. Requests? You look like a slow-song sort.', 'Jory', only_with='Jory'),
            L('CS02_03', 9.6, WREN, 'Jory! Get away from it!', 'Hero', only_with='Jory'),
            L('CS02_03B', 9.6, WREN, 'Hey! Get away from them!', 'Hero', only_without='Jory'),
            L('CS02_04', 14.0, TARNISH, 'Shh. Let him hum for us.'),
            L('CS02_05', 25.0, JORY, 'Ren. We know all your songs.', 'Jory', only_with='Jory'),
            L('CS02_05B', 25.0, '', 'We see you, Silverer. We all do.', 'Jory', only_without='Jory'),
            L('CS02_06', 28.5, WREN, "Not him. You don't get him.", 'Hero', only_with='Jory'),
            L('CS02_06B', 28.5, WREN, "Hold on. I'm going to burn it out of you.", 'Hero', only_without='Jory'),
        ],
        'cues': [
            {'t': 9.5, 'cue': 'Convert', 'attacker': 'Tarnished', 'victim': 'Jory', 'hold_at': 18.6,
             'fallback_take': '/Game/Villain/Conversion/AS_Conversion_Victim_Possessed_A'},
            {'t': 29.9, 'cue': 'BurningEyesDone'},
        ],
    },

    # ---- CS03 The First Page ------------------------------------------------------------------------------------
    'FirstPage': {
        'length': 22.0,
        'cast': [HERO],
        'shots': [
            S('Cupped hands', 0.0, 5.0, 60.0, [
                K(0.0, (160.0, -120.0, 150.0), (0.0, 0.0, 120.0)),
                K(5.0, (150.0, -110.0, 152.0), (0.0, 0.0, 125.0))], aperture=2.8, focus=200.0),
            S('He reads', 5.0, 11.0, 100.0, [
                K(5.0, (60.0, 30.0, 175.0), (0.0, 0.0, 140.0)),
                K(11.0, (52.0, 26.0, 176.0), (0.0, 0.0, 145.0))], aperture=2.0, focus=72.0),
            S('Rising away', 11.0, 17.0, 30.0, [
                K(11.0, (-800.0, -900.0, 1800.0), (0.0, 0.0, 100.0)),
                K(17.0, (-1400.0, -1600.0, 3200.0), (0.0, 0.0, 100.0))]),
            S('Behind Wren, out at the city', 17.0, 22.0, 32.0, [
                K(17.0, (-130.0, 220.0, 180.0), (400.0, 0.0, 150.0)),
                K(22.0, (-320.0, 70.0, 190.0), (600.0, 0.0, 140.0))], aperture=5.6),
        ],
        'lights': [{'label': 'Page glow', 'pos': (35.0, 0.0, 115.0), 'color': (0.85, 0.9, 1.0), 'intensity': 25.0,
                    'radius': 250.0, 'start': 0.0, 'end': 17.0}],
        'takes': [
            T('FirstPage', 'Hero', 0.0, 150, 'A person stands holding both hands together in front of the chest, palms up '
              'as if cradling something flat and fragile, head bowed to look at it.', 83001),
            T('FirstPage', 'Hero', 5.0, 180, 'A person stands still, head bowed over the cupped hands, then slowly tilts '
              'the hands toward the face as if reading words on them, and takes a deep breath.', 83002),
            T('FirstPage', 'Hero', 17.0, 120, 'A person lowers the cupped hands to the waist, lifts the head and looks out '
              'into the distance, shoulders rising with one slow breath.', 83003),
        ],
        'lines': [
            L('CS03_01', 5.5, WREN, "'I cut it in three, so no one dark could hold it all.'", 'Hero', side='Gray'),
            L('CS03_01G', 5.5, WREN, "'Let each side believe it is the true one. Pride makes a good lock.'", 'Hero', side='Red'),
            L('CS03_01F', 5.5, WREN, "'The city I meant is the one they make together. Finish it.'", 'Hero', side='White'),
            L('CS03_02', 10.0, WREN, "One leaf. Still warm from somebody's hand.", 'Hero'),
            L('CS03_03', 15.0, TARNISH, 'You moved a page, Silverer. We felt it in every face.'),
            L('CS03_04', 19.0, WREN, 'Good. Feel the next one too.', 'Hero'),
        ],
        'cards': [
            {'t': 12.0, 'dur': 4.0, 'style': 'location', 'text': 'PEWTERSIDE', 'sub': 'the Old Weigh-House roof', 'side': 'Gray'},
            {'t': 12.0, 'dur': 4.0, 'style': 'location', 'text': 'GILTSIDE', 'sub': 'the Gilt Tower', 'side': 'Red'},
            {'t': 12.0, 'dur': 4.0, 'style': 'location', 'text': 'FROSTSIDE', 'sub': 'the Frost Tower', 'side': 'White'},
        ],
        'cues': [{'t': 21.9, 'cue': 'FirstPageDone'}],
    },

    # ---- CS04 The Gilt Tower -----------------------------------------------------------------------------------
    'GiltTower': {
        'length': 26.0,
        'cast': [
            HERO,
            {'role': 'Pim', 'tag': 'Person_pim_ashgrove', 'person': 'pim_ashgrove', 'mark': (-150.0, -220.0, 0.0, 40.0), 'place': True, 'restore': True},
        ],
        'shots': [
            S('Light from the door', 0.0, 6.0, 24.0, [
                K(0.0, (-420.0, -60.0, 60.0), (300.0, 0.0, 260.0)),
                K(6.0, (-380.0, -50.0, 70.0), (300.0, 0.0, 260.0))]),
            S("Wren's face in the light", 6.0, 12.0, 50.0, [
                K(6.0, (200.0, -150.0, 165.0), (0.0, 0.0, 160.0)),
                K(12.0, (190.0, -140.0, 166.0), (0.0, 0.0, 160.0))], aperture=2.8, focus=250.0),
            S('Pim hurries up', 12.0, 18.0, 45.0, [
                K(12.0, (-40.0, -360.0, 160.0), (-150.0, -220.0, 150.0)),
                K(18.0, (-30.0, -370.0, 160.0), (-150.0, -220.0, 145.0))], aperture=2.8, focus=180.0),
            S('Two-shot', 18.0, 22.0, 40.0, [
                K(18.0, (60.0, 260.0, 160.0), (-60.0, -120.0, 160.0)),
                K(22.0, (70.0, 250.0, 160.0), (-60.0, -120.0, 160.0))], aperture=4.0, focus=300.0),
            S('Behind Wren, looking up', 22.0, 26.0, 30.0, [
                K(22.0, (-200.0, 120.0, 175.0), (500.0, 0.0, 220.0)),
                K(26.0, (-340.0, 60.0, 190.0), (700.0, 0.0, 200.0))], aperture=5.6),
        ],
        'lights': [{'label': 'Doorway gold', 'pos': (250.0, 0.0, 150.0), 'color': (1.0, 0.72, 0.38), 'intensity': 60.0,
                    'radius': 900.0, 'start': 0.0, 'end': 26.0}],
        'takes': [
            T('GiltTower', 'Hero', 0.0, 150, 'A person stands facing forward and lifts one arm to shield the eyes from a '
              'bright light ahead, then slowly lowers the arm.', 84001),
            T('GiltTower', 'Pim', 12.0, 120, 'A person jogs a few steps forward and stops, bending over with hands on '
              'knees to catch their breath, then straightens up quickly.', 84002),
            T('GiltTower', 'Pim', 15.0, 90, 'A person bows quickly from the waist, then clasps both hands together in '
              'front of the chest, nervously.', 84003),
            T('GiltTower', 'Hero', 18.0, 120, 'A person turns to the left, reaches out and rests a hand on the shoulder '
              'of someone shorter, and nods once.', 84004),
            T('GiltTower', 'Hero', 22.0, 90, 'A person turns back to face forward, tilts the head back to look up at '
              'something very high, and rolls the shoulders.', 84005),
        ],
        'lines': [
            L('CS04_01', 6.5, WREN, 'Sealed since the first night of the war. Not any more.', 'Hero'),
            L('CS04_02', 13.0, PIM, 'If you please, Silverer, may I come up? No. Quite right.', 'Pim'),
            L('CS04_03', 17.0, PIM, "I'll mind the door. Properly. Nobody gets past me.", 'Pim'),
            L('CS04_04', 19.0, WREN, "When I'm done, Pim, you ring every bell in this tower.", 'Hero'),
            L('CS04_05', 23.0, TARNISH, "Up you go, Silverer. We'll be waiting at the top."),
        ],
        'cues': [{'t': 25.9, 'cue': 'GiltTowerDone'}],
    },

    # ---- CS05 The Mirror Is Whole: hands the finale to the villain session ------------------------------------
    'MirrorWhole': {
        'length': 24.0,
        'cast': [HERO],
        'shots': [
            S('The leaves join', 0.0, 6.0, 70.0, [
                K(0.0, (140.0, 80.0, 140.0), (0.0, 0.0, 130.0)),
                K(3.0, (130.0, -40.0, 145.0), (0.0, 0.0, 132.0)),
                K(6.0, (80.0, -150.0, 150.0), (0.0, 0.0, 135.0))], aperture=2.8, focus=165.0),
            # cutscenes.md asks for 24 m straight down; this scene plays inside the Frost Tower, so it stays under 9 m.
            S('Ring of light, from above', 6.0, 11.0, 18.0, [
                K(6.0, (0.0, 0.0, 900.0), rot=(0.0, -89.9, 0.0)),
                K(11.0, (0.0, 0.0, 820.0), rot=(0.0, -89.9, 35.0))]),
            S('Lit from below', 11.0, 16.0, 100.0, [
                K(11.0, (90.0, 0.0, 168.0), (0.0, 0.0, 165.0)),
                K(16.0, (80.0, 4.0, 168.0), (0.0, 0.0, 165.0))], aperture=1.8, focus=88.0),
            S('The way up', 16.0, 21.0, 24.0, [
                K(16.0, (-250.0, 0.0, 60.0), (600.0, 0.0, 900.0)),
                K(21.0, (-230.0, 20.0, 50.0), (600.0, 0.0, 1000.0))]),
            S('Behind Wren, looking up', 21.0, 24.0, 32.0, [
                K(21.0, (-130.0, 220.0, 185.0), (500.0, 0.0, 300.0)),
                K(24.0, (-330.0, 60.0, 190.0), (700.0, 0.0, 400.0))], aperture=5.6),
        ],
        'lights': [
            {'label': 'Mirror light', 'pos': (35.0, 0.0, 125.0), 'color': (0.9, 0.95, 1.0), 'intensity': 120.0,
             'radius': 700.0, 'start': 0.0, 'end': 16.0},
            {'label': 'Violet at the top', 'pos': (600.0, 0.0, 1100.0), 'color': (0.55, 0.2, 0.9), 'intensity': 400.0,
             'radius': 1500.0, 'start': 16.0, 'end': 24.0},
        ],
        'takes': [
            T('MirrorWhole', 'Hero', 0.0, 180, 'A person stands with both cupped hands held in front of the chest, then '
              'slowly raises them to face height as if lifting something heavy and bright, arms trembling slightly.', 85001),
            T('MirrorWhole', 'Hero', 6.0, 150, 'A person stands with arms spread slightly away from the body, palms open '
              'and facing forward, head tipped back, chest rising in a deep breath.', 85002),
            T('MirrorWhole', 'Hero', 16.0, 120, 'A person lowers the arms, turns the head to look up at something far '
              'above, then takes one deliberate step forward.', 85003),
        ],
        'lines': [
            L('CS05_00', 3.0, WREN, "The mirror's whole. Now it burns.", 'Hero'),
            L('CS05_01', 7.5, TARNISH, 'Three leaves, one mirror. And one Silverer left to look into it.'),
            L('CS05_02', 12.0, WREN, "I've spent nine years not looking. I'm done with that.", 'Hero'),
            L('CS05_03', 17.5, TARNISH, 'Climb, then. She climbed too.'),
            L('CS05_04', 21.5, WREN, "Mum, if you're up there, I'm coming.", 'Hero'),
        ],
        'cards': [{'t': 9.0, 'dur': 4.0, 'style': 'caption', 'text': 'The Mirror Is Whole'}],
        'cues': [{'t': 11.0, 'cue': 'FinaleReady'}, {'t': 23.9, 'cue': 'MirrorWholeDone'}],
    },

    # ---- CS06 Lanthorne Is Itself Again: the villain calls ShowVictory on OnCutsceneFinished(Ending) -----------
    'Ending': {
        'length': 46.0,
        'hand_off_blend_seconds': 0.0,
        'cast': [HERO],
        'shots': [
            S('Ash', 0.0, 7.0, 35.0, [
                K(0.0, (300.0, -200.0, 120.0), (0.0, 0.0, 80.0)),
                K(7.0, (280.0, -185.0, 115.0), (0.0, 0.0, 85.0))], aperture=4.0, focus=360.0),
            S('He gets up', 7.0, 13.0, 85.0, [
                K(7.0, (120.0, 90.0, 110.0), (0.0, 0.0, 110.0)),
                K(13.0, (130.0, 95.0, 150.0), (0.0, 0.0, 150.0))], aperture=2.0, focus=150.0),
            S('The city warms', 13.0, 22.0, 24.0, [
                K(13.0, (-2000.0, -1800.0, 2600.0), (2000.0, 0.0, 0.0)),
                K(22.0, (-1700.0, -1500.0, 2300.0), (2000.0, 0.0, 0.0))]),
            S("Wren's face", 22.0, 32.0, 50.0, [
                K(22.0, (200.0, 0.0, 160.0), (0.0, 0.0, 160.0)),
                K(27.0, (141.0, 141.0, 160.0), (0.0, 0.0, 160.0)),
                K(32.0, (0.0, 220.0, 160.0), (0.0, 0.0, 160.0))], aperture=2.8, focus=205.0),
            S('Speaking to the light', 32.0, 39.0, 40.0, [
                K(32.0, (-150.0, 60.0, 175.0), (800.0, 0.0, 150.0)),
                K(39.0, (-170.0, 70.0, 176.0), (800.0, 0.0, 150.0))], aperture=4.0),
            S('Alone at the top', 39.0, 46.0, 28.0, [
                K(39.0, (-600.0, -400.0, 400.0), (0.0, 0.0, 150.0)),
                K(46.0, (-1500.0, -900.0, 1200.0), (0.0, 0.0, 150.0))]),
        ],
        'takes': [
            T('Ending', 'Hero', 0.0, 210, 'A person kneels on one knee with one hand braced on the ground, head down, '
              'shoulders heaving with heavy breaths.', 86001),
            T('Ending', 'Hero', 7.0, 180, 'A person kneeling on one knee pushes slowly up to standing, wobbles once, '
              'steadies, and looks down at both open hands.', 86002),
            T('Ending', 'Hero', 22.0, 150, 'A person stands with hands at their sides, lifts the chin, then lets out one '
              'tired laugh, the shoulders shaking once.', 86003),
            T('Ending', 'Hero', 32.0, 180, 'A person stands looking into the distance, raises one open hand slowly to '
              'chest height as if saying goodbye to someone far away, holds it, and lowers it.', 86004),
        ],
        'lines': [
            L('CS06_00', 3.0, WREN, "It's gone. Lanthorne is itself again.", 'Hero'),
            L('CS06_01', 14.0, ILSE, "Boy. Can you hear the bells? Pim's ringing all of them."),
            L('CS06_02', 18.0, WREN, 'I hear them. Ilse, which side was the one it meant?', 'Hero'),
            L('CS06_03', 23.0, ILSE, "None of them alone. All three, standing together. That's the city it meant."),
            L('CS06_04', 28.0, ILSE, "And Elin's boy came home. Mm. Plainly enough."),
            L('CS06_05', 34.0, WREN, 'Goodbye, Mum. I looked. It was only me in there.', 'Hero'),
            L('CS06_06', 40.0, JORY, "Ren! This one's called 'Home Before Dawn'!"),
        ],
        'cards': [{'t': 41.0, 'dur': 5.0, 'style': 'caption', 'text': 'Lanthorne is itself again.'}],
        'fades': [{'t': 43.5, 'dur': 2.5, 'from': 0.0, 'to': 1.0}],
        'cues': [{'t': 45.9, 'cue': 'EndingDone'}],
    },
}


# ---- Re-cut to the recorded voices (15:50) ------------------------------------------------------------------------
# The voiced lines run longer than the script's timings, so these scenes' shot boundaries follow the lines now.
# Each entry: shot index -> (start, end); keys inside a shot are rescaled to the new span. Line, card and cue times
# are set to where the voices actually fall (build_cutscene.fit_lines still guards against overlaps).
RECUT = {
    'BurningEyes': {'length': 36.0, 'shots': {5: (24.0, 31.0), 6: (31.0, 36.0)},
                    'cues': {'BurningEyesDone': 35.9}},
    'FirstPage': {'length': 28.5, 'shots': {1: (5.0, 16.6), 2: (16.6, 23.0), 3: (23.0, 28.5)},
                  'lines': {'CS03_02': 11.4, 'CS03_03': 16.8, 'CS03_04': 25.2},
                  'cards_t': 17.4, 'cues': {'FirstPageDone': 28.4}, 'light_end': 23.0},
    'GiltTower': {'length': 35.5, 'shots': {1: (6.0, 12.5), 2: (12.5, 24.0), 3: (24.0, 28.4), 4: (28.4, 35.5)},
                  'lines': {'CS04_02': 13.0, 'CS04_03': 19.7, 'CS04_04': 24.2, 'CS04_05': 28.6},
                  'takes': {('Pim', 15.0): 17.0, ('Hero', 18.0): 24.0, ('Hero', 22.0): 28.4},
                  'cues': {'GiltTowerDone': 35.4}, 'lights': {'Doorway gold': (0.0, 35.5)}},
    'MirrorWhole': {'length': 29.5, 'shots': {1: (6.0, 12.0), 2: (12.0, 19.8), 3: (19.8, 25.0), 4: (25.0, 29.5)},
                    'lines': {'CS05_01': 7.5, 'CS05_02': 15.5, 'CS05_03': 19.9, 'CS05_04': 25.1},
                    'takes': {('Hero', 16.0): 19.8}, 'cues': {'MirrorWholeDone': 29.4},
                    'lights': {'Mirror light': (0.0, 19.8), 'Violet at the top': (19.8, 29.5)}},
}


def _recut():
    for name, cut in RECUT.items():
        defn = CUTSCENES[name]
        defn['length'] = cut['length']
        for index, (start, end) in cut.get('shots', {}).items():
            shot = defn['shots'][index]
            old_start, old_end = shot['start'], shot['end']
            for key in shot['keys']:
                frac = (key['t'] - old_start) / max(old_end - old_start, 0.01)
                key['t'] = start + frac * (end - start)
            shot['start'], shot['end'] = start, end
        for line in defn.get('lines', []):
            if line['id'] in cut.get('lines', {}):
                line['t'] = cut['lines'][line['id']]
        for take in defn.get('takes', []):
            key = (take['role'], take['t'])
            if key in cut.get('takes', {}):
                take['t'] = cut['takes'][key]
        if 'cards_t' in cut:
            for card in defn.get('cards', []):
                card['t'] = cut['cards_t']
        for cue in defn.get('cues', []):
            if cue['cue'] in cut.get('cues', {}):
                cue['t'] = cut['cues'][cue['cue']]
        for light in defn.get('lights', []):
            if light['label'] in cut.get('lights', {}):
                light['start'], light['end'] = cut['lights'][light['label']]
            elif 'light_end' in cut:
                light['end'] = cut['light_end']


_recut()


# ---- Fallback takes: existing project clips (used wherever no Kimodo take exists yet) -----------------------------
# Hero clips are on Wren's MetaHuman body skeleton: they play as upper-body montages on its DefaultSlot, legs from
# locomotion. NPC clips are on the UEFN driver skeleton. The Kimodo hand wave is retargeted once by
# fallback_takes.py into /Game/Cinematics/Takes/Fallback.
SC = '/Game/SpellCrafting/Gestures/'
HC = '/Game/Characters/Hero/Animation/CombatCasts/'
HS = '/Game/Characters/Hero/Animation/SpellCasts/'
FB = '/Game/Cinematics/Takes/Fallback/'
FALLBACK = {
    'AS_Intro_Hero_24': SC + 'AS_Hero_GestureConjure',
    'AS_Intro_Hero_41': SC + 'AS_Hero_GestureLance',
    'AS_Intro_Jory_27': FB + 'AS_Fallback_Wave_UEFN',
    'AS_BurningEyes_Jory_00': FB + 'AS_Fallback_Wave_UEFN',
    'AS_BurningEyes_Hero_19': HC + 'AS_Hero_CombatHealRaise',
    'AS_BurningEyes_Hero_26': HC + 'AS_Hero_CombatAimHold',
    'AS_FirstPage_Hero_00': HS + 'AS_Hero_HealingPulse',
    'AS_FirstPage_Hero_05': HS + 'AS_Hero_GreaterHeal',
    'AS_GiltTower_Hero_00': HS + 'AS_Hero_ArcaneShield',
    'AS_GiltTower_Hero_18': SC + 'AS_Hero_GestureLance',
    'AS_GiltTower_Hero_22': SC + 'AS_Hero_GestureSkyCall',
    'AS_MirrorWhole_Hero_00': HS + 'AS_Hero_GreaterHeal',
    'AS_MirrorWhole_Hero_06': SC + 'AS_Hero_GestureSkyCall',
    'AS_Ending_Hero_07': HS + 'AS_Hero_HealingPulse',
    'AS_Ending_Hero_32': FB + 'AS_Fallback_Wave_Hero',
}
# Loops for short clips that cover a longer beat.
FALLBACK_LOOPS = {'AS_BurningEyes_Hero_26': 3}


# ---- Camera fixes from the geometry check (test_cutscenes_pie.py geometry on GrayLondon_Geodata) -----------------
# {(cutscene, shot index, key index): (x, y, z)} anchor-space camera positions that replace clipping keys.
CAMERA_FIX = {}


def _apply_camera_fixes():
    for (name, shot, key), pos in CAMERA_FIX.items():
        CUTSCENES[name]['shots'][shot]['keys'][key]['pos'] = tuple(float(v) for v in pos)


_apply_camera_fixes()
