# Commercially clean sources of motion data and reference footage (as of 2026-11-21)

*Method note: "VERIFIED" = fetched and read on the primary (or vendor-hosted) page on 2026-11-21 via a fetch tool that returns a summary of the page, so exact quotes should be re-read by the owner before relying on them. "UNVERIFIED" = only seen in a search snippet, a third-party page, a forum post, or the primary page refused to load. Not legal advice; a lawyer should read the full licence texts named below before a paid release.*

---

## 1. Licensed mocap / animation libraries and datasets: what is usable in a sold game

### Takeaway
For a sold UE 5.9 game, the cleanest library routes are Fab/Epic animations, Mixamo, paid FBX libraries (MoCap Online, Truebones, Rokoko Motion Library) and ActorCore, all of which allow shipping inside a game but forbid re-releasing the raw files and (mostly) forbid ML training on them. Academic datasets (AMASS and everything built on it) are non-commercial; BONES-SEED is gated to academics and sub-$1M startups and bars training motion-generating models, so treat it as grey/avoid.

### Cited Findings

**Adobe Mixamo**
- Adobe-hosted community FAQ (post dated 2022-09-29 by user "TylerG 3D", not labelled Adobe staff): service described as in a "limited duration technology preview" and free "for unlimited commercial or non commercial use"; its table lists "Video Games" and "DLC or Addon Content for Games" as allowed. VERIFIED 2026-11-21 — [Mixamo FAQ thread](https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775)
- Same FAQ: prohibits "Blueprints, templates, or asset packages for video game engines" and says "You may not distribute the files to customers or non-team members"; no credit to Adobe/Mixamo required; the only restricted research use is "training machine-learning models"; "Adobe retains the rights to our software and content"; projects made during the free period are not affected if pricing changes. VERIFIED (same page)
- Availability/maintenance in 2026: forum replies on that thread run to 2026-11-08, where a community expert (not confirmed Adobe staff) says "no rules are changed till now" and points to Adobe's helpx Mixamo FAQ. No shutdown announcement found. VERIFIED that the replies exist (same page); the "no change" claim is community opinion only.
- Adobe's own helpx FAQ (https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) returned HTTP 403 and could not be read. A search snippet says it lists game development as a permitted royalty-free use. UNVERIFIED — [search result](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)
- Mixamo Additional Terms (version dated 2021-06-23) reportedly bar using the services/content "to directly or indirectly create, train, test, or otherwise improve machine learning algorithms or artificial intelligence systems"; community answers disagree whether this is still current and point to Fuse product-specific terms (June 2024). UNVERIFIED (PDF not opened) — [Mixamo Addl Terms PDF](https://wwwimages2.adobe.com/content/dam/cc/en/legal/servicetou/Mixamo-Addl-Terms-en_US-20210623.pdf)
- Known T-pose/rig/root-motion problems (mixamorig skeleton naming, in-place vs root-motion variants, 100x scale, 30 fps): not checked against any source in this session. UNVERIFIED — treat as general community knowledge; the project's own retarget tests are the real evidence.

**Epic: Fab licence, Game Animation Sample (GASP), Motion Matching content**
- Fab Standard License summary: may "Use the assets commercially or privately"; may "Commercially distribute your Projects with the Fab assets incorporated into it"; no credit required; Personal and Professional tiers carry the same rights; may not "Resell or redistribute the asset for free on a standalone basis or allow others to do the same"; may use assets "with any compatible tools (usage is not limited to Unreal Engine)"; sharing with collaborators on your project, including a private repo, is allowed; page says the full EULA is the binding text. The page did not cover generative-AI terms. VERIFIED 2026-11-21 — [Fab EULA](https://www.fab.com/eula)
- GASP licence: a forum user (not Epic staff) quotes the heading "UE-Only Content - Licensed for Use Only with Unreal Engine-based Products" and reads it as allowing commercial games, editing in Blender and mixing with other packs, "as long as its for/with Unreal Engine-based projects & products". VERIFIED that the post says this; the licence reading itself is UNVERIFIED — [Epic forum thread](https://forums.unrealengine.com/t/what-can-i-do-with-game-animation-sample-that-recently-was-at-100-off/1903980)
- A 2024 CG Channel article (seen via search snippet) says GASP animations work with all UE Mannequins, can be used in commercial projects, are licensed only for Unreal Engine, and can be retargeted to other humanoids. UNVERIFIED (snippet only) — [CG Channel](https://www.cgchannel.com/?p=158744)
- Epic's content EULA page returned HTTP 403 and the Fab listing's licence field was blank in the scrape, so Epic's exact written terms for GASP were not read. UNVERIFIED — [Fab listing](https://www.fab.com/listings/880e319a-a59e-4ed2-b268-b32dac7fa016?lang=en)

**Rokoko Motion Library / Studio**
- Rokoko pricing page: Motion Library animations can be exported and used in any project "including commercial ones"; Free, Basic, Plus, Pro all list library access; Studio Plus $28/mo ($20/mo billed annually), Pro $70/mo ($50/mo annual); a second block on the same page shows conflicting figures (Basic $20, Plus $50, Pro "Contact us"). Vision AI video-processing allowance per month: 30 s (Starter), 600 s (Basic), 3,000 s (Plus), 15,000 s (Pro). VERIFIED 2026-11-21 — [Rokoko pricing](https://rokoko.com/pricing/)
- Rokoko Motion Library redistribution/ML terms were not found in this session. Gap below.

**Reallusion ActorCore (Content EULA, "Updated November 1st, 2026")**
- Standard License (s2.1) and Enterprise License (s2.2); "Any use of the Content not expressly permitted under the Standard License requires an Enterprise License." Game use is allowed "provided that the Content is fully integrated, compiled, or packaged into the final application"; game developers are pointed to a separate "EULA Appendix" (not read). VERIFIED — [Reallusion Content EULA](https://www.reallusion.com/Content/EULA/EULA.htm)
- s1.13: exporting content to other formats (e.g., FBX, OBJ) for use outside Reallusion software "requires the acquisition of a Standard License". s2.1(B): you may NOT "import, upload, reproduce, make available, publish, transmit, distribute, or sublicense the Content". s6.3: "strictly prohibited from distributing Content in any deployment architecture that permits end-users" (read with the Appendix; this wording may bite if players can extract assets). s2.1(C)(5) prohibits use "For machine learning, artificial intelligence (AI) training, fine-tuning, or model validation". Changes "effective immediately" (s10). VERIFIED (same page)
- No mass-distribution registration found in the current EULA text (older forum posts mention one). VERIFIED absence on the page; older forum claim UNVERIFIED — [Reallusion forum](https://forum.reallusion.com/PrintTopic375116.aspx)
- ActorCore store page (reallusion.com/ActorCore/) returned 404; motion pack pricing not verified.

**Truebones**
- A Truebones Gumroad listing is reported to say its products are "absolutely royalty free" for "any and all purposes even commercial"; free Unreal-Engine FBX/BVH library exists; Motherlode listed at $45 on one page and $100 on another. UNVERIFIED (search snippets; the product page text did not load) — [Truebones Gumroad](https://truebones.gumroad.com/p/truebones-motherlode-is-the-worlds-largest-mocap-library-in-bvh-and-fbx-formats), [free UE library](https://truebones.gumroad.com/p/free-truebones-unreal-engine-complete-mocap-library-in-fbx-format)

**MoCap Online (a Fab/own-store FBX pack seller; typical of paid mocap packs)**
- Standard License is included with every purchase: use animations "in commercial games, films, simulations, ... projects you sell or monetize"; "You cannot resell, give away, or redistribute the original animation files (FBX, BIP, etc.) as standalone assets"; training AI on the animations needs a separate "AI Usage Permit"; "Attribution is not required under any of our licenses"; larger studios may need a separate Commercial License, thresholds undefined on the page. VERIFIED 2026-11-21 (blog post, not the full legal page) — [MoCap Online licensing](https://mocaponline.com/blogs/mocap-news/legal-updates)

**CMU Graphics Lab Motion Capture Database**
- The official site (mocap.cs.cmu.edu) failed TLS verification and the Wayback Machine was blocked, so the current usage statement was NOT read on a primary page.
- Third-party mirrors quote the terms as: free for use in research; "You may include this data in commercially-sold products, but you may not resell this data directly, even in converted form", and label it "free for all uses". UNVERIFIED — [Papers With Code mirror (via search)](https://paperswithcode.com/dataset/cmu-motion-capture), [CMU resources page (search hit)](https://mocap.cs.cmu.edu/resources.php)
- Conflict: a third-party FBX conversion on 4TU.ResearchData lists CC BY-NC 4.0 in its own metadata; a competitor (MoCap Online) claims a research licence. UNVERIFIED — [4TU FBX conversion](https://data.4tu.nl/datasets/0448aab2-3332-449f-a8e2-d208cb58c7df)

**AMASS and academic datasets**
- AMASS licence: rights only for "non-commercial scientific research, non-commercial education, or non-commercial artistic projects"; "any use for commercial purposes ... is prohibited", including "incorporation in a commercial product"; also prohibits using the data to train methods/networks "for commercial use"; commercial licences via ps-license@tue.mpg.de. The page does not discuss its constituent datasets (e.g., CMU). VERIFIED 2026-11-21 — [AMASS licence](https://amass.is.tue.mpg.de/license.html)
- HumanML3D listed as "research use only" by an aggregator (code repo may be MIT); HumanML3D cannot be redistributed because of AMASS's policy; Motion-X annotations are CC BY-NC-SA 4.0 and its sub-datasets keep their own licences; no licence information found for KIT-ML or 100STYLE. UNVERIFIED — [HumanML3D repo](https://github.com/yc2768/humanml3d), [Motion-X licence PDF](https://motion-x-dataset.github.io/static/license/Motion-X%20License.pdf)

**Bones Studio / BONES-SEED**
- Size and format: 142,220 motions (71,132 original + 71,088 mirrored), about 288 h at 120 fps, 522 performers; SOMA Uniform and Proportional BVH plus Unitree G1 CSV; SOMA skeleton as BVH/USD; FBX not mentioned; login plus a licence checkbox required. VERIFIED — [BONES-SEED on Hugging Face](https://huggingface.co/datasets/bones-studio/seed)
- Licence (bones.studio): rights granted ONLY to "Academic Users" or "Qualifying Startups" (commercial entity under $1,000,000 annual gross revenue); "If you do not qualify ... you are NOT granted any rights"; a Qualifying Startup may use it for "internal research, development, and commercialization activities"; games are not named. Forbidden: redistributing the raw dataset or uploading it to Hugging Face/GitHub, and "using the Dataset to train, fine-tune, or condition any generative model" (models with "non-data outputs" are allowed). Licensee owns "Results" provided the raw dataset cannot be extracted from them; attribution "Training data includes Motion Data by Bones Studio" is mandatory for models/software. VERIFIED — [BONES-SEED License](https://bones.studio/info/seed-license)
- Commercial ML licence for BONES-SEED listed at $480,000 USD (perpetual, non-resalable, covers training/fine-tuning/evaluation). Game-use terms and per-clip library licensing not stated on the page. VERIFIED — [Bones licensing](https://www.bones.studio/licensing)

**Move.ai, Cascadeur and other 2025-26 items**
- Move One (iPhone single camera) plans: Free 30 one-time credits; Starter $18/mo (60 credits); Standard $48/mo (180); Plus $225/mo (240); Advanced $490/mo (700); 1 credit per person-second for Gen 1, 2 credits for Gen 2; clips up to 30 s free / 60 s paid. The page does not state commercial-licence terms, output formats or fps. VERIFIED — [Move One pricing](https://docs.move.ai/knowledge/move-one-pricing)
- Move.ai "Marketplace" library licensing: nothing found. Gap.
- Cascadeur: Free is non-commercial with CASC-only export and a 300-frame cap; Indie $19/mo or $8/mo annual, only if revenue/funding is under $100k/yr, exports FBX/DAE/USD/GLTF; Pro $49/mo or $33/mo annual, unlimited commercial use; Black Friday promo shown. Video-to-motion not mentioned on the plans page. VERIFIED 2026-11-21 — [Cascadeur plans](https://cascadeur.com/plans)
- Motorica: no licence or pricing found. Gap.

### Inferences
- "Shipped inside the game" is the safe harbour in every commercial library (Mixamo, Fab, MoCap Online, Reallusion). Do not ship loose FBX/BVH in a repo that is public, in a DLC "pack", or in a mod kit; keep them cooked in .pak/.utoc (the project's normal packaging), and keep the git repo private.
- Retargeting to MetaHumans in the UE IK Retargeter is "use inside Unreal" and fits Fab/GASP's UE-only wording; exporting retargeted FBX out of UE and handing it to a contractor is covered by the Fab "collaborators" allowance but NOT by "standalone redistribution", so keep that circle small and written.
- A video-to-motion pipeline built on a model trained on Mixamo/ActorCore/MoCap Online/BONES-SEED clips would breach their ML-training clauses; fine-tuning on these libraries is out. Using them only as animation content in the game is not "training".
- If the studio's revenue ever tops $1M, BONES-SEED rights lapse entirely per its own wording; given the $480k commercial price, do not build on it.
- CMU is probably usable as content in a commercial product (no resale), but because the official page was not read, re-fetch it (or ask CMU) and keep a screenshot dated before shipping. Avoid the AMASS-processed (SMPL) versions and the CC BY-NC FBX conversions.

### Gaps
- Mixamo: Adobe's current helpx FAQ and Additional Terms were not read (403/PDF unopened); technical rig/root-motion issues not sourced.
- GASP: Epic's own licence wording for first-party sample content not read (EULA 403, Fab licence field blank).
- CMU: official page unreachable; usage statement only seen second-hand.
- Truebones, Motorica, Rokoko Motion Library redistribution terms, ActorCore pricing and the EULA Appendix for games, Move.ai Marketplace: not found or not read.
- Fab third-party mocap packs have per-seller licences; I did not sample specific listings.

---

## 2. Footage with explicit reuse rights, as input to a video-to-motion pipeline

### Takeaway
Own filming of a signed performer is by far the cleanest input: you control ownership and consent by contract. Public-domain/CC0 and CC BY footage is copyright-clean but carries personality/privacy risk for identifiable people and is poor mocap material; licensed stock (Shutterstock, Adobe Stock, Pond5) has AI/ML-restriction language and no clear "extract motion data" permission, so it is grey and should be avoided without written vendor permission.

### Cited Findings
- Own filming / performer agreement: no primary source was read for filming setup or release wording; the checklist below is general practice. See Inferences. UNVERIFIED.
- Pexels licence: all photos/videos "free to use"; modification permitted; attribution not required; bans selling unaltered copies, implying endorsement, redistributing on other stock/wallpaper platforms, and showing identifiable people "in a bad light or in a way that is offensive". The page says nothing on AI/ML, data extraction or derivative works beyond editing. VERIFIED 2026-11-21 — [Pexels licence](https://pexels.com/license/)
- Pixabay Content License (Terms last updated 20 October 2026): licence for "commercial or non-commercial purposes"; no standalone sale/distribution (Standalone = no creative effort applied); Section 8 prohibits "Data mining, extraction, scraping and the use of programs or robots for automatic data collection" for unauthorised purposes "including ... machine learning purposes" (aimed at bulk collection from the site); "We do not warrant that any consents or licenses have been obtained"; recognisable persons need care ("you must consider whether you require the consent of a third party"). VERIFIED — [Pixabay terms](https://pixabay.com/service/terms/), [licence summary](https://pixabay.com/service/license-summary/)
- Wikimedia Commons: each file's licence sets conditions; public-domain attribution "recommended"; CC BY requires crediting the creator and identifying the licence; CC BY-SA adds ShareAlike; non-copyright rights (trademark, personality, privacy) are independent, "images of people" commercial use may need the subject's consent; Foundation gives no warranty on copyright status. The page does not address CC0 for media. VERIFIED — [Commons reuse guide](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
- CC BY 4.0 attribution mechanics: give creator name/attribution parties, copyright notice, licence notice, disclaimer notice, link to the material and to the licence; "must indicate if you modified the material"; "No additional restrictions" clause; deed is silent on AI/data mining (legal code not read). VERIFIED (deed) — [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/)
- NASA: content "generally are not subject to copyright in the United States", but the NASA insignia/logotype/identifiers are not public domain; commercial uses must not imply endorsement; for identifiable people "permission is generally needed" for commercial use (privacy/publicity); NASA "should be acknowledged as the source". VERIFIED — [NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- Internet Archive: help pages say the Archive cannot guarantee uploader-supplied licence data, "no license" does not mean public domain, and it does not comment on a film's rights status; U.S. copyright status is often not definitively checkable. UNVERIFIED (search snippets of help.archive.org; Terms page rendered empty) — [Archive movies guide](https://help.archive.org/help/movies-and-videos-a-basic-guide/), [Archive forum on missing licence](https://archive.org/post/1056247/how-do-i-see-the-licence-of-a-specific-file)
- Adobe Stock licence page: no mention of ML/AI training in the licence summary (only Generated Outputs); standard licence bars distributing the stand-alone file and making merchandise/templates for resale; Enhanced licences exist for video; says nothing on model releases or footage in games. VERIFIED — [Adobe Stock licence terms](https://stock.adobe.com/license-terms)
- Adobe Stock's older PSLT (2020) bars using Works for "machine learning or AI purposes"; the January 2026 PSLT was not checked. UNVERIFIED — [PSLT Stock WW 2020v2](https://adobe.com/content/dam/cc/en/legal/terms/enterprise/pdfs/PSLT-Stock-WW-2020v2.pdf)
- Shutterstock (search snippet of the official licence page; the page itself returned 403): bars using visual content "as training data for any artificial intelligence, machine learning, or generative AI system, tool, process, or dataset", bars using stills from video except for marketing of your own derivative works, but allows AI features of editing software that do not train on the content. UNVERIFIED — [Shutterstock licence](https://www.shutterstock.com/license)
- Pond5 Video AI Terms (updated 2026-02-24) bar using the AI service's outputs to train ML systems; this concerns Pond5's AI service rather than ordinary footage licences. UNVERIFIED (snippet) — [Pond5 Video AI ToS](https://www.pond5.com/legal/video-ai-terms-of-service)
- Performer cost benchmarks: SAG-AFTRA 2026 interactive rate sheet cited at $374.53-$907.96 per 8-hour day plus 17% contributions; non-union around $250/day. UNVERIFIED (secondary blog) — [Viggle cost post](https://viggle.ai/blog/motion-capture-suit-price-vs-ai-mocap)

### Inferences
- Safe: footage the studio filmed itself of a person who signed a release. Grey: CC0/PD/CC BY footage of identifiable people (copyright fine, personality rights independent, and the footage rarely has clean full-body fixed-camera framing). Avoid: stock/Archive footage unless the vendor/rights-holder confirms in writing that extracting skeletal motion for commercial game animation is allowed. Note that running pose estimation is inference, not "training", but ML/"derivative"/"standalone" clauses make the point arguable; written permission removes the doubt.
- Filming tips (general practice, UNVERIFIED): fixed tripod, full body incl. feet in frame with head/foot margin, 60 fps with a fast shutter (about 1/500 s) to limit motion blur, flat plain background, fitted clothing that contrasts with the background and shows joints (no long skirts/loose cloaks for the base pass), even diffuse light (no hard shadows), performer's A-pose/T-pose at start and end for calibration, one performer per take, a ruler or marked floor squares for scale, repeat each action 3 times, and record sword/prop actions with a prop of the real length and weight.
- Performer agreement should cover (checklist, not legal advice; a lawyer should draft the final): the performer's consent to recording and to extraction/derivation of motion data and a skeleton; assignment (or exclusive perpetual licence) of all rights in recordings, motion data and results to the studio, including worldwide, all media, perpetual, sublicensable; explicit commercial-game use including sale; consent to processing with AI/ML tools and cloud services; no credit, no royalty, no approvals, flat fee stated; no moral-rights claims; right to alter or combine; confirmation that the performer is over 18 and free to sign; confidentiality; handling of video (retention, deletion, biometric/personal-data consent where local law requires, e.g., GDPR/Illinois-type rules); and a statement that the performer does not use or wear third-party-branded or copyrighted items. Keep a signed copy per session.
- CC BY mechanics for a shipped game: put a credits-screen entry and a store-page/readme line in the form Title - Author - Source URL - Licence name and link - "modified" note; keep the retrieved licence page archived on the date of download.

### Gaps
- No primary source on filming best practice, on the current Pexels/Pixabay model-release status for specific clips, on Wikimedia Commons CC0 media handling, or on current Shutterstock/Pond5 footage licence wording (403 or snippets only).
- Internet Archive Terms of Use page could not be read.
- Legal status of extracting skeletal motion from copyrighted video of a third party is untested and unresearched here (another researcher covers YouTube risk).

---

## 3. Kimodo itself and text-to-motion alternatives

### Takeaway
Kimodo's code is Apache-2.0 and its SOMA weights are under the NVIDIA Open Model License, which is commercial, claims no ownership of outputs, and makes the user responsible for output use; its model card says "ready for commercial use". Alternatives (Uthana, Cascadeur, Rokoko text-to-motion, Tencent HY-Motion) are usable commercially on paper, but each has vendor-specific conditions to read.

### Cited Findings
- Kimodo code: Apache-2.0. Weights licensed separately: SOMA, G1 and SOMA-SEED variants under the NVIDIA Open Model License; the SMPL-X variant (Kimodo-SMPLX-RP-v1) under the NVIDIA "Internal Scientific Research and Development Model License" (research only). Trained on proprietary Bones Rigplay (about 700 h) for RP variants and BONES-SEED (about 288 h) for SEED variants. VERIFIED 2026-11-21 — [Kimodo GitHub](https://github.com/nv-tlabs/kimodo)
- Kimodo-SOMA-RP-v1.2 model card: "released under the NVIDIA Open Model License"; "ready for commercial use"; 282M parameters, 30 fps, 30-joint SOMA skeleton; intended uses include "animation for games and media"; limitations listed: foot skating, imperfect prompt adherence, no cartoon/non-physical motion, no scene/object awareness, one skeleton per model; best at locomotion, gestures, combat, dancing, everyday activities; the card does not mention hands, fingers or sword fighting. VERIFIED — [Kimodo-SOMA-RP-v1.2 card](https://huggingface.co/nvidia/Kimodo-SOMA-RP-v1.2)
- NVIDIA Open Model License: "Models are commercially usable"; s2.2 grant is perpetual, worldwide, non-exclusive, royalty-free, revocable; s2.4 "NVIDIA claims no ownership rights in outputs. You are responsible for outputs and their subsequent uses"; s1.1 outputs are not Derivative Models; s3.1 attribution notice ("Licensed by NVIDIA Corporation under the NVIDIA Open Model License") applies if you distribute the Model itself; s2.1 termination if you sue over the model's IP or bypass a guardrail without an equivalent; s8 indemnity to NVIDIA; Cosmos "Built on NVIDIA Cosmos" rule applies only to Cosmos models. VERIFIED — [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
- Uthana: pay-as-you-go credits only; text-to-motion 3.0 at $0.10/s, video-to-motion 3.0 at $0.06/s, locomotion 1.0 at $0.02/s, auto-rig $0.15 per rig; "Uthana stopped offering new subscriptions in August 2026"; paid usage includes commercial use of outputs "subject to Uthana's Terms of Use"; downloads unlimited; the page does not mention FBX/GLB, Unreal or MetaHuman. VERIFIED — [Uthana pricing](https://uthana.com/pricing)
- Cascadeur: see section 1; Indie under $100k revenue, Pro unlimited commercial use, FBX export on paid tiers; AI-assisted AutoPosing listed. VERIFIED — [Cascadeur plans](https://cascadeur.com/plans)
- Rokoko: text-to-motion clips are reported as unlimited on Pro (reseller page); Vision video mocap limits per month are on the pricing page (section 1). UNVERIFIED for text-to-motion — [Knox Labs Rokoko Pro listing](https://www.knoxlabs.com/products/rokoko-studio-pro-monthly-license)
- Tencent HY-Motion 1.0: Hugging Face lists the licence as "tencent-hunyuan-community" (text not shown); needs about 26 GB VRAM (1.0B) or 24 GB (0.46B Lite); no non-humanoids, no multi-person, no seamless loops/in-place animations, English prompts. VERIFIED (card) — [HY-Motion on Hugging Face](https://huggingface.co/tencent/HY-Motion-1.0)
- A CGWorld article says the community licence allows commercial use except for platforms with more than 100M monthly users; the raw LICENSE URL returned 404, so the actual clauses (territory exclusions, output ownership) were not read. UNVERIFIED — [CGWorld](https://cgworld.jp/flashnews/01-202601-HY-Motion.html)
- Other items seen only by title in search results: Altercode "Text To Anim" (local AI text-to-animation for UE) and a Kimodo-based UE authoring plugin on the Epic forum. UNVERIFIED — [Altercode thread](https://forums.unrealengine.com/t/altercode-text-to-anim-local-ai-text-to-animation/2838544), [Kimodo authoring thread](https://forums.unrealengine.com/t/coding-x-embodied-space-studio-kimodo-ai-motion-authoring-for-gameplay-cinematics/2735839)

### Inferences
- Kimodo on the SOMA RP/SEED weights is commercially clean at the licence level. The owner's complaints (no fingers, weak swordplay) match the card's omission of hands and the 30-joint skeleton; fingers must be added by hand/other source.
- Training-data provenance: the RP data is Bones' proprietary set. NVIDIA is the licensee; whether NVIDIA's rights cover downstream users is NVIDIA's representation in the model licence, not something the BONES-SEED licence (which binds dataset downloaders) controls. A lawyer should confirm if the owner uses a SEED-variant checkpoint.
- Output ownership: NVIDIA disclaims ownership, but whether raw generated motion is copyrightable by the studio is a separate question (not researched here, and generally contested for AI output). Hand-edited motion plus original footage-based motion strengthens the claim.
- HY-Motion needs 24-26 GB VRAM and its licence text was unread, so treat it as an experiment, not a pipeline dependency.
- MotionStreamer, MotionGPT successors and any "Kimodo vs others" comparisons: no authoritative source found; do not assume their licences (many academic models inherit AMASS/HumanML3D non-commercial restrictions via their training data).

### Gaps
- No MotionStreamer, MotionGPT-successor or head-to-head Kimodo benchmark source found.
- HY-Motion licence text unread; Uthana Terms of Use unread; Rokoko text-to-motion terms unread.
- No source confirming whether Kimodo's SOMA skeleton includes fingers (the owner reports none).

---

## 4. Hybrid recommendations and 2026 costs

### Takeaway
A pragmatic hybrid is Kimodo for generic body motion, licensed library clips (Fab/GASP, Mixamo, paid FBX packs) for gaps, and the studio's own filmed performance (phone or markerless service) for hard cases such as swordplay, digging and carrying, with hand/finger work done by keyframing or a glove. Phone-based capture costs tens of dollars; an inertial suit costs about $4,500-$9,000; an optical day costs roughly $1,500-$3,300 plus cleanup.

### Cited Findings
- Optical studio rates: one 2026 cost guide puts day rates at about $500-$5,000, most mid-tier studios at $1,500-$3,000; cleanup estimated at 2-8x raw capture time at $75-$150/h. UNVERIFIED (vendor blog) — [MoCap Online cost guide](https://mocaponline.com/blogs/mocap-news/motion-capture-cost-guide)
- A university rate card lists high-quality optical capture at $3,295/day plus cleanup at $130/minute and $95 per FBX export. UNVERIFIED (snippet; PDF not opened) — [ECU WAAPA rate card](https://waapa.ecu.edu.au/__data/assets/pdf_file/0006/1084965/WAAPA-Performance-Capture-Rate-Card.pdf)
- Rokoko hardware: Full Performance Capture bundle (Smartsuit Pro II + Smartgloves II + Headrig or Headcam + 1-year Studio Pro) $4,495; individual hardware prices not listed on the shop page. VERIFIED 2026-11-21 — [Rokoko shop](https://www.rokoko.com/en/shop). A third party prices the Smartsuit Pro II alone at $2,295 and Smartgloves at $1,795 (checked Aug 2026). UNVERIFIED — [Viggle](https://viggle.ai/blog/motion-capture-suit-price-vs-ai-mocap)
- Xsens (blog dated 2025-03-10): hardware from $4,590 one-time plus software subscription from $3,790 per year; Indie Program for new customers with a registered company and revenue at or under $550,000 (EUR 500,000). VERIFIED — [Xsens pricing](https://www.xsens.com/resources/xsens-motion-capture-pricing)
- Move One (single iPhone): $18-$490/month plans (section 1). VERIFIED. Move Pro (multi-camera): custom pricing; a search snippet cites a 30-day trial at $995 with commercial use, up to 4 cameras and 1 person; the docs page itself returned 404. UNVERIFIED — [Move Pro pricing doc](https://docs.move.ai/knowledge/how-does-pricing-work-for-move-pro)
- Uthana video-to-motion 3.0 at $0.06 per second of output; Rokoko Vision allowances per month (section 1). VERIFIED.
- Cascadeur Indie at $8-$19/month for cleanup/physics-aware editing of any source clip, under $100k revenue. VERIFIED.

### Inferences
- Cost ladder for roughly one minute of finished motion: library clip (free to about $50), Kimodo (free, local GPU), own phone footage + Rokoko Vision/Move One/Uthana (about $0-$20), friend performer (free to about $250 per day non-union), inertial suit (about $2,300-$4,500 hardware once, then free), optical studio (about $1,500-$3,300 per day plus cleanup that can double the bill). For a small team shipping one game, buying or renting a suit is justified only if the project needs more than about 15-20 minutes of bespoke motion or finger/prop work.
- Best use of own footage: swordplay (Kimodo's weak spot), digging, carrying, specific gestures and any interaction with a prop. Film with real props, one performer, A-pose start, then run through one video-to-motion tool, clean in Cascadeur or UE Control Rig, retarget via IK Retargeter. Use Kimodo for locomotion, idles, conversations and crowd motion; use library clips for common actions (climbs, falls, hits) to avoid re-making them.
- Hands/fingers: capture with gloves (Rokoko Smartgloves II sold in the bundle above) or keyframe; neither Kimodo's card nor the BONES-SEED skeleton description mentions fingers.

### Gaps
- No verified 2026 price for the Smartsuit Pro II alone, Move Pro beyond the trial snippet, or Xsens Link/Awinda individually.
- Professional day rates are from blogs and one rate card, not studio quotes; get 2-3 quotes before budgeting.

---

## 5. Steam / itch.io AI-disclosure implications

### Takeaway
Steam and itch.io both ask you to disclose generative-AI content that ships to players; library and own-performance motion needs no AI flag, but Kimodo, Uthana text-to-motion and HY-Motion output is generative and should be disclosed. Markerless video-to-motion is a grey area; a short precautionary disclosure costs little.

### Cited Findings
- Steam Content Survey: "Pre-Generated AI content" is any content that ships with the game and is consumed by players "created with the help of AI tools during development"; "Live-Generated AI content" is content created while the game runs and requires explaining guardrails; the page says "Efficiency gains through the use of these tools is not the focus of this section"; developers "describe that implementation in detail"; you also promise the game "will not include illegal or infringing content". VERIFIED 2026-11-21 — [Steamworks content survey](https://partner.steamgames.com/doc/gettingstarted/contentsurvey)
- Valve revised the form around 2026-01-16 so that AI used behind the scenes (e.g., coding helpers) need not be reported and the duty centres on AI content consumed by players, including marketing and concept assets as well as in-game content. UNVERIFIED (multiple news outlets, none primary) — [PC Gamer](https://www.pcgamer.com/software/ai/steam-updates-ai-disclosure-form-to-specify-that-its-focused-on-ai-generated-content-that-is-consumed-by-players-not-efficiency-tools-used-behind-the-scenes/), [GamingOnLinux](https://gamingonlinux.com/2026/01/valve-tweak-steam-ai-disclosure-form-for-developers-to-clarify-its-for-content-consumed-by-players)
- itch.io: "We ask that you accurately tag your project if it contains materials produced by generative AI"; self-contained algorithms without external large datasets need no disclosure; "We are strictly enforcing disclosure for all game asset, soundtrack, physical game, comic, and book pages"; failure to tag "may result in delisting"; tagged projects appear on an AI Assisted browse page. VERIFIED — [itch.io quality guidelines](https://itch.io/docs/creators/quality-guidelines)

### Inferences
- By source: own filming with a hired/friend performer, hardware mocap (Rokoko suit), Fab/GASP, Mixamo, MoCap Online, Truebones, ActorCore, CMU: no AI disclosure needed (not generated by an AI model). Kimodo, Uthana text-to-motion, HY-Motion: generative, ships to players, disclose on both stores (animation is part of what players consume). Move/Rokoko Vision/Uthana video-to-motion and other pose-estimation-based capture: ML-processed capture of a real performance rather than generation; arguable either way, so a one-line "ML-assisted motion capture" disclosure is the cautious choice. Cascadeur AutoPosing: AI-assisted posing; disclose if the poses ship.
- Disclosure by itself does not clear rights: Valve's survey separately holds the developer responsible for infringing content.
- The game is M-rated; the Steam page cited that Valve does not want live-generated AI adult-only sexual content "at this time", which does not affect pre-generated body animation but is worth knowing if any live-generation is ever added.

### Gaps
- The current Steam form text after the January 2026 revision was not read on a primary page; verify the form wording in Steamworks before submission.
- itch.io's disclosure form for games (as opposed to the guidelines page) was not inspected.

---

## 6. Cleanest-to-grayest ranking

### Takeaway
Rank order for a sold game: (1) own filmed/captured performance under a signed release, (2) first-party and mainstream licensed libraries used only inside the game, (3) Kimodo-style licensed generative models, (4) licence-clean tools with vendor conditions, (5) public-domain/CC footage, (6) stock footage, (7) research datasets. The only categories that are clearly out for commercial use are AMASS-derived datasets and, in practice, BONES-SEED.

### Cited Findings
- See sections 1-5 for all sources; each row below summarises those findings.

### Inferences

| Rank | Source | Licence verdict for a sold game | Redistribute raw files? | Attribution | Cost | Fit for MetaHumans / notes |
|---|---|---|---|---|---|---|
| 1 | Own filming or own mocap hardware, performer release signed | Clean by contract (you own recordings and results); tool licences still apply (Rokoko Studio, Move, Uthana, Cascadeur) | You own it | None | Phone free; suit about $4.5k; performer $0-$907/day | Best for swordplay, digging, carrying; hands need gloves or keyframes |
| 2 | Epic Fab / GASP / Motion Matching content | Commercial OK, UE-only (Fab EULA verified; GASP wording UNVERIFIED) | No standalone | None | Free or low | Native UE5 Mannequin skeleton, retargets in UE |
| 3 | Mixamo | Commercial games OK per FAQ; no engine asset packs; no ML training; Adobe's helpx text unread | No | None | Free | mixamorig skeleton, retargeting needed; T-pose/root issues UNVERIFIED |
| 4 | MoCap Online, Truebones, Rokoko Motion Library | Commercial OK in games (MoCap Online verified; Truebones and Rokoko partial) | No standalone | None | $0-$100 per pack; Rokoko from free | FBX/BVH; check per-seller licence on Fab |
| 5 | Reallusion ActorCore | Commercial OK with Standard License if packaged in the game; extra limits on end-user extractable deployments; no ML | No | None | Paid | FBX export needs Standard License |
| 6 | Kimodo (SOMA weights) | NVIDIA Open Model License: commercial, NVIDIA claims no output ownership; copyrightability of raw output unsettled | Own outputs | NVIDIA notice only if you ship the model | Free, local GPU | Owner's primary body-motion source; no fingers, weak swordplay; AI disclosure needed |
| 7 | Cascadeur Indie/Pro; Uthana paid | Tool terms allow commercial (Indie under $100k revenue; Uthana "subject to Terms of Use", unread) | Own outputs | None | $8-$49/mo; Uthana per second | FBX export; Uthana skeleton/MetaHuman support unconfirmed |
| 8 | CMU Mocap Database (original data) | Reported OK in commercial products, no resale; official page unread | No resale | Credit customary | Free | BVH/C3D, old skeleton, low quality; avoid CC BY-NC conversions |
| 9 | CC0 / public-domain footage (NASA, Commons) | Copyright-clean; personality/privacy and logo issues remain | Fine | Recommended | Free | Rarely usable framing |
| 10 | CC BY footage | Clean with attribution; CC BY-SA adds ShareAlike (avoid) | Fine | Required (TASL) | Free | Same people-rights caveats |
| 11 | Pexels / Pixabay footage | Licence permits modification; no model-release warranty (Pixabay says so explicitly) | No standalone | None | Free | Grey for motion extraction of identifiable people |
| 12 | Tencent HY-Motion | Community licence text unread; territory and MAU limits possible | Unread | Unread | Free, 24-26 GB VRAM | Experimental only |
| 13 | Licensed stock footage (Shutterstock, Adobe Stock, Pond5) | AI/ML restrictions and no clear permission to extract motion data; stills/derivative limits | No | Per licence | $ per clip | Avoid without written vendor permission |
| 14 | Internet Archive footage | Rights status unreliable (uploader-supplied) | Unknown | Unknown | Free | Avoid |
| 15 | BONES-SEED | Only Academic Users or startups under $1M revenue; no generative-model training; no raw redistribution; $480k commercial ML licence | No | Mandatory credit | Free (restricted) | Grey/avoid; owner's studio may lose rights above $1M |
| 16 | AMASS, HumanML3D, KIT-ML, 100STYLE, Motion-X | Non-commercial or inherits non-commercial (AMASS verified; others UNVERIFIED) | No | Per licence | Free | Do not use |

### Gaps
- Out of scope: YouTube footage (covered by another researcher); legal advice. A lawyer should read the full texts of the Fab EULA and Epic's GASP terms, NVIDIA Open Model License plus the Kimodo model card, the Mixamo Additional Terms, the Reallusion EULA with its Appendix, and any performer release before the paid release.
