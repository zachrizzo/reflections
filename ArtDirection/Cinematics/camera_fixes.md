# Camera fixes on /Game/GrayLondon/Maps/UEDPIE_0_GrayLondon_Geodata.GrayLondon_Geodata

From `test_cutscenes_pie.py geometry`: each camera key placed at the map's anchor, checked for being inside geometry or losing sight of its subject, and pulled toward the subject until clear. Applied in `CAMERA_FIX` (cutscene_defs.py).

| Cutscene | Shot | Key | Was (anchor cm) | Anchor | Fix |
|---|---|---|---|---|---|
| Intro | 1 Lanthorne at dusk | key 0 | (-6000.0, -4200.0, 4200.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | cannot clear: keep, re-author by hand |
| Intro | 1 Lanthorne at dusk | key 1 | (-4600.0, -3000.0, 3500.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | cannot clear: keep, re-author by hand |
| Intro | 2 Over the rooftops | key 0 | (4200.0, 3600.0, 2600.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | moved to (630, 540, 645) |
| Intro | 2 Over the rooftops | key 1 | (2600.0, 2600.0, 1500.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | moved to (780, 780, 604) |
| Intro | 2 Over the rooftops | key 2 | (1200.0, 1300.0, 700.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | moved to (720, 780, 480) |
| Intro | 8 Behind Wren | key 0 | (-120.0, 240.0, 185.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050665802 | moved to (-99, 229, 183) |
| BurningEyes | 2 The figure | key 0 | (700.0, -260.0, 150.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050671803 | moved to (780, 24, 156) |
| BurningEyes | 2 The figure | key 1 | (690.0, -250.0, 152.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050671803 | moved to (765, 25, 156) |
| BurningEyes | 3 It runs | key 0 | (450.0, -500.0, 160.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050671803 | cannot clear: keep, re-author by hand |
| BurningEyes | 3 It runs | key 1 | (440.0, -520.0, 165.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050671803 | cannot clear: keep, re-author by hand |
| BurningEyes | 4 The conversion, held wide | key 0 | (300.0, -650.0, 260.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050671803 | cannot clear: keep, re-author by hand |
| FirstPage | 3 Rising away | key 0 | (-800.0, -900.0, 1800.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050906841 | moved to (-640, -720, 1460) |
| FirstPage | 3 Rising away | key 1 | (-1400.0, -1600.0, 3200.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050906841 | moved to (-560, -640, 1340) |
| FirstPage | 4 Behind Wren, out at the city | key 0 | (-130.0, 220.0, 180.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2050906841 | moved to (-104, 209, 178) |
| Ending | 3 The city warms | key 0 | (-2000.0, -1800.0, 2600.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2051061865 | moved to (-1200, -1440, 2080) |
| Ending | 3 The city warms | key 1 | (-1700.0, -1500.0, 2300.0) | ReflectionsStoryMarker_UAID_10FFE0B80A24E81403_2051061865 | moved to (-1145, -1275, 1955) |
