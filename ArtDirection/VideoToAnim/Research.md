**Title:** Film Your Own Motion, Skip YouTube: Video-to-Animation for Reflections | **Date:** 2026-11-21 | **Status:** research only; nothing installed, downloaded or changed | **Not legal advice**

*Markers.* (V) = read on a primary source (local file, or page read in a browser). (V*) = read on a primary page only through a summarising fetch tool: re-read the live text before relying on it, above all licence and terms wording. (U) = unverified (search snippet, secondary article, forum post, page not opened). (E) = my estimate or inference. The notes on commercial tools, open models, licences, clean sources, law and pipeline engineering used a summarising fetch tool, so their "verified" items are (V*); the Epic/UE audit and local-fit audit used local files and browser reads, so they are (V) unless marked.

## 1. Bottom line

**Verdict: build a narrower version, and do not build the YouTube version.** A pipeline that turns *your own filmed footage* into body animation is worth a one-day proof of concept and, if that passes, a small build. A pipeline that ingests YouTube videos is not worth building for a game you may sell.

**Recommended path.** Film short clips yourself (tripod, one performer, full body) for what Kimodo does badly: swordplay, digging, carrying, hands on props. Test two routes on the Hero and compare: (A) NVIDIA GEM-X to the SOMA skeleton to your existing `RTG_SomaToHero` retargeter, and (B) Epic's free MetaHuman Animator Markerless Motion Capture plugin, which writes MetaHuman-skeleton animation directly. Kimodo stays the main source for locomotion, idles and talk; licensed libraries fill common actions; face comes from MetaHuman Animator if wanted.

**Three facts drive this.** (1) Licences: the open models with the best published accuracy (GVHMR, ExMR, FlowHMR, PromptHMR) are non-commercial, and the SMPL body-model family bars commercial products and producing other artefacts for commercial purposes. Of the video-to-motion stacks that output joint rotations, only GEM-X (Apache-2.0 code, NVIDIA Open Model License weights, no SMPL) and Epic's plugin are plausibly shippable, and neither is confirmed in writing. (2) YouTube: its Terms bar downloading with no analyse-and-delete exception, a DMCA section 1201 claim over ripping YouTube clips survived a motion to dismiss (order reported 5 Feb 2026) with statutory damages of $200-$2,500 per act, and cloud vendors make you warrant you own what you upload. Copyright risk in the shipped animation is low; the risk is the process, and it scales with volume. (3) Value: the project has no capture assets, Kimodo's SOMA skeleton has no fingers, and no source supports using monocular output without cleanup.

**You are asked to approve** the roughly one-day proof of concept in section 9 (own clips only; downloads of GEM-X weights, an ffmpeg binary and optionally the Epic plugin; a window with the shared editor closed for GPU work, then open for import), and drafting written questions to NVIDIA, Epic and a lawyer.

## 2. State of the art, Nov 2026

**Epic's stack.** Face from ordinary video is built into MetaHuman Animator (MHA): since UE 5.6 (June 2025) it solves from webcams, phones and other single cameras, offline or real time, with no iPhone, depth or Identity asset ([MetaHuman 5.6 post](https://forums.unrealengine.com/t/metahuman-5-6-release/2539165), V). UE 5.9 here ships the MHA editor stack, a Live Link Hub Mono Video Ingest device (mp4/mov) and a body-solver interface, but **no body solver** (V, local audit). Body from video arrived with MetaHuman 5.8 (17 June 2026) as the free, experimental, Windows-only Fab plugin *MetaHuman Animator Markerless Motion Capture*: one actor, one camera, body with hands, face optional, processed locally, UE 5.8-5.9 ([Epic docs](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine); [Fab listing](https://www.fab.com/listings/4095b8e0-3eff-44f1-acb4-cb40b99228b9), V). It is not installed here. Epic's footage rules describe a purpose-shot clip: static camera, one performer, full body, no occlusion, fitted clothes ([guidelines](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-video-capture-guidelines-in-unreal-engine), V*). No accuracy figures exist; trade press frames it for blocking, previs and indie capture ([Digital Production](https://digitalproduction.com/2026/06/23/metahuman-gets-markerless-mocap/), U). The 5.9 release notes (still titled Preview, updated 19 Nov 2026) have no MetaHuman or mocap text; Epic's 5.9 animation-AI work is generative (AnimGen, Kimodo) ([5.9 notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-9-release-notes), V). Video-to-body is a 5.8 experiment carried to 5.9 by a Fab compatibility bump (E).

**Commercial tools.** All are cloud except Cascadeur's desktop app. No independent measured comparison exists for 2026 versions; vendor claims, anecdotes and trade notes agree: usable blocking and decent locomotion on clean, static, single-person footage, with foot contact, hands, occlusion and fast action needing cleanup ([Rokoko, Oct 2025](https://www.rokoko.com/insights/the-future-of-motion-capture), V*).

**Open models.** The classic world-grounded family (GVHMR, WHAM, TRAM, PromptHMR-Video) has published numbers. October 2026 added ExMR and FlowHMR (author numbers only) and NVIDIA GEM-X (30 Oct), the one stack that skips SMPL and outputs world-space motion on the 77-joint SOMA skeleton, the family Kimodo emits ([GEM-X card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md), V*). The only practical comparison is one Windows-app maintainer's subjective ranking on an RTX 5090 ([RGB MoCap guide](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/docs/USER_GUIDE.md), V*).

| Date (2026) | What changed | Marker |
|---|---|---|
| 18-20 Feb | Epic buys Meshcapade (team joins Epic AI Research); Max Planck Innovation takes over SMPL licensing ([MI release](https://www.eurekalert.org/news-releases/1117236); [80.lv](https://80.lv/articles/ai-motion-capture-startup-meshcapade-now-part-of-epic-games)) | (V*); Epic detail (U) |
| Apr | Radical shut, Autodesk took the tech ([CG Channel](https://www.cgchannel.com/?p=175200)); Meshcapade web platform reported shut (one aggregator; conflicting) | (U) |
| 17 Jun | MetaHuman 5.8 and the markerless plugin | (V) |
| 16 Jul | Rokoko Vision 3.0: cloud, folded into Create, no finger tracking ([post](https://www.rokoko.com/insights/introducing-rokoko-vision-3-0)); Uthana goes pay-as-you-go in Aug | (V*) |
| 9 Oct | Move AI assets sold to Oxford Metrics (Vicon) for GBP 525k; Move One's future unclear ([BusinessCloud](https://businesscloud.co.uk/news/cost-cutting-oxford-metrics-agrees-cut-price-deal-for-move-ai/)) | trade press |
| Oct | ExMR and FlowHMR appear; GEM-X released 30 Oct; Epic's EULA update 22 (30 Oct) lifts the AI-training bar on MetaHuman curves ([change log](https://www.unrealengine.com/eula-change-log/unreal)) | (V*); (V) |
| 9 Nov | Fab plugin updated to "5.8-5.9"; changelog empty | (V) |

DeepMotion is alive but its release log stops in 2023 (V*). The Meshcapade-to-plugin link rests on one search summary (U); the engine's body interface names an SMPL-FN body (V, local).

## 3. Comparison table

Verdicts are for *output used in a sold game*, assuming own-filmed footage. **Yes** = licence layers look commercial-clean on the evidence read. **Probably** = clean on paper with a named open item. **Uncertain** = an unresolved layer. **No** = non-commercial or unusable. Accuracy is the authors' own on EMDB-2 (WA-MPJPE100 in mm; jitter and foot-slide units as published); paper-to-paper numbers are not directly comparable. No source reports any run on an RTX 5080.

### 3A. Epic and commercial tools

| Option | Quality (evidence) | Cost | Where | Tool licence | Output terms, sold game | MetaHuman / UE path | Windows + RTX 5080 | Ship? |
|---|---|---|---|---|---|---|---|---|
| [Epic MHA mono-video face](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-02-process-and-export-your-animation-in-unreal-engine) | Face only; no accuracy figures (U) | Free | Local | UE EULA (V) | Your Product; royalty-free; usable outside UE (V) | Native; Performance asset; batch script ships | GPU floor met; CPU below guidance | **Yes** (own footage) |
| [Epic markerless plugin](https://www.fab.com/listings/4095b8e0-3eff-44f1-acb4-cb40b99228b9) | Body+hands; no metrics; fps, install, crash reports (U) | Free | Local | Fab Standard License; AI use: No | Epic silent on baked output and SMPL-X parts | Native; Existing Skeleton export | Windows only; 8 cores vs 16 advised; 5.9 untested | **Probably** |
| [Move One](https://www.move.ai/move-one-app-eula) | Seller claims 85-90% of optical (U) | $18-$490/mo; $267-$533 per 1,000 s | Cloud | n/a | Move AI owns Output IP, licenses back; no games clause; trains on uploads (V*) | FBX/USD | n/a | **Uncertain** (Vicon limbo) |
| [Rokoko Vision 3.0](https://www.rokoko.com/products/vision) | Weak floor contact admitted; no fingers | Free 30 s/mo; Basic $12/mo | Cloud | n/a | Silent on output commercial rights (V*) | FBX/BVH, UE5 Manny | n/a | **Uncertain** |
| [DeepMotion](https://www.deepmotion.com/faq) | Foot-lock modes; stale log | Free NC; paid prices unread | Cloud | n/a | Paid: commercial; in-game binary only, no resale of retargeted clips (V*) | FBX/BVH | n/a | **Probably** (paid) |
| [QuickMagic](https://www.quickmagic.ai/Pricing) and [iClone Video Mocap](https://www.reallusion.com/iclone/video-mocap) | Jitter fixed by smoothing (one anecdote) | Pro ~$40-$50 per 1,000 credits; iClone $0.05/s or $2.50/task (conflict) | Cloud | n/a | Paid tiers: commercial use; free: testing only; no training on private uploads (V*) | FBX/BVH, "UE MetaHuman" preset (test) | n/a | **Probably** (paid) |
| [Uthana](https://uthana.com/terms) | No evidence found | $0.05-0.06/s | Cloud | n/a | Paying customer owns outputs, may use in games; may train on inputs (V*) | Export formats unclear | n/a | **Probably** |
| [Cascadeur](https://cascadeur.com/plans) | Vendor: foot-slide cleanup; one outlet denies video mocap | Indie $19/mo (<$100k revenue) | Local | Commercial tiers | Video-mocap terms not found | FBX; UE5 Live Link | Not checked | **Uncertain** |
| Plask, Flow Studio, Viggle PINOC, Kinetix, FreeMoCap | Not assessed | Varies | Mostly cloud | n/a | Stale 2023 terms (Plask); terms not found (Flow Studio, Viggle); B2B only (Kinetix); multi-camera AGPL (FreeMoCap) | Varies | n/a | **Uncertain** |
| Meshcapade MoCapade, Radical | Gone | n/a | n/a | n/a | Moot | n/a | n/a | **No** |

### 3B. Open models (local)

| Option | Quality (evidence) | Cost | Where | Tool licence | Output terms, sold game | MetaHuman / UE path | Windows + RTX 5080 | Ship? |
|---|---|---|---|---|---|---|---|---|
| [GEM-X](https://github.com/NVlabs/GEM-X) | World-space SOMA; WA 112.8, jitter 34.2, foot slide 4.2; "fast but lower quality" (app maintainer); one person | Free | Local | Code Apache-2.0; weights NVIDIA Open Model License | NVIDIA claims no output rights; open: Internal NVIDIA data, SAM-licence part | `.pt` only; glue to SOMA then `RTG_SomaToHero` | Card lists Windows; README silent; 3.5 GiB peak on a 5090 | **Probably** |
| [GVHMR](https://github.com/zju3dv/GVHMR) | WA 111.0, jitter 16.7, foot slide 3.5; no fingers; skate in issues | Free | Local | Commercial use prohibited; AGPL YOLOv8 | Use barred; needs SMPL(-X); AMASS-trained | No export | Only model with Blackwell+Windows evidence; ~5 GiB | **No** |
| [ExMR](https://github.com/twehrbein/ExMR) | Adds fingers/feet; no benchmarks | Free | Local | Research/non-profit only (GVHMR derivative) | Barred | BVH/FBX export | Linux-tested; ~11 GiB | **No** |
| [FlowHMR](https://github.com/flowhmr/flowhmr) | RICH WA 56.7, jitter 6.7 (authors); slow | Free | Local | Code Apache-2.0; weights non-commercial | Barred | npz, optional FBX | 10.7-14.9 GiB | **No** |
| [FAB](https://github.com/noahcao/FAB) (added 23 Nov) | Author's re-run, same frames: EMDB-2 WA 57.1 vs GEM-X 114.2, jerk 5.3 vs 35.3, foot slide 6.8 vs 4.3 mm; heel/toe contacts; 39 fps on a 4070 Ti SUPER. arXiv Nov 2026, one author | Free | Local | Code Apache-2.0 (SAM/DINOv3 parts excepted); all weights research/non-commercial (`WEIGHTS_LICENSE` part 3: SMPL-supervised, NC datasets); YOLO11 detector of AGPL lineage | Barred; needs SMPL download | SMPL / MHR mesh in npz; no SOMA | Linux-style install; world mode needs ViPE, COLMAP, Mask2Former (Windows unproven) | **No** |
| [PromptHMR-Video](https://github.com/yufu-wang/PromptHMR) | Best classic numbers: 71.0, jitter 16.3, foot 3.5 | Free | Local | Non-commercial; commercial via Meshcapade | Barred | GLB/MCS | Pre-Blackwell torch pins; needs VS2022 | **No** |
| [WHAM](https://github.com/yohanshin/WHAM), [TRAM](https://github.com/yufu-wang/tram) | WHAM 135.6, jitter 22.5, idle since 2024; TRAM 76.4, foot skating 23.4 | Free | Local | MIT code; need SMPL; WHAM AMASS-trained, TRAM data terms unread | Not cleared | None | DPVO/DROID-SLAM builds unproven | **Uncertain** |
| CameraHMR, TokenHMR, CoMotion, Multi-HMR, Human3R, SMPLest-X/SMPLer-X, GEM-SMPL (old) | Per-image or per-frame; mostly no world path | Free | Local | Non-commercial each | Barred | Varies | Linux-style installs | **No** |
| 4DHumans, DuoMo, PEAR | 4DHumans per-frame; DuoMo claims -16% EMDB world error (CVPR 2026) | Free | Local | 4DHumans MIT code, no checkpoint licence; DuoMo unconfirmed; PEAR needs SMPL/FLAME | Not cleared | None | detectron2 fails on Windows | **Uncertain** |
| [SAM 3D Body + MHR](https://github.com/facebookresearch/sam-3d-body) | Single image, no video | Free | Local | SAM License (trade-control clause); MHR Apache-2.0; gated | Open | `mhr2soma` | Not stated | **Probably** (images) |
| [MediaPipe BlazePose](https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full) | 33 landmarks, positions only; one person | Free | Local | Apache-2.0 weights; consented data | Clean | Needs your own IK | Windows not stated (U) | **Yes** (quality?) |
| RTMPose/ViTPose, MotionBERT | 2D or 17-joint lifters | Free | Local | Apache code; weights unstated; H36M data | Uncertain | None | n/a | **Uncertain** |
| MeTRAbs, VideoPose3D, Sapiens, OpenPose | Mixed | Free | Local | Non-commercial each | Barred | None | n/a | **No** |

### 3C. Kimodo, for contrast

| Option | Quality (evidence) | Cost | Where | Tool licence | Output terms, sold game | UE path | Windows + RTX 5080 | Ship? |
|---|---|---|---|---|---|---|---|---|
| [Kimodo-SOMA-RP v1.1](https://github.com/nv-tlabs/kimodo) (pinned) and SEED | Text/pose/trajectory to 30 fps SOMA; foot skating, no fingers, 10 s max (V*) | Free | Local worker | Code Apache-2.0; weights NVIDIA Open Model License; Llama-3 encoder terms unread | NVIDIA claims no output rights; raw AI output copyrightability unsettled | Already integrated; bake to AnimSequence | Running here; ~3 GB extra VRAM | **Probably** (prefer RP) |
| Kimodo-SMPLX-RP | SMPL-X | Free | Local | R&D licence | Non-commercial | None local | n/a | **No** |
| [HY-Motion](https://huggingface.co/tencent/HY-Motion-1.0) | Text-to-motion | Free | Local | Licence text unread | Unknown | None | 24-26 GB VRAM | **Uncertain** |

**Reading the tables.** Best accuracy is not shippable accuracy. GEM-X's accuracy is close to GVHMR's but its jitter figure is about double (different papers), so plan smoothing. The Epic plugin is the only route with no export step and the only one whose quality nobody has measured. Free tiers are never a safe basis for shipped assets (V*).

## 4. Licensing: what could ship in a sold game

**This is research, not legal advice.** Points needing a lawyer are tagged [LAWYER]. Licence wording below mostly comes from a summarising fetch tool (V*); re-read the live text, and the licence version attached to each checkpoint, before relying on it.

**4.1 SMPL / SMPL-X family.** SMPL, SMPL-X, MANO, STAR, SUPR, SKEL and the AMASS dataset are free for non-commercial research (SMPL-X adds non-commercial education and art). They bar commercial products, commercial services, producing other artefacts for commercial purposes, redistribution, and training neural networks for commercial use ([SMPL](https://smpl.is.tue.mpg.de/modellicense.html); [SMPL-X](https://smpl-x.is.tue.mpg.de/modellicense.html); [AMASS](https://amass.is.tue.mpg.de/license.html); V*). None defines "commercial", mentions games, says who may use outputs, or exempts joint-rotation-only use (V*, absence). The one explicit output-side release is the CC BY 4.0 SMPL-Body subset (mesh, rig, shareable as animated FBX with credit); its page cites a Max Planck patent on the SMPL specification and does not say whether the CC grant covers it ([SMPL-Body](https://smpl.is.tue.mpg.de/bodylicense.html), V*). My reading (E): the restriction attaches to *use* of the model files, so running SMPL, or an estimator that needs SMPL files, in production is the exposure, not shipping a mesh. Treat as unsafe unless the licensor confirms in writing. [LAWYER]

*Commercial route.* Quote-based. Since 20 Feb 2026 Max Planck Innovation licenses SMPL directly; Epic bought Meshcapade's team, not SMPL (V*). Public prices conflict: EUR 2,000/yr Micro and EUR 10,000/yr SME in one search summary, EUR 1,500+ in another note, a reported EUR 124,200 Enterprise R&D price, and a founder blog saying pricing was never public (all U). Ask in writing whether (a) outputs of SMPL-based estimators are covered, (b) estimator weights trained on SMPL/AMASS are covered, (c) scope is per title or per company, (d) the patent is licensed. Estimator weights keep their own terms even then.

**4.2 NVIDIA Open Model License route (GEM-X, SOMA, Kimodo).** GEM-X: Apache-2.0 code; weights under the Open Model License, card says ready for commercial or non-commercial use; about 1 M images and 300 h of video, synthetic renders from NVIDIA in-house mocap plus real visual data, annotated by commercial-compatible models; dataset entry Internal NVIDIA; no SMPL ([card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md), V*). The SOMA body model is Apache-2.0 and ready for commercial use ([SOMA-X card](https://nvlabs.github.io/SOMA-X/stable/model_card.html), V*). The generic Open Model License is perpetual, worldwide, royalty-free but **revocable**; NVIDIA claims no ownership of outputs and makes you responsible for them; rights end if you bypass a guardrail or sue NVIDIA over infringement; there is an indemnity to NVIDIA ([agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/), V*). **Open risks:** (1) unlisted real-world training data; (2) a SAM-licensed component (SAM 3D Body) of unstated role in the attributions; the SAM License has no non-commercial clause but a trade-control/military clause and a reverse-engineering ban ([attributions](https://raw.githubusercontent.com/NVlabs/GEM-X/main/ATTRIBUTIONS.md), V*); (3) ViTPose-family, ViPE and YOLOX weights are unread, and EgoHand hand weights carry separate terms (body-only use avoids them); (4) I read the generic agreement, not a per-model PDF; (5) the older SMPL-based GEM checkpoint (NVIDIA OneWay Noncommercial licence) was reported linked from a Hugging Face page named `nvidia/GEM-X`, so confirm the licence on the exact file you download (V*, flagged by two notes). Kimodo: SOMA-RP is Open Model License and ready for commercial use; SEED variants share the licence but were trained on BONES-SEED (academics or startups under $1M revenue only, no training generative models, commercial licence $480,000); the SMPL-X checkpoint is research-only ([Kimodo repo](https://github.com/nv-tlabs/kimodo); [BONES-SEED licence](https://bones.studio/info/seed-license), V*). Prefer RP for shipping. The project's earlier AI declaration lists the Llama-3-based text encoder's licence as unconfirmed (V, local). [LAWYER]

**4.3 Non-SMPL alternatives.** MediaPipe BlazePose (Apache-2.0 weights, consented data, positions only); MHR (Apache-2.0) and SAM 3D Body (SAM License, gated, image-only); Naver's Anny body model (Apache-2.0, CC0 data; no video estimator trained on it found). Blocked: MeTRAbs ([non-commercial weights](https://github.com/isarandi/metrabs)), VideoPose3D, Sapiens, OpenPose (paid CMU licence, price U) and Ultralytics YOLO (AGPL-3.0; YOLOX, RTMDet or RT-DETR are alternatives, weights provenance unverified). Code, weights and training-data licences are separate layers: MIT code on a lifter says nothing about Human3.6M- or AMASS-trained weights.

**4.4 Does a tool's licence follow its output?** Copyleft code licences generally do not reach a program's output unless it copies substantial parts of the program ([GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html); [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html), V*). Research-only and weights licences restrict *use*, so running non-commercial weights to make commercial assets is the breach path whoever owns the output. Enforceability is contested and untested in court; a Stanford analysis finds it questionable and notes no model creator has sued ([Henderson and Lemley](https://arxiv.org/abs/2412.07066), V* abstract). My reading (E): licensors with licensing programmes (Max Planck/Meshcapade, Bones, OpenPose's CMU) are likelier to pursue than a typical model author, and the SMPL patent is a separate lever. Whether raw machine-generated motion is copyrightable by you is unsettled (U); hand-edited motion plus original footage helps. [LAWYER]

**4.5 Stack to commercially shippable output?**

| Stack | Shippable? | Reason | What would change it |
|---|---|---|---|
| Own-filmed footage, any tool | **Yes** (footage side) | You control ownership and consent by contract; tool licence still applies | Missing performer release |
| GEM-X, body only | **Probably** | Apache + Open Model License, no SMPL; open data/dependency items | NVIDIA written confirmation / a non-commercial dependency |
| Epic plugin, baked clips only | **Probably** (weakest) | First-party, free, local; SMPL-FN parts unexplained; no Epic answer | Epic's written answer |
| Epic plugin runtime models shipped | **No** until Epic answers | Fab EULA 5(b), SMPL-X terms | Epic and counsel |
| Kimodo SOMA-RP | **Probably** | Open Model License, ready for commercial use | Version check, Llama-3 encoder terms |
| MediaPipe BlazePose | **Yes** | Apache-2.0 weights | Quality only |
| SMPL-dependent estimators, no licence | **No** (WHAM, TRAM, 4DHumans: **Uncertain**) | Non-commercial or unresolved weights | Commercial licence plus written scope |
| Same, with a commercial SMPL licence | **Uncertain** | Scope and cost unknown | Written coverage of weights and outputs |
| Paid cloud tools, own footage | **Probably** | Clearest: Uthana, QuickMagic, iClone paid; DeepMotion binary-only | Read full terms |
| Any cloud tool, YouTube footage | **No** | You cannot honestly warrant the upload | Creator's written permission |

**Epic's side.** The solved animation looks clean under Epic's terms: MHA output is your own Product, a royalty-free Non-Engine asset, usable outside Unreal ([MetaHuman licence](https://www.metahuman.com/license); [UE EULA](https://www.unrealengine.com/eula/unreal), V). The EULA's consent clause covers only Epic *cloud* features, which local solves do not trigger; no Epic text requires footage ownership or performer consent for local processing (V, absence). The metahuman.com FAQ still carries the old AI sentence the EULA removed (stale). Open: the Fab Standard License says projects incorporating a plugin may only be distributed as Engine Tools ([Fab EULA](https://www.fab.com/eula), V); whether a game containing *baked output* incorporates the plugin is unaddressed [LAWYER]. A developer's query to Epic about shipping the plugin's runtime models got no Epic reply ([thread](https://forums.unrealengine.com/t/licensing-question-shipping-metahuman-animator-markerless-motion-capture-runtime-models-in-a-steam-game/2839692), U). The listing says Allows usage with AI: No, and this project enables MetaHuman toolsets that let an AI agent drive ingest, solve and export through MCP (V, local); whether that is use in a generative-AI program is unaddressed [LAWYER].

## 5. The YouTube question and footage rights

**Short answer: do not use YouTube footage for a game you may sell, except per clip with the creator's written permission.** The shipped animation is the low-risk part; the download, the upload to vendors and the specific clip are the risks.

**5.1 YouTube Terms.** The Terms (dated 15 Dec 2023; re-read the live page) bar accessing, reproducing or downloading Content except as the Service authorises or with prior written permission from YouTube and, where applicable, the rights holders; bar circumventing copy-restriction features and automated access; and limit viewing to personal, non-commercial use. There is no analyse-and-delete carve-out and no machine-learning clause ([Terms](https://www.youtube.com/t/terms), V*). YouTube says it will block scrapers ([blog, Sept 2024](https://blog.youtube/news-and-events/responsible-ai-tools/), V*); against a small developer, expect account or IP blocking (E).

**5.2 DMCA section 1201.** Circumventing a measure that controls access to a protected work is unlawful without the owner's authority, plaintiffs argue fair use does not answer it, and any injured person can sue for statutory damages of $200-$2,500 **per act of circumvention** ([17 USC 1201](https://www.law.cornell.edu/uscode/text/17/1201); [1203](https://www.law.cornell.edu/uscode/text/17/1203), V*). The RIAA used it against youtube-dl in 2020; GitHub reinstated the repo after review, a platform decision, not a ruling ([GitHub blog](https://github.blog/news-insights/policy-news-and-insights/standing-up-for-developers-youtube-dl-is-back/), V*). A Connecticut court dismissed Yout's declaratory claims in 2022; the appeal was argued Feb 2024 and I found no decision (U). A creator suing a user who ripped clips for reaction videos survived dismissal on the 1201 claim in *Cordova v. Huneault* (N.D. Cal., reported 5 Feb 2026): the court accepted that YouTube's rolling cipher plausibly controls access. This is pleading-stage only, and whether a ripping tool or screen recording was used is a fact question ([TorrentFreak](https://torrentfreak.com/ripping-clips-for-youtube-reaction-videos-can-violate-the-dmca-court-rules/), U). Creators have also pleaded 1201 against NVIDIA over YouTube scraping, with no merits ruling found (U). **Exposure scales with volume:** 1,000 downloads at the statutory minimum is $200,000 on paper (E). Whether stream capture avoids 1201 is unresolved. [LAWYER]

**5.3 CC BY on YouTube.** The uploader may apply CC BY only to what they have the right to license; videos with a Content ID claim cannot carry it ([YouTube Help](https://support.google.com/youtube/answer/2797468), V*). CC BY permits commercial adaptation with credit ([CC BY 3.0](https://creativecommons.org/licenses/by/3.0/legalcode), V*; YouTube's version unverified). Limits: copyright only (no likeness clearance); embedded music and clips are not cleared; it does not change YouTube's download wording; labels can be wrong (a CC BY Blender film was re-uploaded by a company that struck a licensee, U). No case law found on whether a CC licence supplies the owner's authority for 1201, or whether motion extraction is an "Adaptation". If used: credit title, author, URL, licence and a modified note; keep a dated screenshot. [LAWYER]

**5.4 Copyright in footage vs movement.** Skeleton data does not reproduce pixels, sound or editing. Single movements, social and line dances, simple routines, athletic manoeuvres and functional motion are not registrable; complex fixed human choreography is ([Compendium ch. 800](https://www.copyright.gov/comp3/chap800/ch800-performing-arts.pdf), V*). *Hanagami v. Epic* (9th Cir., 1 Nov 2023) held choreography is protected through selection and arrangement of unprotectable elements, even when short; it settled in Feb 2024 with no infringement ruling ([opinion](https://cdn.ca9.uscourts.gov/datastore/opinions/2023/11/01/22-55890.pdf), V*; settlement U). Generic motion (walk, idle, punch, sword stance): very low risk. Social dance, simple routines: low. A choreographed routine copied closely: real risk. Martial-arts forms: unsettled. Retargeting does not reliably launder a copied sequence, and no court has addressed motion extracted from video. [LAWYER]

**5.5 Likeness, vendors, platforms.** Publicity and digital-replica laws (California AB 2602 and AB 1836, New York's Dec 2025 laws, Tennessee's ELVIS Act) turn on a realistic, readily identifiable depiction (law-firm summaries, U); generic motion on an unrecognisable fictional character very unlikely qualifies (E). NO FAKES cleared Senate Judiciary on 18 June 2026; no floor vote found (U). Escalators: a named celebrity source, a signature move, a lookalike character, a deceased person. *Cloud vendors:* Move, DeepMotion, QuickMagic, Uthana, Reallusion, Plask and Rokoko all put upload rights on you, and QuickMagic bars another person's private video (V*); uploading a stranger's clip is a representation you could not honestly make. Local tools avoid that representation but not the Terms or 1201. *Steam* asks about pre-generated AI content that ships to players; Valve revised the form in Jan 2026 (survey V*, revision U) ([Steamworks](https://partner.steamgames.com/doc/gettingstarted/contentsurvey)); video-derived motion is ML-processed, so a one-line disclosure is the cautious choice (E). Valve's Distribution Agreement is not public. *itch.io* makes you warrant you have the rights, indemnify it, and tag generative-AI materials ([Terms](https://itch.io/docs/legal/terms); [guidelines](https://itch.io/docs/creators/quality-guidelines), V*). The *2026 Epic AI MegaJam* rules (updated 26 Oct) allow AI content and sourced assets if noted (not scored) and require cleared rights; nothing mocap-specific; pages 1-9 and 12-19 unconfirmed ([rules](https://epicgames.ent.box.com/s/a7xcgl07fqoieeb99sjtd3juhj4agc4z), V). Selling the entry later makes the stricter analysis here apply.

**5.6 Risk ladder, lowest to highest**

| Rung | Source | Main exposure | Confirm |
|---|---|---|---|
| 1 | Own-filmed | People appearing; performing someone else's routine | Releases; no third-party choreography |
| 2 | Hired performer, written agreement | Ownership, scope of use, AI/ML consent, union status | Assignment language [LAWYER] |
| 3 | CC0 / public-domain footage | Provenance; people and music in frame | Provenance and releases |
| 4 | Licensed stock footage | AI/ML and data-extraction clauses; no model release | Written vendor permission |
| 5 | CC BY YouTube footage | Uploader rights, attribution, access route | Creator's written permission |
| 6 | Arbitrary YouTube footage, analysed and discarded | Terms breach; 1201; transient copy; choreography; likeness; platform warranty | Do not |

Two notes disagree on rungs 4-5: one puts licensed stock above CC BY YouTube (assuming a bought licence with written permission), the other the reverse (standard licences carry AI/ML clauses). I rank stock above CC BY only with written vendor confirmation.

**Real vs theoretical.** *Mostly theoretical:* copyright infringement by generic pose data on a fictional character, and by a transient analysis copy (a decent US fair-use argument, weaker in the EU and UK; UK commercial text-and-data-mining has no exception). *Real but modest for a handful of clips:* Terms enforcement against your accounts and IPs. *Meaningful and scaling with volume:* the 1201 theory, the cloud warranty, and choreography or signature-move copying. A claim over process could cost real money in discovery and takedown friction even if it failed. A provenance sheet per clip (URL, date, licence-label screenshot, what motion went where) and a deletion schedule help every time (E).

**Questions for a lawyer**

1. Does running pose estimation on YouTube videos fetched by an automated tool create 1201(a) exposure for a small studio, given *Cordova* and the pending Yout appeal? Do download, stream and screen capture differ?
2. Does a creator's CC BY licence supply the owner's authority for 1201 and permission under YouTube's Terms? Which CC version, and what credit text?
3. Is a transient analysis copy, destroyed after extracting joints, fair use in the US, and text and data mining under EU Article 4 or UK s.29A?
4. Where is the line between generic motion and protectable choreography for our clip rules, and does retargeting reduce *Hanagami*-type risk?
5. Could distinctive motion from an identifiable person be a likeness or digital replica (California, New York, Tennessee, NO FAKES)?
6. Performer agreements: assignment, consent to retargeting and AI/ML processing, AB 2602 specificity, union and moral-rights issues.
7. What do Valve's Distribution Agreement, itch.io's terms and the MegaJam rules require for video-derived animation?
8. Do the SMPL terms reach estimator outputs, estimator weights or joint-rotation-only use, and does the patent matter?
9. Does baked animation from the Epic plugin incorporate it under Fab EULA 5(b)? Is an AI agent driving it use in a generative-AI program?
10. Is a provenance log plus deletion schedule adequate, and should we get an opinion letter or media-liability cover?

### 5.7 Commercially clean sources

**Own filming (cleanest).** Capture checklist (general guidance, U): tripod and locked exposure; subject fills 60-80% of frame height, head to feet visible throughout; one performer; plain contrasting background, flat visible floor; fitted clothing; 60 fps with a fast shutter (Epic asks for HD/4K at 60 fps, H.264 CRF 18 or better); no zoom, no wide-angle or fisheye lens; A-pose at the start; three repeats per action; a real-length prop for sword work; shoot static, which also skips the hardest builds (visual odometry). **Performer release checklist** (general guidance; a lawyer should draft it): consent to recording and to deriving motion data and a skeleton; assignment or exclusive perpetual licence of recordings, motion data and results, worldwide, all media; explicit commercial game use including sale; consent to ML/AI and cloud processing; flat fee, no credit, royalty or approvals, no moral-rights claims; right to alter and combine; over 18; retention, deletion and biometric-data consent where local law requires; a signed copy per session.

**Hired performer.** About $250/day non-union; SAG-AFTRA's 2026 interactive rate sheet is cited at $374.53-$907.96 per 8 hours plus 17% (U). **CC0 / public domain:** copyright-clean, but people, logos and music are separate and framing is rarely usable.

**Licensed libraries (shipped inside the game only; no loose redistribution; mostly no ML training).** Fab Standard License: commercial use, no standalone redistribution (V*); Epic's GASP is UE-only, wording second-hand (U). Mixamo: games allowed per an Adobe-hosted community FAQ by a non-staff user; Adobe's own terms unread (U). MoCap Online: games allowed, AI training needs a permit (V*). Truebones, Rokoko Motion Library: reported fine (U). ActorCore: Standard License if packaged in the application, extra limits on end-user-extractable deployment (V*). CMU database: reported fine without resale, official page unread, sources conflict (U). **Do not use** AMASS-derived sets or BONES-SEED. A model trained on library clips would breach their ML clauses; using the clips as game content is not training.

**Costs and hybrid.** Per 1,000 s of single-person footage cloud tools cost about $25-$130 (Rokoko $24-$28; QuickMagic Pro $40-$50; Plask $36-$50; Uthana $50-$60; Flow Studio $90-$95; DeepMotion about $117, U); Move One $267-$533. Inertial suits: Rokoko bundle $4,495; Xsens hardware from $4,590 plus software from $3,790/yr, with an Indie programme for revenue up to $550,000 (V*). Optical studio: about $1,500-$3,300 a day plus cleanup that can double the bill (U). A suit pays off only beyond about 15-20 minutes of bespoke motion or finger work (E). Use own footage for swordplay, digging, carrying and prop interaction; Kimodo SOMA-RP for locomotion, idles, conversation and crowds; library clips for common actions; gloves or keyframes for fingers.

**Cleanest to grayest**

1. Own filming or own mocap hardware, release signed.
2. Hired performer under a written agreement.
3. Epic Fab / GASP content.
4. Mixamo, MoCap Online, Truebones, Rokoko Motion Library, ActorCore (per-licence conditions).
5. Kimodo SOMA weights (generative; disclose as AI).
6. Paid tool terms with own footage (Uthana, QuickMagic, Cascadeur Indie/Pro).
7. CMU database (official terms unread).
8. CC0 / public-domain footage.
9. CC BY footage with attribution and the creator's permission.
10. Pexels / Pixabay footage (no model-release warranty).
11. Licensed stock and Internet Archive footage (avoid without written permission).
12. Arbitrary YouTube footage.
13. Research datasets (AMASS family, BONES-SEED): clearly out.

## 6. Fit with this project

**Cast and skeleton.** The Hero's body mesh sits on the IvenRook copy of `metahuman_base_skel`: 342 bones, bone 0 `root`, then `pelvis`; four other copies exist and clips are bound to one copy (V, local). `root` must stay bone 0: a save-all on 14 Nov dropped it and T-posed half the cast, so never save the skeleton from an import job, and check bone 0 and the 342 count after every import. The game uses CharacterMovement and a native anim instance with slot playback; every Hero clip so far is in place with root lock (`enable_root_motion=False`, `force_root_lock=True`), so movement from video must become a separate trajectory. As far as the scripts show, no animation FBX/BVH has been imported in this project.

**Kimodo and SOMA assets.** Kimodo is an Epic-shipped experimental engine plugin pinned to `Kimodo-SOMA-RP-v1.1`: 30 fps on a 31-bone skeleton (synthetic `root` plus 30 SOMA joints, no fingers), asset `/Kimodo/Characters/Soma/soma_neutral`. It has no BVH/NPZ/FBX reader or writer and bakes through `BakeToAnimSequenceAsync`, which needs the live editor with Sequencer focused (V, local). *Saved* retarget assets date from **14 Nov**: `/Game/Characters/Hero/Animation/CombatCasts/Rigs/IK_Soma_Combat` and `RTG_SomaToHero` (SOMA to Hero), plus `RTG_MannequinToHero` and `IK_Hero_Source` in `Characters/Hero/Animation/Locomotion/`, target rig `IK_Hero_Body`; existing SOMA clips sit in `Characters/Hero/Animation/CombatCasts/Soma/`. **Today's sword test did not use them:** it used AnimGenOffline's transient auto-generated IK Rigs (editor log: `soma_neutral` template Rokoko to `SKM_MHC_Hero_BodyMesh` template UE5 Mannequin, six pinned chain patches), so no IK Rig or Retargeter asset was created; the takes are `/Game/Animation/KimodoTests/AS_Hero_KimodoSword_Take1..3` (5.5 s, 342 tracks, 30 fps). The saved assets were read from string tables only. Known issues: no fingers; the wrist is not sword-aware.

**What GEM-X's SOMA output would reuse.** `RTG_SomaToHero` unchanged, if the clip arrives as an AnimSequence on the SOMA skeleton asset. The gap (E): GEM-X writes `.pt` files with no BVH/FBX export and an undocumented tensor layout; Kimodo's upstream `motion_to_bvh` and `post_process_motion` exist in NVIDIA's docs, but Epic's vendored copy says its CLI and converters are not shipped, so the upstream package would need installing. The UE soma asset has 30 joints while GEM-X and Kimodo BVH use 77, so the glue must emit the 30-joint subset plus synthetic root in the plugin's rebased rest convention, or import a 77-joint mesh and build a new IK Rig. Whether GEM-X's SOMA and Kimodo's `somaskel77` share rest pose and axes is documented nowhere; the notes call this the biggest integration unknown. Other skeleton copies were not tested against `RTG_SomaToHero`.

**Machine.** RTX 5080, 16,303 MiB, driver 610.88 (Blackwell, sm_120). The editor plus Kimodo worker hold about 11-14 GB; about 4 GB is free (1 GB while another session generated), and free physical memory was 2.8-3.6 GB of 31.1 GB. The CPU is a Ryzen 7 9700X with 8 physical cores; Epic's hardware page asks for at least 16 physical cores and 32 GB RAM (E: below guidance, so expect a slow or failed plugin solve). System Python is 3.14 only; uv holds managed CPython 3.11 and 3.13 (the pipeline note assumed 3.12, which would need a download). `Intermediate/PipInstall` pins torch 2.5.1+cu124, which cannot run on this GPU and is rewritten at every editor start; `KimodoPython` (torch 2.8.0+cu128) belongs to the worker. Keep the video stack in a new, separate cu128 environment. No ffmpeg on PATH (PyAV bundles libraries), no WSL distribution, and Blender 4.5.5 only as a portable build in a Codex temp folder that may vanish. GEM-X needs Python 3.10+ and PyTorch 2.10+ ([repo](https://github.com/NVlabs/GEM-X)); a Windows app measured 3.48 GiB peak on an RTX 5090 for a 9.8 s clip, while the README states no VRAM (V*).

**Automation constraints.** One long-lived shared editor with in-editor Python; heavy work belongs outside it, handing off through `Intermediate/VideoToAnim/` (git-ignored; `.mp4`, `.bvh`, `.npz` are not LFS-tracked). A separate `UnrealEditor-Cmd` import is only safe with the shared editor closed, and the path has spaces, so use a space-free shim. Your rules: a closed editor means the build train may be running (no Source edits or UBT compiles); claim `PIE_LOCK` only on the orchestrator's go; never `StopPIE` unless the lock is free or yours; never save a dirty `metahuman_base_skel`.

**FBX/BVH import rules (blender-to-unreal skill).** Name the Blender armature object exactly `root` (`Armature` drops the root bone; other names replace it); metres, `FBX_SCALE_NONE`, `global_scale=1.0`; `axis_forward='-Z'`, `axis_up='Y'`, `add_leaf_bones=False`; clip FBX with `bake_anim=True`, all bones, forced start/end keys; scene fps set to the sibling library's rate (30 here); import with `automated=True`, `replace_existing=True`, the existing skeleton, `import_mesh=False`, `import_uniform_scale=1.0`. Gate every clip: strip the armature-object track, track count equals a sibling's (342), `root` yaw equals the sibling's, length/fps check, save landed, no bone fling, metrics checked on a known-good control, visual check. Which FBX importer (Interchange or legacy) 5.9 uses is unconfirmed; the project's scripts use the legacy one.

## 7. Proposed pipeline

```
 own footage (tripod, 60 fps, one performer)  +  provenance log + release
   -> [1 prep]   trim 5-20 s, one person, contact sheet; derive constant 30 fps for GEM-X
   -> [2 pose + world motion]
        A: GEM-X  motion-video --camera-mode static --postprocess -> motion.pt (SOMA, world space)
        B: Epic plugin: Live Link Hub Mono Video Ingest -> MetaHuman Performance (body only) -> Process
   -> [3 cleanup] contacts -> foot-skate pass -> quaternion filter -> ground/scale -> in-place + trajectory -> loops
   -> [4 retarget]  A: glue to 30-joint SOMA + root -> RTG_SomaToHero      B: Export "Existing Skeleton"
   -> [5 UE AnimSequence on metahuman_base_skel]  342 tracks, bone 0 root, 30 fps, root lock, in place
   -> [6 QA metrics + visual review on the Hero] -> Hero slot (DefaultSlot / spell slot)

 Kimodo (text/pose/trajectory) -> existing bake -> same RTG_SomaToHero -> same QA   (primary for locomotion, idles, talk)
```

Effort figures are my estimates (E). Assumptions: one developer with an AI coding agent; Kimodo and the SOMA retarget already work; Blender and UE Python are scriptable; the GPU is free of the editor while jobs run; weights and Hugging Face access are in hand; Windows-native first. Ranges run from "goes well" to "typical friction".

| Stage | Cautious choice (A: GEM-X; B: Epic plugin) | Alternative | In to out | Main risks | Effort (E) |
|---|---|---|---|---|---|
| 0 Environment | A: new uv venv on CPython 3.11/3.13, torch 2.10+ cu128, GEM-X, ffmpeg binary. B: install Fab plugin, DX12 RHI | WSL2 (no distro; Blackwell reports mixed); third-party RGB MoCap Windows app bundles GEM-X (unvetted, FBX output) | none to env | Wheels, Windows builds; 5.9 support untested; 8-core CPU | A 0.5-1 d; B 0.25-0.5 d |
| 1 Capture and prep | Own tripod footage at 60 fps; trim 5-20 s; constant 30 fps copy for A; mp4/mov for B | Hired performer; footage with written permission | video to clean clip | Partial framing, a second person, 29.97/30 fps failures | 0.5 d |
| 2 Pose and world motion | A: GEM-X static, body only, `--postprocess`. B: body only (Facial Tracking off, Body Tracking on, Head Movement Mode Disable) | GVHMR/ExMR/FlowHMR only with commercial licences | clip to SOMA `.pt` / Performance | Limb swap, hip rotation, heel lift (GEM-X issues, V*); B solve time, crashes | A 1-2 d; B 1-3 d |
| 3 Cleanup | GEM-X postprocess; Kimodo `post_process_motion` (needs contacts); quaternion filter (1 euro or Savitzky-Golay); leg IK | Cascadeur; Control Rig | rough to clean clip | Untested on external SOMA data; drift; loops are custom (U) | 4-7 d incl. root, loops |
| 4 Retarget | A: glue (SOMA FK to local rotations, 30-joint subset) then `RTG_SomaToHero`. B: Existing Skeleton export | Blender SMPL-style path (SMPL licence) | SOMA clip to Hero clip | Rest-pose/axes mismatch (largest unknown) | A 1-3 d; B ~0 |
| 5 UE import | Python `AssetImportTask` on the existing skeleton, or a direct AnimSequence build; root lock | Closed-editor `UnrealEditor-Cmd` | FBX to AnimSequence | Importer differences; skeleton save accident | 1-2 d |
| 6 QA | Section 9 metrics, preview render, per-clip report | Manual only | clip to pass/fail | Thresholds need calibrating | 1.5-3 d |
| 7 Hands (optional) | A: GEM-X hand model (EgoHand licence check); keyframes or gloves | HaMeR (MANO non-commercial) | clip to fingers | Licences; hand jitter | +3-6 d |

**Totals.** Path A, a reviewed batch MVP: about 10-20 working days (the pipeline note's range). Path B: about 3-6 working days to script and QA (my estimate, no source). Per-clip human review (5-10 minutes) dominates at scale.

**Where Kimodo stays primary.** Locomotion, idles, conversation, crowds and anything needing no real performer; video-derived clips are for prop interaction and signature actions. A design option (E, untested): feed video-derived keyed poses and a root trajectory to Kimodo as constraints so the model fills and cleans the motion.

**Face (optional).** MetaHuman Animator solves face from the same mono footage (UE 5.6+, Performance asset on Monocular Footage, no Identity); face and body are solved independently and merged in Sequencer. For voiced lines, audio-driven animation (shipped Speech2Face; head motion, blinks, mood) needs no video and fits your designed voices (V; doc V*). MediaPipe Face Landmarker's 52 blendshape scores are a lightweight alternative, mapping and quality unverified (U); avoid FLAME-based trackers (non-commercial).

## 8. Recommendation

**Build a narrower version:** a small own-footage path, gated by the proof of concept, kept as a supplement to Kimodo and libraries rather than a general mocap system.

*Why.* The licence evidence leaves two plausibly shippable video routes and no cleared one; the best-accuracy models cannot ship without commercial licences of unknown price and scope. The project has no capture assets, and Kimodo's gaps (fingers, swordplay) are where small amounts of own-filmed motion help. A full batch MVP costs 10-20 working days (E) for a modest amount of bespoke motion, while the Epic route is nearly free to try and writes MetaHuman-skeleton animation directly.

**What not to do.** Do not scrape or download YouTube videos, do not upload third-party clips to cloud tools, and do not run SMPL-dependent models (GVHMR, ExMR, FlowHMR, PromptHMR, WHAM, TRAM) in production without a commercial licence. A YouTube pipeline adds Terms, 1201, vendor-warranty and choreography exposure that scales with clip count, to save the cost of filming a few clips. If YouTube ever matters, use a single clip with the creator's written permission, a local tool and counsel's sign-off.

**What to do instead.** Film your own clips; run the two-route proof of concept; send the written questions below; keep a provenance log (licence version and download date per checkpoint); disclose ML-assisted motion on Steam and itch.

| Gate | Evidence | If yes | If no |
|---|---|---|---|
| G1 PoC quality | Section 9 metrics pass on 2 of 3 clips in one route | Small build | Stop; libraries, Kimodo, hand keying |
| G2 GEM-X licence | NVIDIA confirms data provenance, the SAM-licence part and the exact checkpoint licence | GEM-X can ship | Drop GEM-X |
| G3 Epic plugin | Runs on 5.9 and this CPU; usable quality; Epic answers on SMPL-FN and baked output | Primary or second source | Drop it |
| G4 Lawyer | Reads SMPL, performer-release and Fab 5(b) questions | Ship | Restrict to the cleanest rungs |
| G5 Volume | Bespoke motion needed exceeds ~15-20 minutes or needs fingers | Consider a suit or performer day | Hand-key and library |
| G6 SMPL quality | Owner wants GVHMR-class accuracy | Seek Max Planck/Meshcapade and ZJU licences (price unknown) | Skip |

**Questions to send.** NVIDIA: training-data provenance, the SAM-licence component, ViTPose/ViPE/YOLOX weights, commercial use of outputs in a shipped game. Epic (licensing form): licence of the SMPL-FN components, shipping baked output, performer consent for local processing. Max Planck Innovation: coverage of estimator outputs and weights.

## 9. Proof-of-concept plan for the owner to approve

About one day (E).

| # | Step | Who | Editor / PIE lock? | Time |
|---|---|---|---|---|
| 1 | Film three own clips: a 10-15 s walk/idle, a sword swing or lunge, a dig or carry. Tripod, 60 fps, one performer, full body, fitted clothes, A-pose at start; signed release if anyone else appears | Owner | No | 1 h |
| 2 | Prep: trim, constant-fps copies, contact sheets; provenance log | Claude | No | 1 h |
| 3 | New uv environment (existing CPython 3.11/3.13, torch 2.10+ cu128), install GEM-X; prove `torch.cuda` with a real tensor op on the 5080 | Claude | No; editor closed or Kimodo unloaded | 1-2 h |
| 4 | Run GEM-X static with `--postprocess` on the clips; log seconds and peak VRAM | Claude | No (GPU exclusive) | 1 h |
| 5 | Inspect `motion.pt`; write glue to a 30-joint SOMA clip; check in portable Blender | Claude | No | 2-4 h |
| 6 | Import, retarget with `RTG_SomaToHero`, bake an AnimSequence on the Hero skeleton, set root lock, run integrity gates | Claude | **Editor**; PIE lock only if reviewing in PIE | 1-2 h |
| 7 | Epic baseline: install the plugin, ingest the same clips, solve body only, export Existing Skeleton | Claude | **Editor** (heavy; Kimodo unloaded) | 1-3 h |
| 8 | Score both routes; render side by side on the Hero | Claude, then owner | Editor or capture | 1 h |
| 9 | Decide against gates G1-G3 | Owner | No | 15 min |

**Approvals needed.** (1) Downloads: GEM-X weights (with the licence click-through), an ffmpeg binary, the upstream Kimodo package if its export and post-process helpers are wanted. (2) Installing the Epic plugin from Fab. (3) Use of the shared editor, including closing it for GPU work. (4) Drafting the NVIDIA, Epic and lawyer questions. **Needs.** Run GPU-heavy steps 3-5 first with the shared editor closed (it shares VRAM and RAM, and closing it may collide with the build train, so the owner or orchestrator must say when), then open it for 6-8. No YouTube footage, no Source edits; save only the new AnimSequence packages, never the skeleton.

**Pass/fail metrics.** The notes give no thresholds; these starting values are mine (E), to be calibrated against a control (an existing Hero Walk/Jog clip and Kimodo Take3).

| Metric | Pass |
|---|---|
| Foot skate in planted-foot frames | At most 1.5x the control's, or about 3 cm drift per planted interval |
| Jitter (hand, foot, head frame-to-frame acceleration) | At most 1.5x the control's; no pops |
| Root drift, walk-and-return clip | Return-to-start error at most 5% of path length |
| Integrity | 342 tracks, bone 0 `root`, 30 fps, length = frames/30, zero quaternion flips, no bone fling |
| Visual review on the Hero | Owner rates each clip usable / at most 30 minutes of cleanup / unusable; pass needs 2 of 3 clips at "at most 30 minutes" in one route |
| Throughput | Seconds per clip and VRAM peak recorded |

**Cost.** $0 in licences and cloud; owner's time about 1-2 hours. Optional: $25-$60 for one paid cloud comparison on own footage (Uthana or QuickMagic Pro).

**Risks.** The GEM-X glue is the least certain step and may spill to day 2; GEM-X may not run natively on Windows or the 5080 (no source reports it); the Epic plugin may not work on 5.9, may be slow on 8 cores, or may crash (one 5.8.2 RTX 5070 report); shared-editor state (skeleton save, PIE lock, train window).

## 10. Unknowns and caveats

**Could not verify:** GEM-X `.pt` tensor layout and exact training data; GEM-X on native Windows or an RTX 5080 (no model has a 5080 benchmark); the Epic plugin on UE 5.9 in practice, its accuracy, camera limits and multi-person behaviour; which body-model licence covers its SMPL-FN components; Steam's Distribution Agreement and current form wording; stock-footage licence texts; Epic's GASP terms; CMU's and Adobe's Mixamo terms; Move One tier rights after the Vicon deal; Autodesk output terms; Cascadeur's EULA; SMPL commercial prices and scope; HY-Motion and Llama-3 licence text; Yout, SerpApi and NVIDIA case status after April 2026; the text of the California, New York and Tennessee laws; YouTube's CC version; whether a CC licence supplies 1201 authority; copyrightability of raw AI motion.

**Evidence limits.** Most commercial, open-model, licence, clean-source, law and pipeline items were read through a summarising fetch tool (V*): quotes are pointers, not verbatim text, and every licence needs a live re-read. Law-firm and press summaries (likeness statutes, NO FAKES, Fortnite cases) are (U). Quality evidence is vendor claims, author benchmarks and one maintainer's notes.

| Where the notes disagree | Treatment |
|---|---|
| Fab listing licence: Standard License (browser read) vs blank (scrape) | Used the browser read; re-check |
| Plugin vs Meshcapade: one search summary says linked; Epic pages and Digital Production do not | Unconfirmed (U) |
| Meshcapade shutdown: 18 Apr (one aggregator) vs no notice by Aug | Unverified either way |
| SMPL commercial price: EUR 2,000 / 1,500+ / 124,200 | All (U); ask for a quote |
| `nvidia/GEM-X` name: older GEM-SMPL checkpoint linked there; card now describes GEM-X | Confirm licence on the downloaded file |
| GEM-X VRAM: README states none; an app measured 3.48 GiB on a 5090 | Used the measurement, caveated |
| Python: pipeline note assumed 3.12; local audit shows 3.11 and 3.13 via uv | Use what exists |
| GVHMR Windows build: issue #23 needed VS2019; a port used VS2022 with CPU-only pytorch3d | Unresolved |
| Stock vs CC BY rank: two notes order them oppositely | Depends on written vendor permission |
| Cascadeur video mocap (vendor lists it, one outlet denies it); MegaJam/Steam pages (one note read, one could not); iClone, Rokoko and Move One prices and credits; CMU licence | Ranges shown; re-read at source |

## 11. Sources

**Epic, UE 5.9, MetaHuman**
- [UE 5.9 release notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-9-release-notes), updated 19 Nov 2026; [Animation from Mono Video Capture](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine); [Import footage](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-01-import-your-footage-in-unreal-engine); [Process and export](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-02-process-and-export-your-animation-in-unreal-engine); [Video capture guidelines](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-video-capture-guidelines-in-unreal-engine); [Hardware requirements](https://dev.epicgames.com/documentation/metahuman/metahuman-hardware-requirements-in-unreal-engine); [MetaHuman 5.8 release notes](https://dev.epicgames.com/documentation/metahuman/metahuman-5-8-release-notes-in-unreal-engine); [Audio-driven animation](https://dev.epicgames.com/documentation/metahuman/audio-driven-animation)
- [MetaHuman 5.6 release](https://forums.unrealengine.com/t/metahuman-5-6-release/2539165), 3 Jun 2025; [Markerless plugin thread](https://forums.unrealengine.com/t/epic-games-metahuman-animator-markerless-motion-capture-plugin/2729293); [Plugin licensing thread](https://forums.unrealengine.com/t/licensing-question-shipping-metahuman-animator-markerless-motion-capture-runtime-models-in-a-steam-game/2839692), Oct 2026; [Fab listing](https://www.fab.com/listings/4095b8e0-3eff-44f1-acb4-cb40b99228b9); [Fab EULA](https://www.fab.com/eula); [UE EULA](https://www.unrealengine.com/eula/unreal); [EULA change log](https://www.unrealengine.com/eula-change-log/unreal); [MetaHuman licence](https://www.metahuman.com/license)
- [Digital Production, 23 Jun 2026](https://digitalproduction.com/2026/06/23/metahuman-gets-markerless-mocap/); [80.lv, 24 Feb 2026](https://80.lv/articles/ai-motion-capture-startup-meshcapade-now-part-of-epic-games)

**Commercial tools**
- Move AI: [BusinessCloud, 9 Oct 2026](https://businesscloud.co.uk/news/cost-cutting-oxford-metrics-agrees-cut-price-deal-for-move-ai/); [Move One EULA](https://www.move.ai/move-one-app-eula); [pricing](https://docs.move.ai/knowledge/move-one-pricing)
- Rokoko: [Vision 3.0](https://www.rokoko.com/insights/introducing-rokoko-vision-3-0); [Vision](https://www.rokoko.com/products/vision); [pricing](https://www.rokoko.com/pricing/); [terms](https://www.rokoko.com/studio-term-of-use); [monocular AI essay, Oct 2025](https://www.rokoko.com/insights/the-future-of-motion-capture)
- [DeepMotion FAQ](https://www.deepmotion.com/faq); [DeepMotion terms](https://www.deepmotion.com/terms-of-use); [QuickMagic pricing](https://www.quickmagic.ai/Pricing); [QuickMagic agreement](https://docs.quickmagic.ai/docs/agreement.html); [Plask terms](https://plask.ai/docs/100002); [Uthana pricing](https://uthana.com/pricing); [Uthana terms](https://uthana.com/terms); [Flow Studio news, 12 Aug 2025](https://adsknews.autodesk.com/en/?p=53687); [iClone Video Mocap](https://www.reallusion.com/iclone/video-mocap); [Reallusion AI Service EULA](https://www.reallusion.com/Content/EULA/AI-Service.htm); [Cascadeur plans](https://cascadeur.com/plans); [Radical, CG Channel](https://www.cgchannel.com/?p=175200)

**Open models**
- [GVHMR](https://github.com/zju3dv/GVHMR) and [paper](https://arxiv.org/html/2409.06662); [Windows port](https://github.com/PS12007/video-to-humanoid-mimicry); [WHAM](https://github.com/yohanshin/WHAM); [TRAM](https://github.com/yufu-wang/tram); [PromptHMR](https://github.com/yufu-wang/PromptHMR) and [paper](https://arxiv.org/html/2504.06397); [FlowHMR](https://github.com/flowhmr/flowhmr) and [paper](https://arxiv.org/html/2610.03691v1); [ExMR](https://github.com/twehrbein/ExMR); [CoMotion](https://github.com/apple/ml-comotion); [4DHumans](https://github.com/shubham-goel/4D-Humans); [RGB MoCap app](https://github.com/toyxyz/toyxyz_RGBMocap) and [user guide](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/docs/USER_GUIDE.md); [SAM 3D Body](https://github.com/facebookresearch/sam-3d-body); [MediaPipe BlazePose card](https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full); [MeTRAbs](https://github.com/isarandi/metrabs)

**NVIDIA GEM-X, SOMA, Kimodo**
- [GEM-X repo](https://github.com/NVlabs/GEM-X); [model card](https://huggingface.co/nvidia/GEM-X/blob/main/README.md); [attributions](https://raw.githubusercontent.com/NVlabs/GEM-X/main/ATTRIBUTIONS.md); [demo doc](https://github.com/NVlabs/GEM-X/blob/main/docs/DEMO.md); [GENMO/GEM](https://github.com/NVlabs/GENMO); [SOMA-X card](https://nvlabs.github.io/SOMA-X/stable/model_card.html); [SOMA-X tools](https://github.com/NVlabs/SOMA-X/blob/main/docs/tools.md)
- [Kimodo repo](https://github.com/nv-tlabs/kimodo); [Kimodo output formats](https://research.nvidia.com/labs/sil/projects/kimodo/docs/user_guide/output_formats.html); [post-processing](https://research.nvidia.com/labs/sil/projects/kimodo/docs/api_reference/post-processing.html); [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/); [BONES-SEED licence](https://bones.studio/info/seed-license); [Bones licensing](https://www.bones.studio/licensing)

**SMPL family and licence theory**
- [SMPL](https://smpl.is.tue.mpg.de/modellicense.html); [SMPL-X](https://smpl-x.is.tue.mpg.de/modellicense.html); [SMPL-Body](https://smpl.is.tue.mpg.de/bodylicense.html); [AMASS](https://amass.is.tue.mpg.de/license.html); [Max Planck Innovation release, 20 Feb 2026](https://www.eurekalert.org/news-releases/1117236); [GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html); [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html); [Henderson and Lemley](https://arxiv.org/abs/2412.07066)

**YouTube and footage rights**
- [YouTube Terms](https://www.youtube.com/t/terms); [YouTube blog, Sept 2024](https://blog.youtube/news-and-events/responsible-ai-tools/); [YouTube license types](https://support.google.com/youtube/answer/2797468); [17 USC 1201](https://www.law.cornell.edu/uscode/text/17/1201); [17 USC 1203](https://www.law.cornell.edu/uscode/text/17/1203); [GitHub: youtube-dl](https://github.blog/news-insights/policy-news-and-insights/standing-up-for-developers-youtube-dl-is-back/); [TorrentFreak on Cordova](https://torrentfreak.com/ripping-clips-for-youtube-reaction-videos-can-violate-the-dmca-court-rules/); [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/legalcode)
- [Compendium ch. 800](https://www.copyright.gov/comp3/chap800/ch800-performing-arts.pdf); [Hanagami v. Epic opinion](https://cdn.ca9.uscourts.gov/datastore/opinions/2023/11/01/22-55890.pdf); [Manatt on California digital replicas](https://www.manatt.com/insights/newsletters/client-alert/california-enacts-a-host-of-new-ai-and-digital-rep); [Debevoise on New York](https://www.debevoise.com/insights/publications/2025/12/new-york-enacts-landmark-ai-right-of-publicity-law); [IPWatchdog on NO FAKES, 18 Jun 2026](https://ipwatchdog.com/2026/06/18/senate-judiciary-moves-no-fakes-act-one-step-closer-to-passage/)
- [Steamworks content survey](https://partner.steamgames.com/doc/gettingstarted/contentsurvey); [itch.io Terms](https://itch.io/docs/legal/terms); [itch.io quality guidelines](https://itch.io/docs/creators/quality-guidelines); [Epic AI MegaJam rules](https://epicgames.ent.box.com/s/a7xcgl07fqoieeb99sjtd3juhj4agc4z)

**Clean sources and costs**
- [Mixamo FAQ thread](https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775); [MoCap Online licensing](https://mocaponline.com/blogs/mocap-news/legal-updates); [MoCap Online cost guide](https://mocaponline.com/blogs/mocap-news/motion-capture-cost-guide); [Reallusion Content EULA](https://www.reallusion.com/Content/EULA/EULA.htm); [GASP forum thread](https://forums.unrealengine.com/t/what-can-i-do-with-game-animation-sample-that-recently-was-at-100-off/1903980); [CMU mocap resources](https://mocap.cs.cmu.edu/resources.php); [Pexels licence](https://www.pexels.com/license/); [Pixabay terms](https://pixabay.com/service/terms/); [Rokoko shop](https://www.rokoko.com/en/shop); [Xsens pricing](https://www.xsens.com/resources/xsens-motion-capture-pricing); [HY-Motion](https://huggingface.co/tencent/HY-Motion-1.0)
