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

## External dependencies

- [ComfyUI](https://github.com/Comfy-Org/ComfyUI): native MiniMax H3 conditioning, models, sampling and media types.
- [AIMixer/ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director): temporal motion-context helper, imported from the user's installation. Its source is not bundled here.
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes): optional SageAttention patch node when `attention=auto`.

Model weights, reference media and those projects' code are not included, except for the explicitly identified AudioRefine files above. Their respective licenses apply.
