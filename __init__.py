from .nodes import XavierH3Story, XavierH3StoryOutput, XavierH3StoryStudio

NODE_CLASS_MAPPINGS = {'XavierH3StoryStudio': XavierH3StoryStudio, 'XavierH3Story': XavierH3Story, 'XavierH3StoryOutput': XavierH3StoryOutput}
NODE_DISPLAY_NAME_MAPPINGS = {'XavierH3StoryStudio': 'ComfyUI-Minimax-H3-StoryStudio', 'XavierH3Story': 'StoryStudio · Scene Conditioning', 'XavierH3StoryOutput': 'StoryStudio · Save Scene and Continuity'}
from .vendor.audio_refine.nodes import H3AudioRefineSampler, H3FrozenVideoCache

NODE_CLASS_MAPPINGS.update({
    'StoryStudioH3AudioRefineSampler': H3AudioRefineSampler,
    'StoryStudioH3FrozenVideoCache': H3FrozenVideoCache,
})
NODE_DISPLAY_NAME_MAPPINGS.update({
    'StoryStudioH3AudioRefineSampler': 'StoryStudio · Audio Refine',
    'StoryStudioH3FrozenVideoCache': 'StoryStudio · Frozen Video Cache (RAM fix)',
})
WEB_DIRECTORY = './web'
__version__ = '0.2.0'

# Importing in a standalone validator must not create a PromptServer.
from server import PromptServer
if getattr(PromptServer, 'instance', None) is not None:
    from .service import register_routes
    register_routes()
