# Higgsfield prompt: portfolio thumbnail art

Use as a **background layer only**. Image models garble words and logos, so `thumbnail.html` adds the
exact text and a real app screenshot on top. Save the result as `art.png` next to `thumbnail.html`, then
set `<body class="art">` and re-render at 1600×1200.

- **Model:** `gpt_image_2_5` (quality high, 2k) or `recraft_v4_1` (model_type `vector`). Both need a
  Higgsfield Basic plan or higher. On the free plan, `z_image` jobs failed on 2026-11-03.
- **Aspect ratio:** 4:3
- **Palette (Recraft `colors`):** #032D60, #014486, #0176D3, #00A1E0, #2E844A, #FFFFFF

## Prompt

Premium enterprise software marketing illustration, 4:3, clean isometric-lite data-flow diagram on a deep
navy background (#032D60 fading to #014486), soft blue glow, crisp vector style, no text, no letters,
no logos, no brand marks.

Composition: the LEFT 42% of the frame is calm, empty dark-navy gradient space with only faint grid lines
(reserved for a headline added later). The RIGHT 58% shows the story:
- At the far left of the diagram, a large soft sky-blue cloud made of stacked rounded database records
  (CRM data source), glowing gently.
- From the cloud, luminous data streams flow right into a central hexagonal routing hub with a subtle
  shield outline, like a smart traffic junction.
- From the hub, three clearly separated glowing paths branch out to three destinations:
  (1) top: a bright external cloud node with a small token/mask symbol on the stream (data masked before
  leaving); (2) middle: a compact server rack inside a translucent rounded wall with a padlock (private
  model inside the company network, soft green accent #2E844A); (3) bottom: a small database cylinder
  looping back to the source cloud (answered from the CRM itself, no AI needed).
- Tiny particles on the external path appear as small redacted bars to suggest masked personal data.
- A small checkmark approval badge sits near the hub.

Lighting and palette: Salesforce-style blues (#0176D3, #00A1E0), white highlights, one green accent for
the private path, subtle depth with soft shadows, generous negative space, high contrast, readable even at
thumbnail size. Bottom 18% of the frame darker and empty (reserved for captions). Style: modern B2B SaaS
hero art, flat-gradient vector with gentle 3D depth, not cartoonish, no people, no UI text.
