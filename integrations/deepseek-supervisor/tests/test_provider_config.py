"""Saved custom routes are reused without copying keys or assuming reasoning support."""
import json
import os
from pathlib import Path
import pytest
import yaml
from supervisor.configuration import available_models, provider_definition
from supervisor.runtime import Harness


@pytest.fixture
def provider_config(tmp_path, monkeypatch):
    patch = tmp_path / 'desktop.patch.yml'
    settings = tmp_path / 'settings.json'
    definition = {'displayName': 'Local test', 'api': 'anthropic-messages',
        'apiKeyEnv': 'LOCAL_TEST_API_KEY', 'baseURL': 'http://127.0.0.1:8000/v1',
        'models': [{'id': 'local-one', 'name': 'Local one', 'contextWindow': 100000},
                   {'id': 'local-two', 'name': 'Local two'}]}
    patch.write_text(yaml.safe_dump([{'id': 'llm-pi-ai', 'config': {'providers': {'local': definition}}}]))
    settings.write_text(json.dumps({'provider': 'local', 'model': 'local-one',
        'provider_config': str(patch), 'harness_exe': 'fake.exe', 'harness_cli': 'fake.js',
        'profile_path': str(tmp_path / 'base.patch.yml'), 'reasoning_effort': 'high',
        'max_tokens': 1000, 'concurrency': 4}))
    monkeypatch.setenv('SC2_DEEPSEEK_CONFIG', str(settings))
    return patch, definition


def test_model_discovery_exposes_ids_without_endpoint_or_credential_values(provider_config):
    result = available_models()
    assert result['default_model'] == 'local-one'
    assert result['providers'][0]['models'] == ['local-one', 'local-two']
    assert '127.0.0.1' not in json.dumps(result)
    assert provider_definition('local', 'local-two')['apiKeyEnv'] == 'LOCAL_TEST_API_KEY'
    with pytest.raises(ValueError, match='selected Harness provider catalog'):
        provider_definition('local', 'unknown-model')


def test_inline_secret_is_refused(provider_config):
    patch, definition = provider_config
    definition['apiKey'] = 'test-only-not-a-real-key'
    patch.write_text(yaml.safe_dump([{'id': 'llm-pi-ai', 'config': {'providers': {'local': definition}}}]))
    with pytest.raises(ValueError, match='inline secrets'):
        provider_definition('local', 'local-one')


@pytest.mark.asyncio
async def test_custom_model_does_not_inherit_official_reasoning_and_keeps_keys_out_of_tools(tmp_path, monkeypatch, provider_config):
    import supervisor.runtime as runtime
    calls = {}
    class Process:
        pid = os.getpid()
        returncode = 0
        stdin = None
    class Job:
        def __init__(self, pid): pass
        def close(self): pass
    async def spawn(*args, **kwargs):
        calls['arguments'] = args
        calls['environment'] = kwargs['env']
        return Process()
    monkeypatch.setattr(runtime.asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr(runtime, 'ProcessJob', Job)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only-not-a-real-key')
    harness = Harness(tmp_path / 'candidate', tmp_path / 'run', model='local-two', provider='local')
    async def request(method, options, timeout):
        calls[method] = options
        return {'serverInfo': {'name': 'deepseek-harness-sdk-runtime'}}
    async def no_stream(): pass
    harness.request = request
    harness._stdout = no_stream
    harness._stderr = no_stream
    try:
        await harness.start()
        assert calls['initialize']['provider'] == 'local'
        assert calls['initialize']['model'] == 'local-two'
        assert 'reasoningEffort' not in calls['initialize']
        assert calls['environment']['__COMPAT_LAYER'] == 'RunAsInvoker'
        assert 'DEEPSEEK_API_KEY' not in calls['environment']
        materialized = yaml.safe_load((tmp_path / 'run/provider.patch.yml').read_text())
        assert materialized[0]['config']['providers']['local']['apiKeyEnv'] == 'LOCAL_TEST_API_KEY'
        assert not (tmp_path / 'candidate/provider.patch.yml').exists()
    finally:
        await harness.close()
