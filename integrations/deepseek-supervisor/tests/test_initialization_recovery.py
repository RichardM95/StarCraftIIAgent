import asyncio
import pytest

def test_failed_initialization_is_queryable_and_retryable(tmp_path,monkeypatch):
    from supervisor import manager as module
    monkeypatch.setattr(module,'load_config',lambda:dict(concurrency=1,provider='test',model='test'))
    monkeypatch.setattr(module,'provider_definition',lambda *args:None)
    manager=module.Manager(tmp_path/'tasks')
    monkeypatch.setattr(manager,'_schedule',lambda key,coroutine:coroutine.close())
    source=tmp_path/'source';source.mkdir()
    spec=module.TaskSpec(workspace=str(source),request_id='missing-input',goal='inspect',
                         acceptance='test',input_files=['missing.txt'])
    async def exercise():
        with pytest.raises(ValueError,match='Missing input'):
            await manager.submit(spec)
        import uuid
        key=uuid.uuid5(uuid.NAMESPACE_URL,'deepseek-supervisor:missing-input').hex
        assert manager.status(key)['phase']=='input_validation'
        assert manager.result(key)['changes']==[]
        (source/'missing.txt').write_text('restored')
        result=await manager.submit(spec)
        assert result['task_id']==key and result['state']=='queued'
        assert [row['task_id'] for row in manager.list_tasks()]==[key]
    asyncio.run(exercise())


def test_budget_resets_for_resumed_session(tmp_path,monkeypatch):
    import json
    from supervisor import manager as module
    monkeypatch.setattr(module,'load_config',lambda:dict(concurrency=1,provider='test',model='test'))
    manager=module.Manager(tmp_path/'tasks');key='a'*32
    directory=manager.directory(key);directory.mkdir()
    module.atomic_json(directory/'spec.json',{'max_tool_calls':2})
    manager.save(key,state='failed')
    rows=[{'type':'agent.created','session':'same'},
          *[{'type':'tool.attempt','session':'same','denied':True,'reason':'Task tool-call limit reached'}]*3,
          {'type':'session.resumed','session':'same'},
          {'type':'tool.attempt','session':'same','denied':False}]
    (directory/'audit.jsonl').write_text('\n'.join(json.dumps(row) for row in rows),encoding='utf-8')
    record=manager.status(key)
    assert record['budget']['used_total']==4 and record['budget']['used_current']==1
    assert record['budget']['remaining']==1 and 'failure_category' not in record


def test_policy_records_original_bom(tmp_path):
    from supervisor.policy import make_policy
    import json
    root=tmp_path/'workspace';root.mkdir()
    (root/'GameStrings.txt').write_bytes(b'\xef\xbb\xbfA=B')
    run=tmp_path/'run'
    make_policy(run,root,goal='preserve',allowed_files=['GameStrings.txt'],profile='sc2')
    assert json.loads((run/'contract.json').read_text('utf-8'))['string_bom']=={'GameStrings.txt':True}


def test_invalid_model_is_recorded_before_candidate_creation(tmp_path,monkeypatch):
    import uuid
    from supervisor import manager as module
    monkeypatch.setattr(module,'load_config',lambda:dict(concurrency=1,provider='bad',model='absent'))
    def invalid(*args):raise ValueError('Model is not in the selected provider catalog')
    monkeypatch.setattr(module,'provider_definition',invalid)
    manager=module.Manager(tmp_path/'tasks');source=tmp_path/'source';source.mkdir()
    spec=module.TaskSpec(workspace=str(source),request_id='invalid-model',goal='inspect',acceptance='not launched')
    async def exercise():
        with pytest.raises(ValueError,match='Model'):await manager.submit(spec)
        key=uuid.uuid5(uuid.NAMESPACE_URL,'deepseek-supervisor:invalid-model').hex
        assert manager.status(key)['phase']=='model_configuration'
        assert not (manager.directory(key)/'workspace').exists()
    asyncio.run(exercise())
