"""Submit or inspect one Stampede asset job through the installed Mixar app.

Run with mixar --background --factory-startup --python-exit-code 1
    --python scripts/stampede_mixar_job.py -- REQUEST.json submit|status

Requests and results belong in the ignored art/western/stampede directory.
Credentials stay inside Mixar's normal authentication client. A persisted
idempotency key prevents accidentally paying for a duplicate on retry.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import uuid

import bpy


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('action', choices=['submit', 'status', 'download'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use Mixar to run this script'
    from mixar.modules.common.api.services.job_queue_service import get_job_queue_service

    request = args.request.resolve()
    spec = json.loads(request.read_text())
    state_path = request.with_suffix('.job.json')
    fingerprint = hashlib.sha256(request.read_bytes()).hexdigest()
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        'request_sha256': fingerprint,
        'idempotency_key': str(uuid.uuid4()),
        'mixar_binary': bpy.app.binary_path,
        'mixar_version': bpy.app.version_string,
    }
    assert state['request_sha256'] == fingerprint, 'Create a new request for revised settings'
    if args.action == 'download':
        import requests
        from mixar.modules.common.job_queue.core.helpers import extract_image_urls
        assert state.get('response', {}).get('status') == 'DONE', 'Wait for completion'
        assert args.output and not args.output.exists(), 'Choose a new output file'
        result = state['response']['result']
        if spec['service'] == 'image_gen':
            urls = extract_image_urls(result)
        else:
            files = result.get('result_files', [])
            urls = [f['url'] for f in files if str(f.get('type', '')).lower() == 'glb']
        assert len(urls) == 1, 'Expected exactly one downloadable asset'
        response = requests.get(urls[0], timeout=60)
        response.raise_for_status()
        args.output.write_bytes(response.content)
        state['download'] = {'file': str(args.output.resolve()),
                             'sha256': hashlib.sha256(response.content).hexdigest()}
        write_json(state_path, state)
        print('STAMPEDE_DOWNLOAD', json.dumps(state['download']), flush=True)
        return
    service = get_job_queue_service()
    if args.action == 'submit' and not state.get('job_id'):
        # Historical documentation precedes paid generation, including revisions.
        evidence_name = spec.get('historical_evidence')
        assert evidence_name, 'New rendering requires a historical_evidence file'
        evidence_path = (request.parent / evidence_name).resolve()
        evidence = json.loads(evidence_path.read_text())
        assert evidence.get('date_scope') and evidence.get('location_scope'), 'Record historical date and place'
        assert evidence.get('sources') and evidence.get('render_brief'), 'Record sources and the supported rendering brief'
        assert all(s.get('url') and s.get('supports') for s in evidence['sources']), 'Map every source to its supported claim'
        assert evidence.get('history_lesson'), 'Every character requires a factual history note'
        state['historical_evidence_sha256'] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        payload = {'params': dict(spec['params'])}
        if spec.get('prompt'):
            payload['prompt'] = spec['prompt']
        if spec['service'] == 'image_gen':
            assert payload['prompt'].strip(), 'Image generation requires a prompt'
        if spec.get('image'):
            source = (request.parent / spec['image']).resolve()
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            assert state.get('image_sha256', digest) == digest, 'Generation input changed'
            state['image_sha256'] = digest
            payload.update(image_bytes_b64=base64.b64encode(source.read_bytes()).decode(),
                           image_filename=source.name)
        if spec.get('mesh'):
            source = (request.parent / spec['mesh']).resolve()
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            assert state.get('mesh_sha256', digest) == digest, 'Rigging input changed'
            assert source.stat().st_size <= 150 * 1024 * 1024, 'Mesh exceeds Mixar rig input limit'
            state['mesh_sha256'] = digest
            payload.update(file_bytes_b64=base64.b64encode(source.read_bytes()).decode(),
                           file_filename=source.name, input_name=spec.get('input_name', 'Stampede longhorn'))
        write_json(state_path, state)
        response = service.post('jobs', json={
            'service': spec['service'], 'model': spec['model'], 'payload': payload,
            'idempotency_key': state['idempotency_key'], 'max_retries': 0,
        }, timeout=60)
    else:
        assert state.get('job_id'), 'Submit this request first'
        response = service.get('jobs/' + str(state['job_id']), timeout=45)
    assert response.success, (response.status_code, response.message)
    result = service._normalize_response(response).data['data']
    if result.get('job_id'):
        state['job_id'] = result['job_id']
    state['response'] = result
    write_json(state_path, state)
    print('STAMPEDE_MIXAR_JOB', json.dumps({
        'job_id': state.get('job_id'), 'status': result.get('status'),
        'error': result.get('error'), 'result_fields': list((result.get('result') or {}).keys()),
        'state': str(state_path),
    }), flush=True)
    if result.get('status') in {'FAILED', 'CANCELLED', 'DLQ'}:
        raise RuntimeError(result.get('user_message') or 'Mixar generation failed')


if __name__ == '__main__':
    main()
