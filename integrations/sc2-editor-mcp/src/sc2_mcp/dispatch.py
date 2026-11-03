"""One typed operation boundary and state router for both CLI and MCP."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import threading
from typing import get_type_hints
import uuid

from pydantic import ConfigDict, ValidationError, create_model
from .agent_bridge import project_runtime, process_lock
from .errors import SC2Error
from .operations import create_operations
from . import reports
from .service import Service
from .storage import write_json


class Dispatcher:
    def __init__(self, state: Path, *, project_states=False):
        self.state = Path(state).resolve()
        self.service = Service(self.state)
        self.project_states = project_states
        self.services = {str(self.state): self.service}
        self.operations = create_operations(self.service)
        self.schemas = {}
        self.lock = threading.RLock()
        for name, (fn, _) in self.operations.items():
            hints = get_type_hints(fn)
            fields = {key: (hints.get(key, object), ... if p.default is inspect.Parameter.empty else p.default)
                      for key, p in inspect.signature(fn).parameters.items()}
            self.schemas[name] = create_model(name, __config__=ConfigDict(extra='forbid'), **fields)

    def _index(self):
        path = self.state / 'routing.json'
        return json.loads(path.read_text('utf-8')) if path.exists() else {}

    def _service(self, state):
        state = str(Path(state).resolve())
        with self.lock:
            if state not in self.services:
                self.services[state] = Service(Path(state))
            return self.services[state]

    def _select(self, name, arguments):
        if not self.project_states:
            return self.service
        if name == 'sc2_project_open':
            return self._service(project_runtime(arguments['path']) / 'sc2')
        with process_lock(self.state / 'routing.lock', timeout=2):
            index = self._index()
        for key in ('project_id', 'job_id', 'probe_id', 'source_context_id', 'change_id'):
            if arguments.get(key):
                state = index.get(key + ':' + arguments[key])
                if state:
                    return self._service(state)
        if name == 'sc2_report_read' and 'report:' + arguments['name'] in index:
            return self._service(index['report:' + arguments['name']])
        if name == 'sc2_artifact_image':
            requested = Path(arguments['path']).resolve()
            for state in set(index.values()):
                if requested.is_relative_to(Path(state)):
                    return self._service(state)
        return self.service

    def _remember(self, result, service):
        if not self.project_states:
            return
        additions = {}
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'project_id':
                        # Only a registered project in this store owns its route.
                        if isinstance(item, str) and item in owned_projects:
                            additions[key + ':' + item] = str(service.state)
                    elif key in {'job_id', 'probe_id', 'source_context_id', 'change_id'} and isinstance(item, str):
                        additions[key + ':' + item] = str(service.state)
                    elif key == 'report_name':
                        additions['report:' + item] = str(service.state)
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        owned_projects = {record['project_id'] for record in service.projects.list()}
        walk(result)
        if additions:
            with process_lock(self.state / 'routing.lock', timeout=2):
                index = self._index()
                index.update(additions)
                write_json(self.state / 'routing.json', index)

    def call(self, name, arguments=None):
        if name not in self.operations:
            raise SC2Error('unsupported_operation', 'Operation is not exposed by this workspace', operation=name)
        try:
            arguments = self.schemas[name].model_validate(arguments or {}).model_dump()
            service = self._select(name, arguments)
            if name == 'sc2_project_clone' and self.project_states:
                owner = service
                service = self._service(project_runtime(arguments['destination']) / 'sc2')
                result = owner.projects.clone(arguments['project_id'],arguments['destination'],service.projects)
            elif name == 'sc2_project_create' and self.project_states:
                with process_lock(self.state / 'routing.lock', timeout=2):
                    states = set(self._index().values())
                matches = [(self._service(state),rec) for state in sorted(states) for rec,_ in
                           self._service(state).find_templates(arguments['template'],arguments['template_project_id'])]
                if len(matches)!=1:
                    raise SC2Error('template_ambiguous' if matches else 'template_not_found','请选择已注册模板的来源项目',
                                   candidates=[{'project_id':r['project_id'],'path':r['root']} for _,r in matches])
                owner,record = matches[0]
                service = self._service(project_runtime(arguments['destination']) / 'sc2')
                result = owner.create_from_template(arguments['template'],arguments['destination'],record['project_id'],service.projects)
            elif name == 'sc2_project_list' and self.project_states:
                with process_lock(self.state / 'routing.lock', timeout=2):
                    states = set(self._index().values())
                result = {'projects': [p for state in sorted(states) for p in self._service(state).projects.list()]}
            else:
                result = create_operations(service)[name][0](**arguments)
            if name == 'sc2_report_read':
                return {'ok': True, 'result': result}
            if reports.size({'ok': True, 'result': result}) > reports.LIMIT:
                report = uuid.uuid4().hex + '.json'
                path = service.state / 'reports' / report
                characters = reports.write_report(path, result)
                if name != 'sc2_project_list':
                    self._remember(result, service)
                result = {'summary': reports.summary(result), 'report_file': str(path),
                          'report_name': report, 'characters': characters}
            if name != 'sc2_project_list' or 'report_name' in result:
                self._remember(result, service)
            return {'ok': True, 'result': result}
        except SC2Error:
            raise
        except (ValidationError, ValueError, KeyError, TypeError, OSError) as exc:
            raise SC2Error('invalid_request', str(exc)) from exc

    def close(self):
        for service in self.services.values():
            service.jobs.shutdown(cancel_pending=True)

    def error_payload(self, error):
        if reports.size({'ok': False, 'error': error}) <= reports.LIMIT:
            return error
        name = uuid.uuid4().hex + '.json'
        path = self.service.state / 'reports' / name
        characters = reports.write_report(path, error)
        return {**reports.short_error(error), 'report_name': name, 'characters': characters}
