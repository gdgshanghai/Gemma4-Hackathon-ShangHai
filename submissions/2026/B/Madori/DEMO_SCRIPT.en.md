[中文](DEMO_SCRIPT.md) · **English**

# Demo Video Storyboard (≤ 5 min)

> For the hackathon submission. The main demo shows the **stable local e4b four-view build** (`web/madori.html`); the cloud large Gemma 4 precision serves as a technical-highlight shot.
> Before recording: run `./run.sh samples/madorizu_1f.png` to produce `web/madori.html`, and open it fullscreen in the browser, ready.

---

## 0:00–0:25 ｜ Pain point (hook)
- **Visual**: close-up of a densely annotated floor plan, slowly zooming in
- **Action**: none (static image + text overlay "This plan — can you read it?")
- **Voiceover**: When you rent or buy, you face this floor plan — can you read it? Most people can't. Yet it's precisely from this drawing that people make the biggest housing decision of their lives.

## 0:25–0:55 ｜ One-line pitch + reading the plan
- **Visual**: terminal running `./run.sh samples/madorizu_1f.png`, or open `madori.html` directly with its intro animation
- **Action**: show "feed in one image → results in seconds"
- **Voiceover**: Madori uses **local Gemma 4** to read this plan like an architect, then draws the professional analysis **directly onto the plan**. It all runs on your computer — the floor plan is never uploaded to the cloud.

## 0:55–2:20 ｜ Four views (core, the heaviest segment)
Click the four bottom tabs in order, ~20s each:

- **📖 Read** (0:55–1:20)
  - Action: click a few room chips / lenses, watch the corresponding rooms highlight live in the 3D white model
  - Voiceover: It reads out every room and explains it in plain language through several "professional lenses" — circulation, daylight, accessibility, critique. Click a room, and it lights up in the model.
- **☀ Daylight** (1:20–1:55) ⭐ key moment
  - Action: switch to the daylight view (auto top-down into a zoning map) → **turn the compass to change north**, watch room colors recompute live
  - Voiceover: An architect glances at orientation and judges daylight; ordinary people can't. Madori lets you set north — south = warm orange, north = cool blue — see at a glance which rooms get sun. **This is a fact computed from geometry, recomputed live as you turn the orientation, not the model guessing.**
- **🚶 Circulation** (1:55–2:08)
  - Action: switch to circulation, show the path line from the entrance
  - Voiceover: How you move once inside — one line, seen at a glance.
- **♿ Accessibility** (2:08–2:20)
  - Action: switch to accessibility, show wet-zone / entrance concern markers
  - Voiceover: For the elderly and wheelchair users, where it may be unfriendly — flagged directly.

## 2:20–3:05 ｜ 3D white model + interaction
- **Visual**: back to the Read view, drag the "flat ⟷ 3D" slider, drag-rotate the white model
- **Action**: show glass windows, walls, contact shadows
- **Voiceover**: You can also see the home's 3D volume and layering with your own eyes — instead of imagining it from a flat drawing.

## 3:05–3:40 ｜ Honest engineering (differentiating highlight)
- **Visual**: switch to the result of a dirty image (e.g. `hk_greenview.jpg`) — 3D downgraded to an outline + orange "geometry is estimated" warning + top banner "massing indication · not a source-accurate reconstruction"
- **Voiceover**: When an image can't be read accurately, it **downgrades honestly** — instead of drawing a pretty but misleading model, it falls back to an outline and clearly states "this is an estimate." **Honesty is part of this product.**

## 3:40–4:25 ｜ Technical highlight: Gemma orchestration + dual-spec precision
- **Visual**: ① the Mermaid architecture diagram from the technical report ② the 16-room layout reconstructed by the cloud large Gemma 4 (`madori3_debug.html`) side-by-side with the source image
- **Voiceover**: The core architecture is — **Gemma 4 as the orchestrating brain, directing deterministic tools: understanding goes to Gemma, precise computation goes to code**. The local small model keeps things private; the larger-spec Gemma 4 can **precisely reconstruct** a floor plan's room layout (all 16 rooms here match the source). Privacy tier, precision tier — both selectable, the core is always Gemma 4.

## 4:25–5:00 ｜ Social-value closing
- **Visual**: mission copy rises into frame
- **Voiceover**: Ordinary people make the biggest decision of their lives in front of a floor plan they can least read. Madori uses the eyes of Gemma 4 to hand an architect's ability to read a plan — **for free, privately, and honestly** — to everyone.

---

## Recording checklist
- [ ] Pre-run `madori.html` (madorizu_1f) + a dirty-image result ready to switch to
- [ ] Browser fullscreen, bookmarks bar hidden, notifications off
- [ ] Confirm the daylight view's "turn orientation → live recompute" demos well
- [ ] Architecture diagram + `madori3_debug.html` screenshots ready
- [ ] Keep total runtime under **5:00** (official hard limit)
- [ ] Voiceover can be Chinese audio or subtitles; pair jargon with plain language when it appears
