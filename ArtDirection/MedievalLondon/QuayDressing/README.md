# Gray London quay dressing

An original loaded timber handcart and separate ground cargo for medieval warehouse entrances and wharf staging areas. The cart load uses oak, flax and hemp from the opening market palette. The GLBs are static visual props, with no authored collision or gameplay behavior.

| Asset | Dimensions (m) | Practical staging space (m) | Use |
| --- | --- | --- | --- |
| `SM_GL1450_QuayHandcart` | 2.73 × 1.61 × 1.35 | 3.00 × 1.80 | Run the long axis along the frontage. The handles extend 1.80 m in +X from the axle pivot. |
| `SM_GL1450_QuayCargo` | 1.09 × 0.93 × 0.69 | 1.25 × 1.05 | Tuck into a solid wall bay or quay loading area. |

Ground both pivots on measured floor geometry. Leave door openings, thresholds and at least 2 m of clear public route. The cart is supported at its wheels and forward feet, so check all four contacts on uneven paving. Neither prop is tied to a previous building or facade actor.

From the repository root with `blender` on `PATH`:

```sh
blender --background --factory-startup --python-exit-code 1 --python ArtDirection/MedievalLondon/QuayDressing/build_quay_dressing.py -- --preview
blender --background --factory-startup --python-exit-code 1 --python ArtDirection/MedievalLondon/QuayDressing/build_quay_dressing.py -- --audit-import
```

The first run regenerates the GLBs and optional preview in `Source/`. The second imports each GLB and compares bounds, transforms, UV count, triangle count and ordered material slots to the export report. Unreal import and in-map placement are pending.
