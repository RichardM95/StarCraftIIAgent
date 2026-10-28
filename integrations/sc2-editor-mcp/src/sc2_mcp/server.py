"""Thin MCP adapter over the shared operation dispatcher."""
from __future__ import annotations
import functools
import json
from pathlib import Path
import anyio
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from . import __version__
from .dispatch import Dispatcher
from .errors import SC2Error


def create_server(state: Path, *, project_states=False):
    dispatcher = Dispatcher(state, project_states=project_states)
    mcp = FastMCP('sc2-editor', log_level='WARNING', instructions=(
        'SC2 development tools. Read sc2_capabilities, then open an explicit project. '
        'Workspace AGENTS and skills define source boundaries and tool routing. '
        'Generated Galaxy stays read-only. Terrain evidence remains scoped.'))
    mcp._mcp_server.version = __version__
    mcp.sc2_service = dispatcher.service
    mcp.sc2_dispatcher = dispatcher
    for name, (fn, readonly) in dispatcher.operations.items():
        def adapt(operation, original):
            @functools.wraps(original)
            async def invoke(**kwargs):
                try:
                    result = await anyio.to_thread.run_sync(
                        functools.partial(dispatcher.call, operation, kwargs))
                    if operation == 'sc2_artifact_image':
                        return Image(path=result['result']['path'], format='png')
                    return result
                except SC2Error as exc:
                    raise ToolError(json.dumps(exc.as_dict(), ensure_ascii=False)) from exc
            return invoke
        mcp.tool(name=name, annotations=ToolAnnotations(
            readOnlyHint=readonly, destructiveHint=not readonly,
            idempotentHint=readonly, openWorldHint=False))(adapt(name, fn))
    return mcp
