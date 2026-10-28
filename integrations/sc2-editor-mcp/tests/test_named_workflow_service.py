import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot


def test_named_workflow_is_readonly_and_binds_selected_source(tmp_path, monkeypatch):
    import sc2_mcp.secret_hangar_audit as module
    root = tmp_path / 'readonly.SC2Map'
    root.mkdir()
    (root / 'DocumentInfo').write_bytes(b'<DocInfo/>')
    service = Service(tmp_path / 'state')
    before = snapshot(root)
    try:
        project = service.projects.open(str(root), False)
        selected = service.prepare_dependencies(project['project_id'])
        def audit(source, *, source_context):
            assert source == root
            assert source_context['source_context_id'] == selected['source_context_id']
            return {'validation':'static', 'overall':'unknown', 'source_context_complete':False}
        monkeypatch.setattr(module, 'audit_secret_hangar', audit)
        result = service.audit_named_unit_workflow(project['project_id'], 'secret_hangar', selected['source_context_id'])
        assert result['project_id'] == project['project_id']
        assert result['source_context_id'] == selected['source_context_id']
        assert result['validation'] == 'static' and result['overall'] == 'unknown'
        assert snapshot(root) == before
    finally:
        service.jobs.shutdown()


@pytest.mark.parametrize('workflow', ['', 'custom_code', 'other'])
def test_unknown_named_workflow_rejected_before_map_or_source_access(workflow):
    service = Service.__new__(Service)
    with pytest.raises(SC2Error) as error:
        service.audit_named_unit_workflow('nonexistent', workflow)
    assert error.value.code == 'unsupported_named_workflow'
