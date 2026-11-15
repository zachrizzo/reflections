# Red London crowd looks

The project contains 36 separately saved actor Blueprint looks under
`/Game/Characters/RedLondon/Crowd/Variants/BP_Crowd_01` through `BP_Crowd_36`.
They are six existing MetaHuman identities, each with six clothing palettes:
Original, Moss, Ocean, Ochre, Plum, and Ash. Some looks also hide hand-held
props in game. These are 36 combinations, not 36 newly sculpted faces or bodies.

The existing body meshes, faces, hair, and equal-height scaling are retained.
The new clothing material instances preserve the source material graph and its
textures while recoloring selected fabrics. The manifest records each look's
base character, material, and optional props. `verified.json` records a check
of all 36 Blueprint assets, six distinct face meshes, original body/face and
scale assignments, fabric overrides, and prop flags.

`CrowdLooks_QA.png` shows three sample looks. The underlying outfits are early
art prototypes; collars, fit, materials and props still need art review. The
Blueprints are conventional actors, not MetaHuman Crowd Collection instances or
proof that a large crowd can be rendered or simulated. The Crowd Collection,
Mass representation, movement and scaling work must be integrated and tested
separately.
