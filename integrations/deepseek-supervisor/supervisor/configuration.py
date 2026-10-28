"""Local runtime settings; credentials remain exclusively owned by Harness."""
import json
import os
import re
from pathlib import Path
from .agent_bridge import user_config
from .runtime_root import ROOT


def configured_providers():
    """Read only saved provider definitions; never open the credential store."""
    import yaml
    config = load_config()
    path = Path(config.get('provider_config', Path.home() / '.dsh/profiles/desktop/cordis.patch.yml'))
    if not path.exists():
        return {}
    rows = yaml.safe_load(path.read_text(encoding='utf-8-sig')) or []
    providers = {}
    for row in rows:
        if isinstance(row, dict) and row.get('id') == 'llm-pi-ai':
            providers.update(row.get('config', {}).get('providers', {}))
    return providers


def provider_definition(provider, model):
    providers = configured_providers()
    if provider == 'deepseek-official':
        return None
    if provider not in providers:
        raise ValueError('Provider is not in the saved Harness model settings: ' + provider)
    definition = providers[provider]
    def check(value):
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = re.sub('[^a-z]', '', key.lower())
                if normalized in ('apikey', 'authorization', 'token', 'secret', 'password'):
                    raise ValueError('Provider settings must reference the Harness credential service, not inline secrets')
                if normalized == 'apikeyenv' and not re.fullmatch(r'[A-Z_][A-Z_0-9]*', str(child)):
                    raise ValueError('apiKeyEnv must be an environment-name reference')
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(definition)
    models = definition.get('models', [])
    ids = list(models) if isinstance(models, dict) else [item['id'] for item in models]
    if ids and model not in ids:
        raise ValueError('Model is not in the selected Harness provider catalog: ' + model)
    return definition


def available_models():
    config = load_config()
    result = []
    for name, definition in configured_providers().items():
        models = definition.get('models', [])
        result.append({'provider': name, 'display_name': definition.get('displayName', name),
            'protocol': definition.get('api'), 'models': list(models) if isinstance(models, dict) else [m['id'] for m in models]})
    return {'default_provider': config['provider'], 'default_model': config['model'],
            'providers': result, 'credential_contents_read': False, 'endpoint_values_exposed': False}


def load_config():
    override = os.environ.get('SC2_DEEPSEEK_CONFIG')
    if override:
        return json.loads(Path(override).read_text(encoding='utf-8-sig'))
    settings = user_config().get('deepseek')
    if settings:
        return settings
    path = ROOT / 'config.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8-sig'))
    raise ValueError('DeepSeek is not configured; run the workspace integration setup tool')


def capabilities():
    path = ROOT / 'reports/capabilities.json'
    evidence = json.loads(path.read_text('utf-8')) if path.exists() else None
    summary = {key: evidence.get(key) for key in ('status', 'harness_version', 'recorded_date',
        'plugin_sha256', 'recommended_default_model', 'effective_routing', 'supported_tools', 'limitations')} if evidence else None
    return {'execution': 'isolated-candidate-files', 'requires_supervisor_review': True,
            'automatic_delegation_scope': 'authorized_sc2_subtasks',
            'historical_evaluation': summary, 'historical_evaluation_file': str(path),
            'historical_evaluation_is_current_acceptance': False,
            'model_selection': available_models(),
            'concurrency': load_config()['concurrency']}


def diagnose():
    config = load_config()
    checks = {name: Path(config[name]).exists() for name in ('harness_exe', 'harness_cli')}
    # Electron resolves paths inside app.asar; pathlib cannot inspect those virtual members.
    cli = str(config['harness_cli']).replace('\\', '/')
    if '/app.asar/' in cli:
        checks['harness_cli'] = Path(cli.split('/app.asar/')[0] + '/app.asar').is_file()
    from .sc2_bridge import SC2BridgeWorker
    checks['sc2_runtime'] = SC2BridgeWorker.python_path() is not None
    checks['credential_file_present'] = Path(config.get('credential_file', Path.home() / '.dsh/.credentials.yaml')).is_file()
    return {'ok': all(checks.values()), 'checks': checks,
            'provider': config['provider'], 'model': config['model'],
            'harness_launch': 'not_tested', 'credential_contents_read': False}
