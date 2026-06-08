# UR Fall Video Validation Subset

This folder defines the video validation subset used to test the video detection flow.

Source dataset:

- UR Fall Detection Dataset
- Dataset page: https://fenix.ur.edu.pl/~mkepski/ds/uf.html

Downloaded local videos:

- 60 fall clips: `fall-01` through `fall-30`, `cam0` and `cam1`
- 40 no-fall ADL clips: `adl-01` through `adl-40`, `cam0`
- Total: 100 MP4 videos, about 120.7 MB

Manifest:

```text
video_validation/urfall_full_manifest.csv
```

Purpose:

- Validate that the video reader can open real fall/no-fall videos.
- Validate frame-by-frame YOLO inference.
- Validate false positives on ADL/no-fall clips.
- Validate that fall clips produce fall detections across multiple frames.

Run one clip:

```powershell
python detection.py --source inputs\urfall_fall_01_cam0.mp4 --weights weights\best.pt --name urfall_fall_01 --max-frames 0
```

Run the no-fall control clip:

```powershell
python detection.py --source inputs\urfall_adl_01_cam0.mp4 --weights weights\best.pt --name urfall_adl_01 --max-frames 0
```

Expected validation rule:

- Fall clips should contain at least one sustained segment with fall detections.
- ADL/no-fall clips should remain mostly negative. Occasional single-frame false positives should be reviewed, not treated as automatic success.

Run full validation:

```powershell
python evaluate_video_validation.py --manifest video_validation\urfall_full_manifest.csv --weights weights\best.pt --output-dir outputs\video_validation_full --confirm-frames 5 --min-fall-ratio 0.35
```

Current full baseline:

```text
items: 100
accuracy: 0.86
tp: 53
tn: 33
fp: 7
fn: 7
```
