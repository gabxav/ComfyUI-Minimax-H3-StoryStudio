"""Sequential ComfyUI queue orchestration. Never runs a sampler in an HTTP handler."""
import asyncio
import copy
import json
import logging
import time
import uuid

from aiohttp import web
from .plan import parse_story, recipe_hash
from .runtime import (assemble, atomic_json, output_file, project_root, read_manifest, records_for)

LOG = logging.getLogger('StoryStudio')
JOBS = {}
TASKS = set()


def identify(graph):
    story_nodes = [k for k,n in graph.items() if n.get('class_type') in ('XavierH3Story', 'XavierH3StoryStudio')]
    outputs = [k for k,n in graph.items() if n.get('class_type') == 'XavierH3StoryOutput']
    if len(story_nodes) == 1 and graph[story_nodes[0]].get('class_type') == 'XavierH3StoryStudio':
        return story_nodes[0], story_nodes[0]
    if len(story_nodes) != 1 or len(outputs) != 1:
        raise ValueError('Use exactly one Story panel and one Story output in the workflow.')
    return story_nodes[0], outputs[0]


def job_status(pid):
    if pid in JOBS:
        return {k:v for k,v in JOBS[pid].items() if k != 'stop'}
    path = project_root(pid)/'job.json'
    if path.exists():
        d = json.loads(path.read_text())
        if d.get('status') in ('running', 'queued', 'assembling'):
            d.update(status='interrupted', message='ComfyUI restarted. Use Continue sequence to resume.')
        return d
    return {'status': 'idle'}


def publish(pid, job):
    atomic_json(project_root(pid)/'job.json', {k:v for k,v in job.items() if k != 'stop'})


async def enqueue(graph, workflow, client_id):
    import execution
    from server import PromptServer
    server = PromptServer.instance
    body = server.trigger_on_prompt({'prompt': graph, 'extra_data': {'extra_pnginfo': {'workflow': workflow}}, 'client_id': client_id})
    graph = body['prompt']
    server.node_replace_manager.apply_replacements(graph)
    prompt_id = str(uuid.uuid4())
    valid = await execution.validate_prompt(prompt_id, graph, None)
    if not valid[0]:
        raise ValueError(json.dumps({'error': valid[1], 'nodes': valid[3]}, ensure_ascii=False))
    extra = body.get('extra_data', {})
    if client_id:
        extra['client_id'] = client_id
    extra['create_time'] = int(time.time()*1000)
    number = server.number
    server.number += 1
    server.prompt_queue.put((number, prompt_id, graph, extra, valid[2], {}))
    return prompt_id


async def wait_prompt(prompt_id):
    from server import PromptServer
    queue = PromptServer.instance.prompt_queue
    absent_since = None
    while True:
        history = queue.get_history(prompt_id=prompt_id)
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get('status', {})
            if status.get('status_str') != 'success':
                errors = [m[1] for m in status.get('messages', []) if m[0] in ('execution_error', 'execution_interrupted')]
                raise RuntimeError(json.dumps(errors or status, ensure_ascii=False)[-2500:])
            return entry
        running, pending = queue.get_current_queue()
        if any(item[1] == prompt_id for item in running+pending):
            absent_since = None
        else:
            absent_since = absent_since or time.monotonic()
            if time.monotonic()-absent_since > 10:
                raise RuntimeError('The scene was removed from the queue. Use Continue sequence to resume.')
        await asyncio.sleep(2)


async def run_job(pid, data, story, node_id, indices):
    job = JOBS[pid]
    graph = data['prompt']
    recipe = recipe_hash(graph)
    try:
        for index in indices:
            if job['stop']:
                break
            job.update(status='running', scene_index=index+1, message=f'Generating scene {index+1}/{len(story["scenes"])}')
            publish(pid, job)
            current = copy.deepcopy(graph)
            token = uuid.uuid4().hex
            current[node_id]['inputs'].update(story_json=json.dumps(story, ensure_ascii=False), scene_index=index+1, execution_token=token)
            prompt_id = await enqueue(current, data.get('workflow', {}), data.get('client_id'))
            job['prompt_id'] = prompt_id
            publish(pid, job)
            await wait_prompt(prompt_id)
            _, records = records_for(story, recipe)
            if not records[index] or records[index].get('execution_token') != token:
                raise RuntimeError('Execution finished without saving the expected scene result.')
            job['completed'].append(index+1)
        _, records = records_for(story, recipe)
        if not job['stop'] and all(records):
            job.update(status='assembling', message='Assembling the complete film')
            publish(pid, job)
            file = await asyncio.to_thread(assemble, pid, records)
            manifest = read_manifest(pid)
            manifest['assembled'] = {'video': file, 'revisions': [r['revision'] for r in records]}
            atomic_json(project_root(pid)/'manifest.json', manifest)
            job['video'] = file
        job.update(status='paused' if job['stop'] else 'complete', message='Paused after the current scene' if job['stop'] else 'Generation complete')
    except Exception as exc:
        LOG.exception('Story %s failed', pid)
        job.update(status='failed', message=str(exc))
    finally:
        job['finished_at'] = time.time()
        publish(pid, job)


def register_routes():
    from server import PromptServer
    routes = PromptServer.instance.routes

    @routes.post('/xavier-story/status')
    async def status(request):
        try:
            d = await request.json()
            story = parse_story(d['story'])
            _, records = records_for(story, recipe_hash(d['prompt']))
            manifest = read_manifest(story['project_id'])
            assembled = manifest.get('assembled')
            if assembled and (not all(records) or assembled['revisions'] != [r['revision'] for r in records]):
                assembled = None
            return web.json_response({'job': job_status(story['project_id']), 'scenes': records, 'assembled': assembled})
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)

    @routes.post('/xavier-story/start')
    async def start(request):
        try:
            d = await request.json()
            node_id, _ = identify(d['prompt'])
            story = parse_story(d['prompt'][node_id]['inputs']['story_json'])
            pid = story['project_id']
            if JOBS.get(pid, {}).get('status') in ('running', 'queued', 'assembling'):
                return web.json_response({'error': 'This story is already running.'}, status=409)
            _, records = records_for(story, recipe_hash(d['prompt']))
            mode = d.get('mode', 'continue')
            if mode == 'selected':
                index = int(d.get('scene_index', 1))-1
                if not 0 <= index < len(records):
                    raise ValueError('Invalid scene.')
                if story['scenes'][index]['continue_previous'] and not records[index-1]:
                    raise ValueError('Generate the previous scene first or use Continue sequence.')
                indices = [index]
            elif mode in ('continue', 'next'):
                missing = next((i for i,r in enumerate(records) if not r), None)
                if missing is None:
                    indices = []  # Reassemble valid scenes, without regenerating.
                else:
                    indices = [missing] if mode == 'next' else list(range(missing, len(records)))
            else:
                raise ValueError('Invalid mode.')
            # Validate graph before returning success or starting an async job.
            import execution
            valid = await execution.validate_prompt(str(uuid.uuid4()), copy.deepcopy(d['prompt']), None)
            if not valid[0]:
                raise ValueError(json.dumps({'error': valid[1], 'nodes': valid[3]}, ensure_ascii=False))
            if JOBS.get(pid, {}).get('status') in ('running', 'queued', 'assembling'):
                return web.json_response({'error': 'This story is already running.'}, status=409)
            job = {'id': uuid.uuid4().hex, 'status': 'queued', 'stop': False, 'completed': [],
                   'planned': [i+1 for i in indices], 'started_at': time.time(), 'message': 'Preparing the sequence'}
            JOBS[pid] = job
            publish(pid, job)
            task = asyncio.create_task(run_job(pid, d, story, node_id, indices))
            TASKS.add(task)
            task.add_done_callback(TASKS.discard)
            return web.json_response({'job': job_status(pid)})
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)

    @routes.post('/xavier-story/pause')
    async def pause(request):
        from .plan import project_id
        try:
            pid = project_id((await request.json())['project_id'])
            if pid in JOBS:
                JOBS[pid]['stop'] = True
                publish(pid, JOBS[pid])
            return web.json_response({'job': job_status(pid)})
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)
