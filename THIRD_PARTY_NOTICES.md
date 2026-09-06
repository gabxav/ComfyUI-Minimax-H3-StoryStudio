# Third-party components

## Bundled: ComfyUI-H3-AudioRefine

- Author: Adudeguyman; copyright (c) 2026 Adudeguyman.
- Source: https://github.com/Adudeguyman/ComfyUI-H3-AudioRefine
- Snapshot: `d0ed019b6f1c4ceb0caf3d69c502a313d1f6da9d` with Gabriel Xavier's pageable RAM correction, as published in commit [`34862c6bf9a85a14495e9ed0e3e21b38c7375999`](https://github.com/gabxav/ComfyUI-H3-AudioRefine/commit/34862c6bf9a85a14495e9ed0e3e21b38c7375999).
- Upstream proposal: [PR #1 — Fix retained host memory in H3 RAM cache](https://github.com/Adudeguyman/ComfyUI-H3-AudioRefine/pull/1), open and unmerged when verified on September 5, 2026 UTC.
- Files: `vendor/audio_refine/nodes.py` and `vendor/audio_refine/frozen_cache.py`, copied verbatim from that commit.
- License: MIT; full original notice in [vendor/audio_refine/LICENSE](vendor/audio_refine/LICENSE).

StoryStudio registers the sampler and cache under distinct `StoryStudioH3*` node IDs and uses them in its internal graph. It does not replace the original extension's node registrations or edit its installation. The bundled cache uses `pin_memory=False` for persistent RAM tensors. The upstream VRAM and disk staging implementations are unchanged.

SHA-256 of the bundled source files:

| File | SHA-256 |
| --- | --- |
| `nodes.py` | `409a6cf2f855f1828983185ab53827444569cebd5d8535ad40e4e79953c1dc47` |
| `frozen_cache.py` | `1a94ae80e774e111883737c5f5f96bcab82fcf28c9dabe546b9e52717dd53e3e` |
| `LICENSE` | `19cb889133b1980bcd71089c0caebbe453602b145ff3bcd3e8cbe623ff1ab0ad` |

## Bundled: Director temporal helpers

- Source: [AIMixer/ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director).
- Snapshot: [`b8f721cb145490cb2c13c8944ff90f21551570f8`](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/tree/b8f721cb145490cb2c13c8944ff90f21551570f8).
- Files: `director/h3_motion_context.py`, `director/h3_context_patches.py` and `director/frame_align.py`, copied byte-for-byte into `vendor/director/`. These files implement temporal context, compatible H3 layout/payload patches and frame alignment.
- License: Apache-2.0; the complete upstream license, including its copyright notice, is retained in [vendor/director/LICENSE](vendor/director/LICENSE). No upstream root NOTICE file was present at this snapshot.
- Modifications: none to the three source files or license. StoryStudio adds its own package initializer and imports the helpers locally. No Director UI, node registration or installation is loaded.
- Existing upstream patch markers are retained so identical implementations can share an already-installed patch instead of double-wrapping ComfyUI functions.

SHA-256 of the bundled files (original line endings preserved):

| File | SHA-256 |
| --- | --- |
| `h3_motion_context.py` | `1901cfcb5b9c02a338266bd830b7a46ce3b2bbac8166d673b17280c27840b19d` |
| `h3_context_patches.py` | `08aea5c494d4df9f67fce9e818b42588c304b4b9cd0f486ec59ddc8e044b2dcd` |
| `frame_align.py` | `cb774f298963417e869956bb9392bc09b7f9fe47714b0453d24f83c078ee58ed` |
| `LICENSE` | `367fe288aba854ae7d586c5cd3df10183c8880e7776531de3ba12d2300df9ae2` |

## External dependencies

- [ComfyUI](https://github.com/Comfy-Org/ComfyUI): native MiniMax H3 conditioning, models, sampling and media types.
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes): optional SageAttention patch node when `attention=auto`.

Model weights, reference media and those projects' code are not included, except for the explicitly identified AudioRefine and Director files above. Their respective licenses apply.
