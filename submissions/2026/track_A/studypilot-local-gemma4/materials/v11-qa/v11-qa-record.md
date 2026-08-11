# V11 QA Record

Status: PASS

Initial V11 build: 2026-08-10 (Asia/Shanghai)
Fresh final contract verification: 2026-08-11 10:32:29 +08:00

## Audited artifacts

- Formal target: `release/时间规划小助手_决赛路演V11_产品闭环讲清版.pptx`
- RC path: `v11-assets/stage/时间规划小助手_决赛路演V11_产品闭环讲清版-RC.pptx`
- RC byte length: 15767129
- RC SHA256: 01EE030CFF8E49EF09C89257DF158DCDC98F1E9EE4F82E464FF433D8F8D6452C
- Native staging: `v11-assets/stage/v11-content-native.pptx` (`70440` bytes; SHA256 `F372B9CE74952B117FA49BBFF4D64907D9FC5A15EEB5821396CDC7C2AEB71634`)
- Staging closing PNG: `v11-assets/stage/10_father_daughter_1920x1080.png` (`1920x1080`, `121964` bytes; SHA256 `5AC723CA31882DFDFC309DFF256FF438ECB5E181F2EEA8A6D53E074AD8953171`)

## Frozen inputs

- Formal V10: `release/时间规划小助手_决赛路演V10_评测驱动架构版.pptx` (`15764860` bytes; SHA256 `E051FABFC325600A977F21ABAF13034AAB7BEE6E3B4AAAF08D967EFD2D5DC125`)
- Frozen V7 MP4: `release/时间规划小助手_决赛演示视频_V7_100秒完整落底版.mp4` (`15090148` bytes; SHA256 `F47F6788A1FC4E98D5640468543206E412A6C36B63E12421B6FE13C4960947B7`)

## Commands and results

1. `powershell -NoProfile -ExecutionPolicy Bypass -File pitch/final-roadshow-v1/test-roadshow-v11.ps1`
   - Result: `V11 source-contract checks passed.`
2. `powershell -NoProfile -ExecutionPolicy Bypass -File pitch/final-roadshow-v1/test-roadshow-v11.ps1 -PptxPath pitch/final-roadshow-v1/v11-assets/stage/时间规划小助手_决赛路演V11_产品闭环讲清版-RC.pptx`
   - Result: `V11 roadshow source and package-contract checks passed.`
   - Includes SVG/source hashes, PowerPoint COM rendering, OOXML package checks, frozen V10/MP4 checks, and `slides_test.py`.
3. SVG quality checker: 8/8 approved SVGs, 0 warnings, 0 errors.
4. PowerPoint evidence renders: all 10 pages at `1920x1080`; changed pages P1/P2/P5-P10 also at `960x540`. The 1920 and 960 montages, plus P6/P7/P10 full-size renders, were visually inspected.

## Package contract

- 10 slides and 10 speaker-note parts.
- Exactly one embedded MP4, related only to logical P4; embedded hash equals the frozen V7 hash.
- 0 SVG media entries and 0 external media relationships.
- P1, P2, P5-P9 are native shape pages with no picture surface.
- P10 contains exactly one PNG surface; its embedded hash equals the staging PNG hash.
- P3 and P4 PowerPoint renders are byte-baseline equivalent to formal V10.
- P1/P2/P5-P9 render exactly match their native staging pages; P10 is visually equal to staging.
- `slides_test.py`: `Test passed. No overflow detected.`

## Rehearsal and authorization boundary

Timed rehearsals were **NOT EXECUTED**. No duration or rehearsal result is estimated or fabricated. Formal publication is authorized by the user's explicit request, recorded as `USER_REQUESTED_FORMAL_V11_BUILD`, after manual SVG review.

## Publication verification

- Published formal path: `release/时间规划小助手_决赛路演V11_产品闭环讲清版.pptx`.
- Formal byte length: 15767129
- Formal SHA256: 01EE030CFF8E49EF09C89257DF158DCDC98F1E9EE4F82E464FF433D8F8D6452C
- RC/formal byte equality: `PASS`.
- Post-publication formal contract: `V11 roadshow source and package-contract checks passed.`
- Second publish attempt: refused by the no-overwrite guard (`PASS`).
