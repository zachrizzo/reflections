# Our actors on Gray London (world-jump, row B, Nov 14 21:11)

Everything world-jump added to `/Game/GrayLondon/Maps/GrayLondon_Geodata` is a **new** World Partition external actor
package. None of Jah's actors or the map file was modified (`git status` shows no `AM`/`D` under GrayLondon; the
.umap is still the 21:00 checkout). To find them in the editor: actor tag `Lanthorne.Overlay`, labels starting `LT_`.

- 1 PlayerStart `LT_PlayerStart_Intro` at (3292.9, 310.9, 1.1) m, Great Tower Street, facing east (towards the Tower),
  not spatially loaded, PlayerStartTag `Lanthorne`. Jah's `Trafalgar Square start` is still there: the engine picks a
  random start among several, so the game mode needs to prefer the `Lanthorne` tag (see below).
- 89 `ReflectionsStoryMarker` actors `LT_Marker_<name>` carrying 164 names (MarkerName plus tags, every name unique),
  Side = Auto (one London), not spatially loaded, traced to the street. Spots: `graylondon_markers.json`.
- Map axes: Unreal X = metres east, Y = metres north of 51.5080 N, 0.1281 W (calibrated on the Tower and Tower Bridge).

## Packages (90)

- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/0/8Z/1ZPQU3UE8EF4TAGXMMMXL0`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/0/BG/LI9ODGJ24KIJM4LPQKP6HE`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/0/E0/HU5P8EO8E7H81VF94CGSTZ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/0/JD/MCSPE6IISZG5BP836ZTOGQ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/0/K9/HIV8PM00372BZOC0UDUVHO`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/1/PU/7WXTBNG07D4XW2QYF0T0LR`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/1/XW/8FB8J5V20R04KZXKAOG7S8`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/2E/XILHAN5YH3HGI8JB7II2PE`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/AM/WB326VA4YFCYTYZSRRPPAN`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/FC/WLURS8SS63XS429C1D6QCC`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/GA/PEJ5862F7M5EPR79VIKA65`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/HV/4QZ9KUEMPBGKV88NVKYV1Y`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/VM/F6IJVQBGLD5EZ21RFHFG1Z`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/2/VN/47S66F97U5K0L089D4S3AF`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/1D/SKZ0GD2MM93UR1PS701KH6`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/7P/FUVGEKC37SDHJKW2MEF1WK`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/B0/675YTV1T1B6QSBB660O145`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/KC/AB2A3BHEQQFOUZUOR5YFQ6`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/NK/1GWKLZCIJSZ7RNK1Z33NBN`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/S2/A2J8GVIAT9BHA3C8VHDQN1`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/U2/ME2ZBQMDLL8M1XY4RHAHVZ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/U9/8LWD8IKG5HNN0XQV73PEVU`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/3/WT/C7KO066KCI5CXUOBQBC3K5`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/4/AJ/SX2F269DNLOC84TIVZAS2I`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/4/K1/6PEZAXHG0QKBXPO4ZK4SGB`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/4/VI/TBVO7WGM7F3JHAVLNJQGTF`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/4/WJ/6IGATQ5UXG9EMC8LV8L7MR`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/5/M4/2MVAJ8KZ9RSGV8AAPR0UOR`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/5/OR/RAI46D6OM0V6OG9OPKZUH2`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/1G/AC3ENA7TTYBXL2UKIK6JLA`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/5C/LQMTD8VFJZHU0EE8E09LQC`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/8J/9CBGDN64PTDHK3ZNQT5KDK`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/8M/UEQ01B074ZT1FV4PB2CF1X`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/90/J0B0LWM5YVA20M2UYTBCKT`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/NW/HCS8NO9NGUIM92CATL0ZLF`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/QM/GT8FZ8GK5XG50SAY04PUL1`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/R2/JXZYG56JHRE32RI0IU2N3D`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/6/RC/U02DDU3L0TTJB2NN14846T`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/7U/L1GCDGLHFGJSO612O6MJDV`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/F4/VHOOT4DEIJGQLTFM58DBHL`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/FX/A42XDWWRUG6VITSL2CR4X4`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/7/OT/IE1926647W9TEXSXCT4J6L`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/1U/GPP26V6EADJZWM0F5RGG4B`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/54/G7XP2K3LVB2YVOMX6ASJ1Z`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/DE/DFGJSLDBELJ55K3UKVG13L`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/IO/8Z9K0Q8OERK10A27PQCB3O`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/S2/FIU3UEAICIX7OXO528UHT4`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/SZ/SEWKF7YKHSEHLBDWAX22NB`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/8/YR/3PD85Q68JGYX2BHG05I2DF`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/2C/BKXJNG9QZBMBZ1LXZV8RHT`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/41/UJLG01AGLSZKD5LWBH1CDJ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/7S/P2MSGDZBGCXVFNH5MGY2AR`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/BQ/WOAAHAQTHPOHYIU0WI5GSH`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/NW/4FAZWBBGDKKS1QNCC208S7`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/UQ/8030XK1VO6GFX7AM47CSIA`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/X1/E8WNVRSGFAMQV662STIAN5`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/9/X7/D2NUHKY0IVKCMZJQAPGLA6`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/A/2U/SNADCUOIC0VRHWKA39YWEC`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/A/L2/XVH7B6CXSVRGI5QHM1FWWZ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/A/SG/V2L6VQ4Q38Z5K907SH743A`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/A/VT/E022OH3Q5AIIL3NWCGBXIY`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/A/VT/F8UJOF8W0O7X5WU0R3DDG5`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/B/CF/IK564XC74XG3VM3IV4P5HG`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/B/Q7/A2ZELKI8EPF5PWMPHE59CV`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/B/V3/ABD8W9OJ3QTJY0SMA08M6T`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/13/OYBIK1A5MSJ0Q5SWEJBEQK`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/1X/F95MMHFEL2KXVNBNAAY1NN`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/5Y/0SIEV3WLZ9NBUGDE2YCIUM`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/97/QL39T2XTGXF3BEC6BM87X2`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/FP/8I0G323LE4A3BUQEC4KY5G`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/IC/469DVR7B48MXSQGNOB247J`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/KJ/4EQA1H8SL1YTXGEYZQ9664`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/KP/E745Q36VHCKYMGT1MKECZR`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/PR/4UETZFCJAD821ZBJD5P4OQ`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/RQ/9PPH290M64SBSVQZ146WMN`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/C/YK/385UH0NX7ZQH5AELUSM3CB`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/D/A3/UHUR3VWVZM21QX2Y7TWSXU`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/D/AT/FL86Z5X2D5YXXL048X9C6N`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/D/S3/VZ4RBK154DPTKD4U1MZBIY`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/33/77NHIRAN1O9624JHJTNMQ9`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/JK/B5WNKV0E2DY5JCHRHMLOVS`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/KA/N5KXBA8L7RBIF2OG8YEO88`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/L1/1Q31LCJTJSCD45EVFEENON`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/LJ/FYVJ0SVASOCIJF2A0FRM4D`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/QO/I20BPJ6V2BHGCWURDGRRS5`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/TW/YQ884NXD4DG9H4CQ4KC3T7`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/V9/54QG2FVTW9YATIV2UGECXE`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/E/ZK/52UA8VNN0FTLAIKGM9RPBC`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/F/34/W8WHW5RNK27C3XZ7F1FBHP`
- `/Game/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/F/4M/8TZ2NF3UJT50BBFE6ZXI4U`
