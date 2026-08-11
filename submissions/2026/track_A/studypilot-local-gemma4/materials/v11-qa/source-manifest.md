# V11 Source Manifest

Generated: 2026-08-10 (Asia/Shanghai)

V11 is an independent source and QA tree. The eight SVGs below are the
user-approved review sources. `v10-assets/` and the formal V10 release remain
unchanged.

## Assembly map

| Logical page | V11 source | Assembly treatment |
|---|---|---|
| P1 | `svg_output/01_时间规划小助手.svg` | native shapes from staging |
| P2 | `svg_output/02_初一的晚上.svg` | native shapes from staging |
| P3 | formal V10 slide 3 | inherited byte-for-byte |
| P4 | formal V10 slide 4 | inherited, including frozen MP4 |
| P5 | `svg_output/05_model_testing.svg` | native shapes from staging |
| P6 | `svg_output/06_harness.svg` | native shapes from staging |
| P7 | `svg_output/07_stateful_loop.svg` | native shapes from staging |
| P8 | `svg_output/08_dual_loop.svg` | native shapes from staging |
| P9 | `svg_output/09_validation.svg` | native shapes from staging |
| P10 | `svg_output/10_father_daughter.svg` | PowerPoint-exported single PNG |

## Approved SVG hashes

| Page | File | Bytes | SHA256 |
|---|---|---:|---|
| P1 | `svg_output/01_时间规划小助手.svg` | 4289 | `A68A48F7773B98F32A869FEDE0ADDB0C5CD33772D62A64783FA34735181A1BAD` |
| P2 | `svg_output/02_初一的晚上.svg` | 3797 | `D94AFDD98757B6D7ACE14F300E7C6BC7B504AD41DC8F709CF6B94D62BD3381E5` |
| P5 | `svg_output/05_model_testing.svg` | 7475 | `66F19624B1753AB1B8FD4B0F7ECECC4136BD06B9E0078D79794CB6AEF494B756` |
| P6 | `svg_output/06_harness.svg` | 10012 | `EA7E9DA6A2B91140075DD3F7A0A856FC8AEA2901C2F0F1D0F558D1CDEC739B02` |
| P7 | `svg_output/07_stateful_loop.svg` | 8943 | `7B70E694B0301A44A58572CEF70E15AB2D39DFF470D09AFE3DC26A8EE592F901` |
| P8 | `svg_output/08_dual_loop.svg` | 10834 | `93929820318E8BB649263B18DFCD4DC287E1350E256F45663C783862E6C57CBC` |
| P9 | `svg_output/09_validation.svg` | 6602 | `79529C7A4EE7D140C14A1F8460F27D3987B941DBBFA82CD329DF6AA34BB96792` |
| P10 | `svg_output/10_father_daughter.svg` | 5564 | `6CF4F73C5280B086530A66CE3F10BAFDBAF069ACC4409901BC86E5B9078A4112` |

## Frozen external inputs

- Formal V10: `release/时间规划小助手_决赛路演V10_评测驱动架构版.pptx`, 15764860 bytes, SHA256 `E051FABFC325600A977F21ABAF13034AAB7BEE6E3B4AAAF08D967EFD2D5DC125`.
- V7 MP4: `release/时间规划小助手_决赛演示视频_V7_100秒完整落底版.mp4`, 15090148 bytes, SHA256 `F47F6788A1FC4E98D5640468543206E412A6C36B63E12421B6FE13C4960947B7`.

## Generated staging

- Native eight-slide staging: `stage/v11-content-native.pptx`, 70440 bytes, SHA256 `F372B9CE74952B117FA49BBFF4D64907D9FC5A15EEB5821396CDC7C2AEB71634`.
- P10 export: `stage/10_father_daughter_1920x1080.png`, 1920x1080, 121964 bytes, SHA256 `5AC723CA31882DFDFC309DFF256FF438ECB5E181F2EEA8A6D53E074AD8953171`.
- Audited RC: `stage/时间规划小助手_决赛路演V11_产品闭环讲清版-RC.pptx`, 15767129 bytes, SHA256 `01EE030CFF8E49EF09C89257DF158DCDC98F1E9EE4F82E464FF433D8F8D6452C`.

No V11 video was generated. The product code, database, prompts, model
configuration, P3, P4, and the frozen MP4 were not modified.
