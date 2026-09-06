[← README](../README.md)

# StoryStudio quick start

**One node to organize prompts, references and a story across scenes of up to 15 seconds.** Each scene's final frames and audio can provide temporal context for the next. AudioRefine is included with the RAM retention fix.

![StoryStudio](assets/banner.svg)

## Installation

1. Use a recent ComfyUI version with native MiniMax H3 support, compatible models, CLIP, and video/audio VAEs.
2. Install [AIMixer's Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director), which provides temporal context.
3. Clone this repository into `ComfyUI/custom_nodes/ComfyUI-Minimax-H3-StoryStudio`.
4. Install `requirements.txt` using ComfyUI's Python. Make FFmpeg and ffprobe available on `PATH`.
5. Wait for the queue to finish, restart ComfyUI and refresh your browser.

```bash
cd ComfyUI
git clone https://github.com/gabxav/ComfyUI-Minimax-H3-StoryStudio.git custom_nodes/ComfyUI-Minimax-H3-StoryStudio
```

Using the interpreter that runs ComfyUI:

```bash
python -m pip install -r custom_nodes/ComfyUI-Minimax-H3-StoryStudio/requirements.txt
```

Adjust paths for your current directory. On Windows portable, use `python_embeded\python.exe`. If you have an older local StoryStudio version, move its directory outside `custom_nodes` before restarting; keep only one installation.

The separate AudioRefine package is not required. KJNodes/SageAttention are optional: select `attention=disabled` if they are unavailable.

## Your first story

Import [workflows/story_studio.json](../workflows/story_studio.json). The example contains three generic scenes without media files and starts at 512 × 512.

1. Select the **REF2VA**, **FL2VA**, **CLIP**, **video VAE** and **audio VAE** files available in your installation.
2. Choose the Turbo LoRA and sampling steps appropriate for your model. REF2VA generates video and audio; FL2VA is used only when refinement is enabled.
3. Click **Open Story Studio**.
4. Edit each scene's prompt and duration. Add images, videos and audio in the editor.
5. Click **Continue sequence**.

![Scene editor](assets/editor.png)

Shared references apply to every scene. Extra references apply only to the selected scene. Use the numbers shown in the editor: `<Picture 1>`, `<Video 1>` and `<Audio 1>`. Shared and individual references together allow up to 9 images, 3 videos and 3 audio references per scene.

For video and audio, choose a starting time and a segment of up to 15 seconds. A video reference provides frames; to also use its soundtrack as an audio reference, add the same file to the Audio column.

There are no `reference_image`, `reference_video` or `reference_audio` connectors on the main node. All references are managed inside the editor.

## Continue, regenerate and pause

| Button | Result |
| --- | --- |
| **Continue sequence** | Generate from the first pending or outdated scene to the last, then assemble the film. |
| **Generate next scene** | Generate only the next pending scene. |
| **Generate / redo selected** | Create a new take of the selected scene. |
| **Stop after this scene** | Finish the current scene without queuing another. |

Saving in the editor updates the open node. Also use ComfyUI's **Save workflow** action to preserve your changes. The sequence continues on the server after the editor closes. After a server restart, use **Continue sequence** to resume.

Regenerating a scene marks later scenes that depend on it as outdated. Previous takes remain on disk. To start another project while keeping the script, use **Create a new story from this one**.

## Continuity and audio

The default uses the **final 22 frames at 24 fps**, about 0.92 seconds, and the matching audio tail. These are encoded as temporal context for the next generation. The context segment and extra frames are then removed: each 15-second scene exports 360 frames.

The internal H3 grid is `17k + 5`: the first scene uses 362 frames; with 22 context frames, it uses 396. This internal window exceeds approximately 15 seconds. Quality depends on the model, prompt and context length; invisible transitions, perfect faces, exact dialogue and identical backgrounds are not guaranteed.

- **audio_refine:** enables a second pass with FL2VA, without Turbo LoRA.
- **audio_steps / audio_denoise:** control refinement steps and strength.
- **audio_cache:** uses `hidden / int4 / auto` caching without disk caching. This is an approximation and can be disabled for comparison.

## Included RAM fix

[AudioRefine PR #1](https://github.com/Adudeguyman/ComfyUI-H3-AudioRefine/pull/1) proposes keeping persistent cache tensors in ordinary CPU memory with `pin_memory=False`. This prevents PyTorch's pinned-memory allocator from retaining those large blocks after repeated cache rebuilds. Transfers may be slower than transfers from pinned RAM.

StoryStudio includes the files from commit `34862c6` with this fix, without depending on PR approval or changing another AudioRefine installation. See [credits, hashes and license](../THIRD_PARTY_NOTICES.md).

## Output locations

`ComfyUI/output/story_director/<project_id>/` contains individual videos, `.pt` checkpoints, `manifest.json`, `job.json` and the assembled film. Keep checkpoints to continue from saved scenes. New files use `scene_` and `film_` prefixes; existing manifest entries continue to resolve their original filenames.

Initial validation generated three real 15-second scenes at 512 × 512, exercised continuation, refinement, retakes, pause and resume, and produced a 45-second film. See the [README](../README.md#validation-and-limits) for test coverage and limitations.
