# Licensing of human body models and video-to-motion stacks for a commercially sold UE 5.9 game (as of 2026-11-21)

Method note (read first). All "VERIFIED" items below were read on 2026-11-21 through a fetch-and-summarise tool (WebFetch), so quotes are as returned by that tool and are kept under 15 words; the full licence text was NOT reproduced for most licences. Items marked UNVERIFIED come from web-search summaries, third-party blogs, forums, or my background knowledge and were not read on a primary page. Several primary pages (meshcapade.com, Meshcapade Notion licence page, info.meshcapade.com, coco terms, gnu.org partially) returned 403 / 429 / empty to my fetcher. This is research, not legal advice; places where a lawyer's read is needed are tagged **[LAWYER]**.

---

## Key question 1. SMPL / SMPL-X / MANO / SUPR / STAR / SKEL licences: scope, outputs, joint-rotations-only, Meshcapade/Max Planck positions, commercial licence cost, AMASS

### Takeaway
All MPI-IS "model" licences (SMPL, SMPL-X, MANO, STAR, SUPR, SKEL, AMASS) are free-for-non-commercial-research grants that expressly bar commercial products, commercial services, "production of other artefacts for commercial purposes", and training neural networks for commercial use. None of them says what happens to motion data produced with them; no MPI or Meshcapade FAQ I could find addresses commercial use of SMPL-based estimator outputs or games, and nothing I found carves out "joint rotations only". The one explicit output-side release is the CC BY 4.0 "SMPL-Body" subset. Commercial licensing is paid and quote-based; public price figures conflict and are unverified. Since Feb 2026 Max Planck Innovation licenses SMPL directly (Epic bought Meshcapade's team, not SMPL).

### Cited Findings

**SMPL-Model licence (smpl.is.tue.mpg.de/modellicense.html) — VERIFIED**
- Grant: "To use the Software for the sole purpose of performing non-commercial scientific research" — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- Prohibition: "Any other use, in particular any use for commercial purposes, is prohibited." — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- Examples of prohibited commercial use: "incorporation in a commercial product, use in a commercial service" and "production of other artefacts for commercial purposes" — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- Training restriction: the licence "prohibits the use of the Software to train methods/algorithms/neural networks/etc." for commercial use of any kind — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- Redistribution: the Software may not be "made available in any form to any third party" without written permission; the grant includes the right to create derivative works of the Software — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- The page does NOT define "commercial", does not mention games, and does not say who owns or may use outputs (animations, meshes) — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)
- Commercial route: "available for commercial licensing through Meshcapade.com"; email smpl@max-planck-innovation.de — [SMPL model licence](https://smpl.is.tue.mpg.de/modellicense.html)

**SMPL-X licence (smpl-x.is.tue.mpg.de/modellicense.html) — VERIFIED**
- Same structure; grant widened to "non-commercial education, or non-commercial artistic projects" (still not commercial); same "incorporation in a commercial product, use in a commercial service" and "production of other artifacts for commercial purposes" language; same neural-network-training prohibition; adds a ban on fake/libelous/misleading/defamatory content; same commercial contact — [SMPL-X licence](https://smpl-x.is.tue.mpg.de/modellicense.html)

**MANO, STAR, SUPR, SKEL, AMASS — VERIFIED (each page fetched)**
- MANO: grant limited to non-commercial scientific research/education/artistic projects; prohibits training neural networks for commercial/pornographic/military/surveillance/defamatory purposes; commercial contact ps-license@tue.mpg.de — [MANO licence](https://mano.is.tue.mpg.de/license.html)
- STAR: same grant; "available for commercial licensing through Meshcapade.com"; commercial contact smpl@max-planck-innovation.de; the licence text defines "Data & Software" to include "3D meshes, images, videos, textures"; no distribution; no commercial/pornographic/military/surveillance use without licence — [STAR licence](https://star.is.tue.mpg.de/license.html)
- SUPR: non-commercial scientific research only; no distribution; training restriction; commercial contact ps-license@tue.mpg.de — [SUPR licence](https://supr.is.tue.mpg.de/license.html)
- SKEL: non-commercial; "any use for commercial, pornographic, military, or surveillance, purposes is prohibited"; training restriction; contact ps-license@tue.mpg.de; page does not mention SMPL/AMASS/BSM dependencies — [SKEL licence](https://skel.is.tue.mpg.de/license.html)
- AMASS: grant is non-commercial scientific research/education/artistic; the licence "prohibits the use of the Dataset to train methods/algorithms/neural networks/etc." for commercial use of any kind; "may not be reproduced, modified and/or made available" to third parties; commercial contact ps-license@tue.mpg.de; text does not mention trained models/derived data/outputs otherwise — [AMASS licence](https://amass.is.tue.mpg.de/license.html)

**SMPL-Body CC BY 4.0 (the only explicit "outputs" licence) — VERIFIED**
- "SMPL-Body" is a subset of SMPL-Model without the shape blendshapes; it "contains a 3D mesh, a skeleton rig, pose blendshapes" plus dynamic blendshapes; may be shared as OBJ, animated FBX, or other 3D formats; licensed CC BY 4.0 with credit, licence link, change notice, no-endorsement; media projects must credit MPI-IS — [SMPL-Body licence](https://smpl.is.tue.mpg.de/bodylicense.html)
- The same page states the SMPL-Model specification is covered by patents owned by the Max Planck Society (US10395411B2 granted; EP3314577A1 and WO2016207311A1 pending) and does not say whether the CC grant extends to the patent rights — [SMPL-Body licence](https://smpl.is.tue.mpg.de/bodylicense.html)
- Meshcapade's Blender add-on README: "Body meshes generated using this add-on are covered under the SMPL-Body CC-BY4.0 license" but also says "make sure you have an active SMPL Model commercial-use license" before using the add-on (model files are "available only under the SMPL-Commercial use license") — [Meshcapade SMPL_blender_addon LICENSE.md](https://github.com/Meshcapade/SMPL_blender_addon/blob/main/LICENSE.md)
- A search-engine summary attributes to the Meshcapade FAQ the statement that output bodies (animated FBX / OBJ) are free to distribute under the SMPL-Body CC licence while the statistical model needs a commercial licence; I could not open the FAQ page (info.meshcapade.com did not resolve) — UNVERIFIED — search result summary, [Meshcapade FAQ (unreachable)](https://info.meshcapade.com/faqs)

**Meshcapade wiki / licensing structure — VERIFIED**
- SMPL and variants "can all be sublicensed through Meshcapade's licensing options"; the commercial licence covers the adult variants "(SMPL+H, SMPL-X, STAR)"; infant SMIL and animal SMAL were "expected to be available as separate licenses soon"; each variant is free for academic use; page says nothing about games or SMPL-derived animations — [Meshcapade wiki SMPL.md](https://github.com/Meshcapade/wiki/blob/main/wiki/SMPL.md)
- MPI SMPL FAQ: "For commercial uses, please contact" sales@meshcapade.com; the FAQ has no Q&A on games, estimator outputs, joint rotations, or retargeting — [SMPL FAQ](https://smpl.is.tue.mpg.de/faq.html)

**Ownership/licensor change in 2026 — VERIFIED**
- Max Planck Innovation press release dated 20 Feb 2026: "MI will now directly take over the licensing of the SMPL technology"; core technology "remains available to both existing and new customers"; Meshcapade's team joins Epic's AI Research team for Unreal Engine/MetaHuman; release gives no terms or pricing — [EurekAlert / Max Planck Innovation](https://www.eurekalert.org/news-releases/1117236)
- Trade press: Epic acquired Meshcapade, deal announced 18 Feb 2026 (price undisclosed), closing April; technology expected to feed MetaHuman/Unreal; no statement on SMPL licence terms — [80.lv, 24 Feb 2026](https://80.lv/articles/ai-motion-capture-startup-meshcapade-now-part-of-epic-games); [Digital Production, 23 Jun 2026](https://digitalproduction.com/2026/06/23/metahuman-gets-markerless-mocap/)
- Consumer tool Me.Meshcapade reported shut down 18 Apr 2026 — UNVERIFIED — single aggregator page, [aixploria](https://www.aixploria.com/en/meshcapade-ai-3d-avatar-human/) (appeared in search results only)

**Pricing — UNVERIFIED and conflicting**
- Search summary of meshcapade.com/assets/body-models: commercial tiers "Micro" EUR 2,000/yr and "SME" EUR 10,000/yr, Enterprise on request; R&D licences EUR 600 / 3,000; tier re-evaluated annually; terms "subject to change without notice"; R&D licence "does not allow the commercialization of any products developed using the Body Models"; datasets: SMPL scan datasets EUR 10,000, MoCap datasets EUR 4,000 — UNVERIFIED — [Meshcapade body models](https://meshcapade.com/assets/body-models) (my fetch returned HTTP 403; figures come from a search-engine summary; a second search could not re-confirm them)
- A Meshcapade Notion licence page reportedly shows an Enterprise R&D price of EUR 124,200 and commercial "Contact Sales", with annual increases — UNVERIFIED — [Notion SMPL licences page](https://meshcapade.notion.site/The-SMPL-Model-Licenses-2144560e54388085af5eff111fcdf266) (page returned no text to my fetcher)
- Third-party founder blog: "Pricing has never been public; you email sales and negotiate"; author appears to have no first-hand licence — UNVERIFIED — [clad.you blog](https://clad.you/blog/posts/body-pipeline/)
- Blog claim "You need to pay when you create a 3D mesh from params" (HMR models output SMPL params; making a mesh needs the NC model files) — opinion, UNVERIFIED — [clad.you blog](https://clad.you/blog/posts/body-pipeline/)

### Inferences
- The restriction attaches to USE of the model files/software by whoever clicked through the licence, plus an explicit clause on "production of other artefacts for commercial purposes". It is not primarily a distribution-only restriction, so "the SMPL mesh never ships" is not a clean defence for a commercial studio that runs SMPL (or an SMPL-dependent estimator that requires the downloaded model files) in production to make game assets. **[LAWYER]**
- "Only joint rotations are used" is not addressed by any source I found. Arguments for safety (rotations are mere numbers; the 24-joint tree is generic) and against (the artefacts-for-commercial-purposes clause, the MPG patent on the model spec, estimator weights trained under SMPL/AMASS terms) are both open. Treat as UNSAFE unless MPI/Meshcapade confirm in writing. **[LAWYER]**
- Training-restriction clauses (SMPL, SMPL-X, MANO, STAR, SUPR, SKEL, AMASS all carry one) mean that estimator WEIGHTS trained against SMPL fits / AMASS may themselves be tainted for commercial use independent of whether SMPL ships. That is the weights-provenance question for HMR2.0/WHAM/GVHMR-class tools (covered by the other researcher).
- Practical commercial route if SMPL-family tools are wanted: a Max Planck Innovation / Meshcapade commercial licence (quote-based; price UNVERIFIED), explicitly asking in writing (a) whether motion/animation derived via SMPL-based estimators is covered, (b) whether estimator weights trained with SMPL/AMASS are covered, (c) game/per-title vs per-company scope, (d) whether the patent is licensed. The CC BY 4.0 SMPL-Body subset may let finished animated FBX of a SMPL-Body be shipped with attribution, but patent coverage is unclear and generating one still touches the model files.
- Epic's acquisition makes an Epic-side commercial arrangement for MetaHuman users plausible, but no source says the Max Planck licence now flows through Epic; licensing is described as going back to Max Planck Innovation.

### Gaps
- No MPI or Meshcapade FAQ/statement found on commercial use of outputs of HMR2.0/GVHMR/WHAM-style estimators, on games, or on joint-rotation-only use.
- Primary Meshcapade pricing/tier pages unreadable (403/empty); prices, "per title" vs "per company" scope, and whether the commercial licence covers training/estimator use are unknown.
- MoCapade / Meshcapade API terms for output rights could not be retrieved (meshcapade.com/legal returned 403); post-acquisition status of MoCapade unknown.
- Exact full text of each licence was not reproduced by the tool; only key clauses.

---

## Key question 2. NVIDIA stack: GEM-X, SOMA, Kimodo, BONES-SEED / Bones Studio, other 2026 releases

### Takeaway
NVIDIA's 2026 stack is the cleanest large-scale video-to-motion option found: GEM-X (video to world-space SOMA motion, released 30 Oct 2026) has Apache-2.0 code, an NVIDIA Open Model License weights licence with an explicit "ready for commercial use" statement, no SMPL, and SOMA (Apache 2.0) as its body model. Remaining uncertainty is dependency/backbone provenance (SAM License, ViTPose, hand weights) and unlisted real-world training data. Kimodo's SOMA-RP checkpoint is commercial-ready; the SMPL-X Kimodo checkpoint is non-commercial; BONES-SEED raw data is NOT free for ordinary commercial use (academics, or startups under USD 1M revenue only).

### Cited Findings

**GEM-X (NVlabs/GEM-X; HF nvidia/GEM-X; released 10/30/2026) — VERIFIED**
- Code licence Apache-2.0 (LICENSE file: Apache 2.0, "Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES", no non-commercial wording); some hand-processing files carry `LicenseRef-OpenMDW-1.1` — [GEM-X LICENSE](https://github.com/NVlabs/GEM-X/blob/main/LICENSE); [GEM-X repo](https://github.com/NVlabs/gem-x)
- Repo: "Model weights, geometry assets, and dependencies retain their respective terms"; SMPL is not mentioned anywhere on the repo page — [GEM-X repo](https://github.com/NVlabs/gem-x)
- Model card: "Use of the associated model is governed by the NVIDIA Open Model License Agreement"; "This model is ready for commercial or non-commercial use"; training data and SOMA body model "owned by NVIDIA or released under permissive licenses" — [GEM-X model card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md)
- Training data: about 1 M images and 300 h of video, "synthetic human-motion video rendered from NVIDIA in-house motion-capture data with real-world visual data"; annotations generated "by models released under licenses compatible with commercial use"; individual datasets are not listed and the dataset entry reads "Internal NVIDIA" — [GEM-X model card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md)
- Architecture/IO: 12-layer temporal Transformer, 46.8 M parameters (excluding body-pose feature extractor, hand model, detectors); input video of any resolution plus optional person boxes and camera intrinsics; output "Human body motion in SOMA format (world-space)", 77 joints — [GEM-X model card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md)
- Camera modes: `--camera-mode vipe` (moving camera, ViPE optional) or `static`; commands `pose-image`, `pose-video`, `motion-video`; outputs are `.pt` files (`body.pt`, `hands.pt`, `motion.pt`) rendered with `gem-render`; the repo page mentions no BVH/FBX/SMPL export — [GEM-X repo](https://github.com/NVlabs/gem-x)
- Hardware/OS: model card lists NVIDIA Ampere, inference hardware "NVIDIA Ampere A100 80GB", OS Linux/Windows/macOS; repo says Python >=3.10, PyTorch >=2.10 (CPU or CUDA), FFmpeg; rendering dependencies target "a Linux x86-64 environment"; no minimum VRAM is stated anywhere — [GEM-X model card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md); [GEM-X repo](https://github.com/NVlabs/gem-x)
- Dependencies named: SOMA 0.3.3 runtime, YOLOX HumanArt person detector (`yolox_humanart.onnx`), optional RT-DETR hand detector, original native77 ViTPose weights (`vitpose.pth` in the bundle), EgoHand-v1 hand weights "distributed separately" with licence "managed by the EgoHand-v1 model card" — [GEM-X repo](https://github.com/NVlabs/gem-x); [GEM-X model card](https://huggingface.co/nvidia/GEM-X)
- ATTRIBUTIONS.md lists four third-party licences: NVIDIA hand utilities (OpenMDW 1.1), OpenAI guided-diffusion (MIT), PyTorch3D/ACTOR rotation code (BSD-3), and "SAM 3D Body" under the SAM License (last updated Nov 19, 2025); it does not state SAM 3D Body's role (weights vs code) and does not mention DINOv3, MHR, ViTPose, YOLOX — [GEM-X ATTRIBUTIONS](https://raw.githubusercontent.com/NVlabs/GEM-X/main/ATTRIBUTIONS.md)
- The repo points to NVIDIA AI for Media (AR SDK / NIM) for developers integrating 3D body pose estimation into applications — [GEM-X repo](https://github.com/NVlabs/gem-x)

**Older GEM / GENMO (SMPL-based) — VERIFIED**
- GENMO/GEM repo: "released under the NVIDIA OneWay Noncommercial License"; released checkpoint "GEM-SMPL" is SMPL-based; training lists body model SMPLx; README sends full-body (hands + face) users to GEM-X; GENMO was renamed GEM in Dec 2025 — [NVlabs/GENMO](https://github.com/NVlabs/GENMO); project page [NVIDIA GEM](https://research.nvidia.com/labs/dair/gem). Do not confuse this with GEM-X. (The GENMO README links its checkpoint to an HF page named nvidia/GEM-X; verify which file is which before use.)

**SOMA-X body model — VERIFIED**
- "SOMA is released under the Apache 2.0 License"; "This model is ready for commercial use" — [SOMA-X model card](https://nvlabs.github.io/SOMA-X/stable/model_card.html)
- 77-joint full-body skeleton, 25-joint hand layers; identity backends: SOMA-shape, SMPL, SMPL-X, MHR, ANNY, GarmentMeasurements; SMPL/SMPL-X/MANO use is optional and MANO hand interop uses "separately licensed user-supplied model files" — [SOMA-X model card](https://nvlabs.github.io/SOMA-X/stable/model_card.html)
- Shape PCA trained on SizeUSA and TripleGangers scans "commercially licensed 3D body scan dataset" (purchased by NVIDIA); pose-corrective MLP trained on Bones RigPlay, "commercially licensed (purchased by NVIDIA)" — [SOMA-X model card](https://nvlabs.github.io/SOMA-X/stable/model_card.html)

**Kimodo (nv-tlabs/kimodo) — VERIFIED**
- Code Apache-2.0; checkpoints "licensed separately": most SOMA and G1 checkpoints under the NVIDIA Open Model License; Kimodo-SMPLX-RP-v1 under the NVIDIA R&D Model licence — [Kimodo repo](https://github.com/nv-tlabs/kimodo)
- Training data: Bones Rigplay 1 (~700 h, "proprietary", described as "commercially-friendly optical motion capture dataset"); BONES-SEED public subset 288 h — [Kimodo repo](https://github.com/nv-tlabs/kimodo)
- Kimodo-SOMA-RP-v1: NVIDIA Open Model License, "This model is ready for commercial use"; output root translation + joint rotations on the SOMA skeleton, 30 fps, max 10 s; hardware tested RTX 3090/4090/5090, A100 etc., Linux or Windows — [Kimodo-SOMA-RP-v1](https://huggingface.co/nvidia/Kimodo-SOMA-RP-v1)
- Kimodo-SOMA-SEED-v1 / v1.1: NVIDIA Open Model License, "This model is ready for commercial use"; trained on the public Bones-SEED dataset; the card does not address whether the BONES-SEED licence passes to model users — [Kimodo-SOMA-SEED-v1.1](https://huggingface.co/nvidia/Kimodo-SOMA-SEED-v1.1)
- Kimodo-SMPLX-RP-v1: "This model is for non-commercial research use only"; licence "NVIDIA Internal Scientific Research and Development Model License"; "Motions were retargeted to SMPL-X body-only skeleton for training"; gated — [Kimodo-SMPLX-RP-v1](https://huggingface.co/nvidia/Kimodo-SMPLX-RP-v1)
- Resources: ~17 GB VRAM for full GPU generation (mostly the text encoder); `TEXT_ENCODER_DEVICE=cpu` cuts that to under 3 GB; developed on Linux, "Windows should work especially if using Docker"; default output NPZ (`posed_joints`, `global_rot_mats`), SOMA 77-joint skeleton, SMPL-X models export AMASS NPZ; no video input (README points to GEM for video) — [Kimodo repo](https://github.com/nv-tlabs/kimodo)

**BONES-SEED dataset licence (bones.studio/info/seed-license) — VERIFIED**
- Eligibility: only (i) Academic Users (non-commercial, publicly available research) or (ii) Qualifying Startups with annual gross revenue under USD 1,000,000 (notice within 30 days and conversion to a paid licence if exceeded or on change of control); otherwise "you are NOT granted any rights" — [BONES-SEED licence](https://bones.studio/info/seed-license)
- Redistribution banned ("Sell, rent, lease, ... redistribute ... the raw Dataset"); public mirrors prohibited; raw-data embedding in a shipped product is not explicitly addressed but would read as redistribution; "Results" (including trained ML models) may be used and the licensee "acquires all proprietary copyrights to any Results", conditional on the raw data not being extractable — [BONES-SEED licence](https://bones.studio/info/seed-license)
- Models that generate motion data "as a commercial substitute for the Dataset" are prohibited; attribution phrase "Training data includes Motion Data by Bones Studio" required in model cards/README; no re-identification, deepfakes, weapons use; Polish governing law; USD 100 liability cap — [BONES-SEED licence](https://bones.studio/info/seed-license)
- HF dataset: licence name `bones-seed-license`, gated; formats SOMA Proportional/Uniform BVH, Unitree G1 CSV; "expanded datasets available for commercial licensing" via licensing@bones.studio — [BONES-SEED dataset](https://huggingface.co/datasets/bones-studio/seed)

**NVIDIA Open Model License (generic agreement page) — VERIFIED**
- "Models are commercially usable"; grant is "perpetual, worldwide, non-exclusive, no-charge, royalty-free, revocable" covering reproduction, modification, sale and distribution — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
- "NVIDIA claims no ownership rights in outputs"; licensee is "responsible for outputs and their subsequent uses" — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
- Rights terminate if a guardrail is bypassed without a substantially similar replacement, or if the licensee sues alleging the model infringes copyright/patents; distribution requires the Notice "Licensed by NVIDIA Corporation under the NVIDIA Open Model License"; use must be consistent with NVIDIA's Trustworthy AI terms; section 8 indemnification of NVIDIA; "Built on NVIDIA Cosmos" notice applies to Cosmos models only — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)

**Other NVIDIA 2026 items — VERIFIED**
- SOMA Retargeter v0.2 reads BVH on the SOMA base skeleton and writes robot CSV for Unitree G1/H2, Booster T1, AgiBot X2 Ultra/A3T3 (robots only; no MetaHuman target documented); NVIDIA blog states GEM-X "reconstructs whole-body 3D human motion from a single video" and also lists ARDY (interactive text/pose motion generation) and MotionBricks (G1 control) — [NVIDIA developer blog](https://developer.nvidia.com/blog/?p=125128); licence terms not stated there.

### Inferences
- Output-licensing logic: the NVIDIA Open Model License says NVIDIA claims no rights in outputs, GEM-X/Kimodo cards say commercial use is fine, and no SMPL model files are needed. That makes GEM-X SOMA motion and Kimodo SOMA-RP motion the best-documented commercial video/text-to-motion path. Still verify the exact licence version linked from the checkpoint you download (I read the generic agreement page, not a per-model PDF).
- Open risk for GEM-X: "Internal NVIDIA" plus unspecified "real-world visual data" and auto-labelling models, a SAM-License component in ATTRIBUTIONS.md (the SAM License has no non-commercial clause but has a trade-control/military clause, copy-of-agreement-on-redistribution, and a reverse-engineering ban), and the separately licensed hand weights. Body-only use (no EgoHand) removes the hand-weight question. Use NVIDIA's own commercial route (AI for Media / NIM) if a contractual warranty is needed.
- Same SOMA skeleton as Kimodo: GEM-X output (77-joint SOMA, world-space) should feed the same SOMA-to-MetaHuman retarget the project already uses for Kimodo; no NVIDIA MetaHuman retargeter exists in my sources, and GEM-X export is `.pt` (a SOMA-to-BVH/FBX step is needed; not documented on the repo page).
- Prefer Kimodo SOMA-RP over SOMA-SEED for shipping. The SEED checkpoint is NVIDIA Open Model License but trained on a dataset whose licence (startups under USD 1M, attribution, no-substitute clause) NVIDIA's card does not say it has passed through. Do not ship raw BONES-SEED BVH clips unless you hold a Bones Studio commercial licence or clearly qualify as a Qualifying Startup. **[LAWYER]** if revenue could exceed USD 1M.
- Kimodo-SMPLX-RP-v1 and the old GEM-SMPL/GENMO checkpoints are not shippable (R&D / OneWay Noncommercial, and SMPL).
- VRAM: GEM-X's only stated hardware is A100 80GB; a consumer 24 GB card may or may not run it (unknown). Kimodo is documented at roughly 17 GB, or under 3 GB with CPU text encoding.

### Gaps
- GEM-X minimum VRAM, Windows-native install status (README says rendering is Linux x86-64), and whether a SOMA-to-BVH/FBX exporter ships.
- What the SAM 3D Body entry in GEM-X's ATTRIBUTIONS.md actually covers (weights initialisation vs code) and its training-data terms.
- Licences of the ViTPose native77 weights bundle, ViPE, EgoHand-v1, YOLOX HumanArt weights.
- Full text of the BONES-SEED licence beyond the tool's summary; whether NVIDIA's Kimodo SEED weights are covered for downstream commercial users.
- The per-model licence PDF version linked from each NVIDIA model card.

---

## Key question 3. Meta SAM 3D Body / MHR (and other first-party video-pose options, including Epic's markerless plugin)

### Takeaway
SAM 3D Body (single-image, MHR output) is under Meta's SAM License, which has no non-commercial clause but carries trade-control/military, no-reverse-engineering, and copy-of-licence conditions; MHR is Apache 2.0. SAM 3D Body is image-only (no video/world-space), so video use means per-frame inference plus your own smoothing, or taking it via GEM-X. Epic's new MetaHuman Animator markerless plugin is the most MetaHuman-native route but its shipping/licence status is explicitly unresolved.

### Cited Findings

**SAM 3D Body — VERIFIED**
- "The SAM 3D Body model checkpoints and code are licensed under" the SAM License; checkpoints (facebook/sam-3d-body-dinov3, -vith) are gated on HF (request access) — [sam-3d-body repo](https://github.com/facebookresearch/sam-3d-body)
- Describes reconstruction from a single image ("3DB can reconstruct 3D full-body human mesh from a single image"); no video or world-space motion claimed; VRAM and Windows support not stated on the page; output is MHR-based; accepts auxiliary 2D keypoint/mask prompts — [sam-3d-body repo](https://github.com/facebookresearch/sam-3d-body)
- SAM License (Nov 19, 2025): grant is a "non-exclusive, worldwide, non-transferable and royalty-free limited license" to use, reproduce, distribute, modify; no non-commercial wording found; redistribution requires a copy of the Agreement; research publications must acknowledge use; no reverse engineering; no end uses prohibited by Trade Controls, including military/warfare, nuclear, espionage; patent-suit termination; outputs "AS IS" — [SAM License text in repo](https://github.com/facebookresearch/sam-3d-body/blob/main/LICENSE); [GEM-X ATTRIBUTIONS (reproduces it)](https://raw.githubusercontent.com/NVlabs/GEM-X/main/ATTRIBUTIONS.md)
- DINOv3 License (same wording family: "non-exclusive, worldwide, non-transferable and royalty-free limited license"; no commercial exclusion; same trade-control/military restrictions) — [DINOv3 LICENSE](https://raw.githubusercontent.com/facebookresearch/dinov3/main/LICENSE.md)

**MHR (Momentum Human Rig) — VERIFIED**
- "MHR is licensed under the Apache Software License 2.0"; 45 identity, 204 pose, 72 expression parameters; 7 LODs; includes MHR to/from SMPL/SMPL-X conversion tools (using those converters requires the SMPL model licences); README makes no statement on commercial use or training data — [MHR repo](https://github.com/facebookresearch/MHR)

**Sapiens (Meta) — VERIFIED**
- LICENSE file is CC BY-NC 4.0 (commercial use not permitted); whether the licence text reaches the weights is not addressed by the text itself — [Sapiens LICENSE](https://raw.githubusercontent.com/facebookresearch/sapiens/main/LICENSE); [Sapiens repo](https://github.com/facebookresearch/sapiens)

**Epic MetaHuman Animator Markerless Motion Capture plugin (UE 5.8+) — mixed**
- Free Fab add-on that "generates body animation from standard video footage"; output is an animation sequence; "animation maps to the final character without retargeting" because MetaHumans share one skeleton; Windows only for body capture; experimental ("not production-ready"); runs locally in batch — VERIFIED — [Epic docs: mono video capture](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine); [Digital Production](https://digitalproduction.com/2026/06/23/metahuman-gets-markerless-mocap/)
- Recommended hardware (MetaHuman Animator general): DirectX 12 GPU, 16 physical cores, 32 GB RAM, GPU such as RTX 3070 with 8 GB VRAM — VERIFIED (as reported) — [Digital Production](https://digitalproduction.com/2026/06/23/metahuman-gets-markerless-mocap/)
- Neither Epic docs nor the announcement name the underlying models or licences; Digital Production does not say whether the plugin uses Meshcapade technology — VERIFIED — [Epic docs](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine); [UE forum announcement](https://forums.unrealengine.com/t/epic-games-metahuman-animator-markerless-motion-capture-plugin/2729293.md)
- A developer asked (forum, Oct 2026) whether the plugin's model assets (GeoCalib, Detectron2, CHMR, HUE, "SMPL-X-related data") can be cooked into a shipped Steam game and whether SMPL-X needs a separate commercial licence; he had sent the question to Epic's licensing form on 27 Sep 2026 with no reply; the only responder was a community member (not Epic) advising to treat it as a "no" until Epic or the model authors confirm; no Epic answer in the thread — VERIFIED — [UE forum licensing thread](https://forums.unrealengine.com/t/licensing-question-shipping-metahuman-animator-markerless-motion-capture-runtime-models-in-a-steam-game/2839692)
- Fab listing reportedly "free, including for commercial use, under the Fab Standard License"; Fab EULA section 5(b) concern (engine plugins only distributable as Engine Tools) is raised in the thread — UNVERIFIED — search-result summary, [Fab listing](https://fab.com/s/bbce5dfd6b28)

### Inferences
- For a game that only ships baked animation sequences (not the plugin runtime or its models), the Epic plugin is the most MetaHuman-skeleton-native video route and probably the lowest friction; the unresolved part is whether SMPL-X-derived components inside the plugin place any restriction on its outputs, and Epic has not answered publicly. Get Epic's written answer (licensing form) before relying on it. **[LAWYER]** if outputs are shipped at scale.
- SAM 3D Body/MHR is usable commercially on its face (SAM License has no NC clause) but is a per-image estimator; temporal smoothness and foot contact would be your own problem unless taken via GEM-X.
- Sapiens is excluded by licence (CC BY-NC 4.0).

### Gaps
- No Meta video-to-motion/world-space release verified (SAM 3D Body page is single-image only); I did not find one.
- SAM 3D Body VRAM/Windows requirements (INSTALL.md not read) and training-data terms.
- Which models the Epic plugin contains and under what licences; whether Fab Standard License allows shipping its cooked runtime content.

---

## Key question 4. Commercially clean alternatives that avoid SMPL: code licence, weights licence, training data, 3D lifters, YOLO/detector risk

### Takeaway
Only a few options are clean on all three layers (code, weights, data). MediaPipe BlazePose and Anny (the body model) are the clearest. Most research lifters (MeTRAbs, VideoPose3D, MotionBERT-class) are blocked or doubtful because training data (Human3.6M, MPI-INF-3DHP, AMASS) is non-commercial; Apache/MIT code does not clean the weights. Sapiens, OpenPose, SKEL are non-commercial; Ultralytics YOLO is AGPL-3.0.

### Cited Findings

**MediaPipe Pose / BlazePose (Google) — VERIFIED**
- HF model card for the Full task bundle lists licence `apache-2.0`; training "Real-world consented in-the-wild AR images (30K)" plus fitness pose datasets (85K) with synthetic GHUM depth supervision — [HF litert-community Pose Landmarker Full](https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full)
- Output 33 landmarks with normalised image coordinates and world coordinates "in real-world meters with the midpoint of the hips as the origin" (positions, not rotations; needs IK to a MetaHuman rig); single person only; Z is relative/up to scale; "Any form of surveillance or identity recognition is explicitly out of scope" — [Google MediaPipe docs](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker); [HF card](https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full)
- Documentation lists Web/Android/iOS/Python/Flutter; Windows is not named on that page (pip install works on desktop Python in my experience, UNVERIFIED) — [Google MediaPipe docs](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)

**RTMPose / RTMW / MMPose (OpenMMLab) — mixed**
- Code: "released under the Apache 2.0 license" — VERIFIED — [MMPose repo](https://github.com/open-mmlab/mmpose)
- Pretrained model zoo is trained on combined datasets (COCO, AI Challenger, Halpe, Body8, Cocktail14, UBody); no weights licence statement and no dataset-licence statement on the README/RTMPose page I read — VERIFIED (absence) — [MMPose repo](https://github.com/open-mmlab/mmpose); [RTMPose README](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/README.md)
- Detectors: MMDetection (RTMDet) code Apache 2.0, no pretrained-weight licence statement — VERIFIED — [mmdetection](https://github.com/open-mmlab/mmdetection)

**ViTPose — VERIFIED**
- Code Apache-2.0; no weights licence statement (weights on OneDrive); trained on COCO, AIC, MPII, CrowdPose, AP-10K, APT-36K, COCO-WholeBody — [ViTPose repo](https://github.com/ViTAE-Transformer/ViTPose)

**OpenPose — VERIFIED / UNVERIFIED**
- Licence grants "a personal, non-exclusive, non-transferable license to use the Software for noncommercial research purposes" to academic/non-profit users; derivatives are owned by the Licensor and usable only for internal noncommercial research; text mentions no commercial licence — VERIFIED — [OpenPose LICENSE](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/LICENSE)
- Commercial licence via CMU's FlintBox listing; USD 25,000/year appears only in community forum posts, no official source found — UNVERIFIED — [Intel community post](https://community.intel.com/t5/Intel-Distribution-of-OpenVINO/Is-royalty-for-human-pose-estimation-0001-commercial-use-free/td-p/1144783); [Vuo forum](https://community.vuo.org/t/have-you-seen-openpose/6070)

**3D lifters — VERIFIED**
- MeTRAbs: code MIT, but "The models can only be used for non-commercial purposes due to the licensing of the used training datasets"; SMPL is only a supported skeleton convention (joint naming), not a required model — [MeTRAbs repo](https://github.com/isarandi/metrabs)
- MotionBERT: code Apache-2.0; pretrained weights (OneDrive/HF) have no stated licence; the README does not state training datasets or their terms (the paper trains on Human3.6M among others, UNVERIFIED from my background knowledge) — [MotionBERT repo](https://github.com/Walter0807/MotionBERT)
- VideoPose3D: "licensed under CC BY-NC" (version not shown); repository archived 31 Oct 2023; "Third-party datasets are subject to their respective licenses" — [VideoPose3D repo](https://github.com/facebookresearch/VideoPose3D)
- Human3.6M licence: "Licenses free of charge are limited to academic use only"; commercial via separate arrangement; does not address trained models — [Human3.6M licence](http://vision.imar.ro/human3.6m/eula.php)
- MPI-INF-3DHP download page states no licence or terms (contact the author) — [MPI-INF-3DHP page](https://vcai.mpi-inf.mpg.de/3dhp-dataset/)
- MotionAGFormer: not checked (no source read) — UNVERIFIED.

**Body models other than SMPL — VERIFIED**
- Naver Anny: code Apache 2.0; MPFB2 and face-unit data CC0 1.0; SOMA-adapted data Apache 2.0; the `smplx` topology/interop is "non-commercial use only" and the `[smpl]` install pulls non-free dependencies; "Free install" vs "Full install (non-free dependencies)"; "Anny is open-source and free" — [anny repo](https://github.com/naver/anny)
- Naver blog: Anny "doesn't use 3D human scans"; built from MakeHuman and WHO anthropometric data; "released under Apache 2.0 for unrestricted use"; the Anny-One synthetic image set (800 k+ images) has no stated licence — [NAVER LABS Europe blog](https://europe.naverlabs.com/blog/anny-a-free-to-use-3d-human-parametric-model-for-all-ages/)
- Multi-HMR (Naver's HMR) code/checkpoints "provided under the terms of this LICENSE and accompanying NOTICE" (licence type not shown), the Anny-based checkpoint has its own separate licence file (`Checkpoint_License_Anny.txt`, not read); the SMPL-X variant needs user-registered SMPL-X files — [Multi-HMR repo](https://github.com/naver/multi-hmr)
- MHR (Meta): Apache 2.0 (see Key question 3); SOMA (NVIDIA): Apache 2.0 (see Key question 2).
- SKEL: non-commercial (see Key question 1).

**FreeMoCap — VERIFIED**
- Licence AGPL-3.0; maintainers will "discuss terms" for another licence at "a price point that increases exponentially"; the page does not say whether recordings/outputs are covered; dependencies skellytracker/skellycam come from private git repos with unstated licences; (multi-camera system; monocular video not its design) — [FreeMoCap repo](https://github.com/freemocap/freemocap)

**Detectors/trackers — VERIFIED**
- Ultralytics YOLO: AGPL-3.0 with a separate Enterprise License that "bypasses" the AGPL open-source requirements; the page does not say whether weights/outputs are covered or address games — [Ultralytics repo](https://github.com/ultralytics/ultralytics)
- Apache-2.0 code: YOLOX (also the detector GEM-X uses: `yolox_humanart.onnx`), RT-DETR (lyuwenyu), MMDetection/RTMDet; none of the three repos states a licence for pretrained weights; RT-DETR weights are trained on COCO and Objects365 — [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX); [RT-DETR](https://github.com/lyuwenyu/RT-DETR); [mmdetection](https://github.com/open-mmlab/mmdetection)
- COCO terms-of-use page did not load for my fetcher; the commonly cited "annotations CC BY 4.0, images under Flickr terms" is UNVERIFIED — [COCO](https://cocodataset.org/#termsofuse)

### Inferences
- Layering rule: code licence != weights licence != training-data licence. MeTRAbs is the proof case (MIT code, non-commercial weights). Apache/MIT on a lifter repo says nothing about whether Human3.6M/AMASS-trained weights can be used commercially.
- Cleanest 3D-lift path from the sources: MediaPipe BlazePose world landmarks (Apache weights, consented Google data) then your own IK/retarget; or NVIDIA GEM-X/Epic plugin which output rotations directly. Quality of BlazePose for hands/feet and occlusion is a separate engineering question (not researched).
- 2D-only detectors (RTMPose COCO-trained variants, ViTPose, YOLOX, RTMDet, RT-DETR) are probably lower risk because COCO-class datasets are the main training data, but the multi-dataset weights (Body8/Cocktail14/Halpe/AIC) were not checked dataset by dataset. Treat as Uncertain until each dataset's terms are read.
- Avoid Ultralytics YOLO unless an Enterprise License is bought; use YOLOX/RTMDet/RT-DETR instead (code verified Apache 2.0; weights provenance unverified).
- An H36M/3DHP/AMASS-trained lifter's outputs: see Key question 5; the clean answer is that the clause that bites is the restriction on USING the weights commercially, not the ownership of outputs.

### Gaps
- RTMPose/RTMW/RTMPose3D weights licences and the exact datasets in Body8/Cocktail14 (and their terms); RTMPose3D in particular.
- MotionBERT/MotionAGFormer training sets and weights terms; MPI-INF-3DHP licence terms.
- Multi-HMR and Anny-checkpoint licence text; whether any monocular video estimator is trained purely on Anny-One synthetic data.
- GHUM licence status (BlazePose uses GHUM-based supervision; HF card says Apache 2.0 for the model).
- COCO and AI Challenger licence text.

---

## Key question 5. Does a tool's licence follow its output? (AGPL/GPL, research-only licences, weights licences)

### Takeaway
Mainstream position: copyleft code licences generally do not reach a program's output, except where the output copies substantial parts of the program. Research-only licences and model-weights licences are different in kind: they restrict USE (and often include artefact/training clauses), so using non-commercial weights to produce commercial assets is the clear breach path, regardless of who "owns" the output. Whether such contract-style restrictions are enforceable at all is contested in academic commentary and untested in court; this is exactly where a lawyer is needed.

### Cited Findings
- GPL FAQ: the output of a GPL program is "not, in general, covered by the copyright on the code"; exception when the output includes substantial parts of the program itself (e.g. its own text/art; video-game audio/art that comes from the program); "In general this is legally impossible" to GPL a user's output — VERIFIED — [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html)
- AGPL-3.0 section 2: output from running a covered work is covered "only if the output, given its content, constitutes a" covered work (tool truncated the quote); section 13 requires modified versions to offer source to network users — VERIFIED — [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html)
- Henderson & Lemley (Stanford Law), arXiv Dec 2024: "the legal enforceability of these licenses is questionable"; weights and outputs generally lack copyright protection; copyright-preemption trends may undermine state-law (contract) claims; DMCA/CFAA "offer limited recourse"; "no model creator has actually tried to enforce these terms" with money damages or injunctions (apart from account suspensions) — VERIFIED (abstract) — [The Mirage of AI Terms of Use Restrictions](https://arxiv.org/abs/2412.07066)
- NVIDIA Open Model License expressly disclaims ownership of outputs but makes the licensee "responsible for outputs and their subsequent uses" and makes the licence revocable — VERIFIED — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
- Research-only licences in this space are explicit about use, not just distribution: SMPL family "production of other artefacts for commercial purposes" and neural-network-training bans; OpenPose "noncommercial research purposes"; MeTRAbs weights "non-commercial purposes"; Human3.6M "academic use only" — VERIFIED — see Key questions 1 and 4 sources
- US Copyright Office Part 2 report on copyrightability of generative-AI outputs published 29 Jan 2025; the tool could not read its conclusions; commonly summarised as pure AI-generated output lacking human authorship not being copyrightable — page confirms only title/date; conclusion UNVERIFIED — [Copyright Office AI page](https://www.copyright.gov/ai/)

### Inferences
- Output-follows-tool: for copyleft code (FreeMoCap AGPL, Ultralytics AGPL) the mainstream view is that recorded/estimated motion data is not a derivative of the tool's code, so shipping the data does not drag the game under AGPL; the AGPL risk is instead (a) embedding/linking the code into the game or a network service, (b) dependency/commercial-licence demands. Ultralytics sells an Enterprise licence precisely because they treat production use as needing one.
- Output-follows-weights: no mainstream authority says outputs inherit a model's licence; but this does not rescue a commercial studio that ran a non-commercial licensed tool, because the breach is the use. The risk is contract/licence enforcement (and SMPL's patent), not copyright in the animation. Enforcement against a game studio is untested; academic commentary says such terms are shaky, but a patent (SMPL) or a licensor with actual commercial licensing programmes (MPI/Meshcapade, Bones Studio, CMU OpenPose) is more likely to pursue than a typical model author.
- Practical posture: choose stacks where every layer (code, weights, data) is explicitly commercial (GEM-X, Kimodo SOMA-RP, BlazePose, MHR, SOMA, Anny) and keep a provenance log (licence version, download date) per checkpoint. For "uncertain" layers, ask the licensor in writing.
- **[LAWYER]**: (1) whether a lifter trained on non-commercial data (MeTRAbs, VideoPose3D-class) produces shippable outputs in the owner's jurisdiction; (2) SMPL patent and the "artefacts" clause vs joint-rotation-only use; (3) BONES-SEED "Results" ownership/startup threshold; (4) Fab EULA section 5(b) for shipping plugin content.

### Gaps
- No court decisions on research-only licence enforcement for weights/outputs found.
- Copyright Office Part 2 conclusions not read directly.
- No jurisdiction-specific (EU/UK) analysis; Max Planck licences are governed by German law (SKEL page states this), Bones by Polish law.

---

## Key question 6. Bottom line: which stack gives commercial-shippable output?

### Takeaway
Best documented: NVIDIA GEM-X (video) and Kimodo SOMA-RP (text) on the SOMA skeleton. Most MetaHuman-native: Epic's markerless plugin (status unresolved for shipping runtime, probably fine for baked animations). Avoid anything SMPL-dependent or trained on H36M/AMASS-class data unless a commercial licence and written confirmations are in hand.

### Cited Findings (bottom-line table; ratings are my judgement from the sources cited above)

| Stack | Shippable output? | One-line reason | What would change it |
|---|---|---|---|
| NVIDIA GEM-X (video to SOMA motion) | Probably | Apache code; NVIDIA Open Model License weights "ready for commercial or non-commercial use"; no SMPL; SOMA Apache 2.0; NVIDIA claims no rights in outputs. Open: "Internal NVIDIA" data, SAM-License component, hand weights. | Yes if NVIDIA confirms backbone/data provenance in writing; No if a dependency (ViTPose/SAM 3D Body weights, EgoHand) turns out non-commercial |
| Kimodo SOMA-RP-v1 (text to motion) | Yes (Probably) | Open Model License, "ready for commercial use", trained on NVIDIA-purchased Rigplay | Check the licence version on the card; revocability |
| Kimodo SOMA-SEED-v1 / v1.1 | Probably | Same licence, but trained on BONES-SEED whose licence (academics / startups under USD 1M) is not shown to pass to users | Bones Studio / NVIDIA confirmation, or revenue above USD 1M |
| Kimodo SMPL-X-RP-v1 | No | "for non-commercial research use only"; SMPL-X | NVIDIA commercial arrangement plus SMPL licence |
| BONES-SEED raw clips | No (default) | Academics or Qualifying Startups only; redistribution of raw data banned | Commercial licence from licensing@bones.studio |
| Old GEM/GENMO (GEM-SMPL) | No | "NVIDIA OneWay Noncommercial License" and SMPL | None |
| Epic MetaHuman Animator markerless plugin (baked animations) | Probably | First-party, free on Fab (commercial use reportedly allowed, UNVERIFIED), maps directly to MetaHuman skeleton; no Epic answer on SMPL-X-derived models or shipping runtime | Epic written answer; if runtime/models must ship, treat as No until answered |
| Meta SAM 3D Body + MHR (per image) | Probably | SAM License has no NC clause; MHR Apache 2.0; image-only; gated weights; trade-control/military clause | Meta clarification on training data; use via GEM-X for video |
| SMPL / SMPL-X / MANO / STAR / SUPR / SKEL + any SMPL-requiring estimator (HMR2.0, WHAM, GVHMR...) without licence | No | Non-commercial; bans commercial artefacts, commercial training, redistribution; MPG patent | Max Planck Innovation / Meshcapade commercial licence plus written scope on estimator outputs |
| Same, WITH a commercial SMPL licence | Uncertain | Licence cost/scope unknown (price UNVERIFIED); estimator weights have own (AMASS/dataset) terms | Written confirmation covering estimator weights and outputs |
| SMPL-Body CC BY 4.0 artefacts (mesh + rig + FBX) | Probably (attribution) | Explicit CC BY 4.0 grant, FBX sharing allowed; patent not addressed; generating them needs the model files | MPG patent statement; licensed generation route |
| MediaPipe BlazePose | Yes | Apache-2.0 weights; consented Google data; keypoints only (IK needed) | Lower quality, single-person |
| RTMPose / RTMW / RTMPose3D | Uncertain | Apache code; weights trained on mixed datasets, no weights licence stated | Dataset-by-dataset check; COCO-only checkpoints safest |
| ViTPose | Uncertain | Apache code; weights licence not stated; COCO/AIC/MPII-class data | Dataset terms review |
| MotionBERT / MotionAGFormer | Uncertain to No | Apache code, weights unlicensed, Human3.6M-type training data | Retrain on clean data |
| MeTRAbs | No | Weights "can only be used for non-commercial purposes" | Retrain on clean data |
| VideoPose3D | No | CC BY-NC; H36M | None |
| Sapiens | No | CC BY-NC 4.0 | Meta commercial licence |
| OpenPose | No (without paid licence) | Non-commercial research licence; paid CMU licence (price UNVERIFIED) | Buy FlintBox licence |
| FreeMoCap | Probably (outputs) / Uncertain (code use) | AGPL code; outputs generally not covered; dependency licences unstated; multi-camera | Commercial licence or clean-room use |
| Anny (body model) | Yes for model; Uncertain for Multi-HMR checkpoint | Apache 2.0; CC0 data; no scans; checkpoint licence unread; smplx topology NC | Read Checkpoint_License_Anny.txt |
| Ultralytics YOLO (detector) | No (without Enterprise licence) | AGPL-3.0 | Enterprise licence, or use YOLOX/RTMDet/RT-DETR |

### Inferences
- Suggested shortlist for the project: (1) GEM-X to SOMA77 for video-to-motion, reusing the existing Kimodo SOMA retarget; (2) Epic markerless plugin as a second source for baked MetaHuman-skeleton animations, after getting Epic's answer; (3) MediaPipe BlazePose as a fully permissive fallback needing IK. Everything SMPL-based is deferred pending a commercial licence quote and written scope.
- Ask NVIDIA, Epic and Max Planck Innovation the specific questions listed in Key questions 1-3; they are the only ones who can convert "Probably" to "Yes".

### Gaps
- Everything marked UNVERIFIED above (Meshcapade prices, OpenPose fee, Fab listing wording, COCO terms, Copyright Office conclusion, Meshcapade FAQ on SMPL-Body outputs).
- No lawyer-reviewed read of any of these licences.
