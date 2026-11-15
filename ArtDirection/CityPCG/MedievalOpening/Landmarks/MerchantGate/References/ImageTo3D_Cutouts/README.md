# Merchant Gate image-to-3D cutouts

These are reference images for a possible image-to-3D trial. They are not 3D
meshes, Unreal assets, or gameplay content. The original reference was
preserved, and the built-in `image_gen` tool performed both edits without
local GPU, Blender, or Unreal use. Since this was a generative edit, exact
pixel-for-pixel preservation of the original building is not established.

| Image | SHA-256 |
| --- | --- |
| Original `../merchant_gate_imagegen_v1.png` | `0e5d8a11fc11a94537d44cf8c370940cb88782e4e86312a5ffde6f98811b324c` |
| [Square v1](merchant_gate_cutout_square_v1.png), edited from original | `5c6e0f37de8e85856308d8b1379b4dcd2ef1a2257e91f1cc38c76c04c5135c06` |
| [Square v2](merchant_gate_cutout_square_v2.png), edited from square v1 | `d9cbdd4f222dd2a8a62693d274ee5c4dc618e20365e16b1176ec7ff044275ca9` |

Both PNGs are 1254 x 1254 RGBA. In v2 the visible gate at alpha >= 128 spans
about 81.8% of the canvas width, the sampled arch opening is alpha 0, and the
dark ceiling and visible interior wall remain. A total of 1,474 low-opacity
pixels (alpha 1–31) outside the main silhouette expand its alpha > 0 bounds
to 92.9% of the canvas width. The pinned TripoSR foreground resizer uses
alpha > 0; with its 0.85 ratio the visibly opaque building would occupy
approximately 75% of the preprocessed square. The cutout has minor colored
edge artifacts. Square v1's near-opaque building spans about 96.8% of its
canvas.
The existing guarded inference runner is pinned to the original reference and
needs a separately reviewed input configuration to use either cutout.

A 15 November 2026 trial sent square v2 to a public community TripoSR Space
with additional background removal disabled and mesh resolution 256. The
result was warped and fragmented, with missing lower walls and pale slab-like
surfaces; it is not suitable for the game. The raw vertex-colored GLB remains
only in this workstation's `Saved/CityPCG` for review. Its SHA-256 is
`cf375e5893f49b38d4b2fe90d289fdadfd6969d25ec0382b568b0124d186ec0e`.
The trial does not validate the opening, collision, materials or Unreal import.

## Prompt 1 — original to square v1

> Use case: background-extraction. Input image: the exact building to cut out, not a style reference. Create a genuinely transparent-alpha PNG on a SQUARE 1:1 canvas suitable for image-to-3D. Center the entire building and preserve its original proportions and perspective with NO stretching; the building should occupy approximately 80–85% of the square canvas width, with transparent padding on all sides. Remove only the gray studio background and detached cobblestone street or paving, including paving visible through the rear opening. The empty view beyond the arched passage must be genuinely transparent. Preserve the stone piers, attached footings, both interior arch side walls and dark timber passage ceiling, roof, chimneys, timber framing, shutters, leaded windows, and every detail of the original facade. Do not redesign, crop, relight, recolor, redraw, add architecture, insert props, or invent ground. Match the original building pixel appearance as closely as possible. No shadow, text or background.

## Prompt 2 — square v1 to selected square v2

> Use case: background-extraction. This is a precise framing edit to the provided transparent building cutout for image-to-3D, not a redesign. KEEP THE CANVAS SQUARE. Uniformly shrink the entire intact building to exactly 82% of the square canvas width, centered horizontally and vertically. Its leftmost solid edge must be at 9% of the canvas width and its rightmost solid edge at 91%, leaving at least a 9%-wide truly transparent margin on BOTH sides. Leave generous transparent margin above and below. Preserve the original aspect ratio, perspective, silhouette, colors, details, stone footings, both interior arch walls and overhead timber ceiling. Keep the empty view through the arch genuinely transparent, as well as all background and margins. Do not stretch, crop, redraw, redesign, recolor, add or erase any building features. No new ground, shadows, props, text, or background. Output actual transparency.
