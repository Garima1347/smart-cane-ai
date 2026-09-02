# Training Data — Sourcing &amp; Labeling Guide

Getting labeled data is the actual bottleneck for custom classes like potholes —
not the training step itself, which is just a few commands once you have data.

## Option A — Start from an existing pothole dataset (fastest, do this first)

Roboflow Universe hosts several public, pre-labeled pothole datasets you can
download in YOLOv8 format directly — no labeling needed to get started:

1. Go to https://universe.roboflow.com and search "pothole detection"
2. Pick a dataset with a few thousand images (more images = better; look for
   ones with Indian/Asian road conditions specifically if available, since
   pothole appearance varies a lot by road surface type — asphalt potholes
   look different from broken-concrete potholes)
3. Export in **YOLOv8** format — Roboflow gives you the exact `dataset.yaml`
   + `images/` + `labels/` folder structure already in the right shape
4. Download and drop it straight into `training/dataset/`

This alone can get you a working first model in an afternoon.

## Option B — Add your own images on top (do this second, to cover local conditions)

Public datasets often don't reflect your specific city's road/lighting
conditions. Once Option A gives you a working baseline:

1. **Collect**: walk around campus/local roads with a phone camera, film
   video of the ground ahead (the same angle your cane's camera will see).
   Aim for varied lighting (morning/evening), varied road surfaces, and
   both with and without potholes in frame.
2. **Extract frames**: pull still frames out of the video every ~1 second —
   ```bash
   ffmpeg -i pothole_walk.mp4 -vf fps=1 frames/frame_%04d.jpg
   ```
3. **Label them**: use Roboflow's free web annotation tool (upload your
   frames, draw boxes around potholes, it exports in YOLO format directly) —
   or LabelImg (`pip install labelImg`) if you want a fully offline tool.
4. **Merge** these newly labeled images into the same `dataset/images/train`
   and `dataset/labels/train` folders from Option A.

### Labeling tips that matter for accuracy
- Draw the box tight around just the pothole/hazard, not a wide margin —
  loose boxes teach the model imprecise localization.
- Label partially-visible potholes at the frame edge too (helps the model
  handle real walking footage where hazards enter/exit frame).
- Include some "hard negative" images — puddles, manhole covers, shadows,
  drain grates — WITHOUT labeling them as potholes. This teaches the model
  what a pothole is NOT, which cuts down false alarms a lot.

## Option C — Other classes (zebra crossing, stairs, open drain)

Same process as Option B — these have far fewer public datasets available,
so you'll mostly be collecting and labeling your own. Realistically, budget
these as a Phase 2 addition after the pothole model is proven working, per
the project roadmap.

## How much data is "enough"?

- **Rough minimum** for a usable single-class model: 300-500 labeled images.
- **Good**: 1000-2000 images.
- Quality and variety matter more than raw count — 500 varied images (different
  lighting, angles, pothole sizes) beats 2000 near-identical ones.
