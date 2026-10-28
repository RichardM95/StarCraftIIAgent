"""Six MCP tools; task submission returns immediately while the owned worker runs."""
from contextlib import asynccontextmanager
import json
from mcp.server.fastmcp import FastMCP
from .runtime import ROOT
from .manager import TaskSpec
from .router import TaskRouter
from .configuration import capabilities as read_capabilities

manager = TaskRouter()


@asynccontextmanager
async def lifespan(server):
    try:
        yield {}
    finally:
        await manager.close()


mcp = FastMCP("deepseek-supervisor", lifespan=lifespan, log_level="WARNING",
    instructions="Delegate bounded sub-tasks within authorized SC2 work. Other domains need an explicit user request. Workers edit isolated candidates; the primary agent reviews actual diffs and validates before integrating. Do not repeat uncertain submissions; query their request/task IDs first.")


@mcp.tool()
async def submit_task(task: TaskSpec | None = None, continue_task_id: str | None = None,
                      followup: str | None = None) -> dict:
    """Submit task, or explicitly continue a finished task by ID and followup with unchanged scope. Never blindly retry an uncertain submission."""
    if task is not None and continue_task_id is None and followup is None:
        return await manager.submit(task)
    if task is None and continue_task_id and followup:
        return await manager.continue_task(continue_task_id, followup)
    raise ValueError("Provide task OR both continue_task_id and followup")


@mcp.tool()
def task_status(task_id: str) -> dict:
    """Read worker state; worker_completed is not independent acceptance."""
    return manager.status(task_id)


@mcp.tool()
def task_result(task_id: str) -> dict:
    """Get final text, actual candidate changes, source conflicts, and full-log location."""
    return manager.result(task_id)


@mcp.tool()
async def cancel_task(task_id: str) -> dict:
    """Stop this task and reap its owned runtime process tree without stopping other tasks."""
    return await manager.cancel(task_id)


@mcp.tool()
def list_tasks(limit: int = 20) -> list[dict]:
    """List recent local tasks, including completed records from earlier connections."""
    return manager.list_tasks(max(1, min(limit, 100)))


@mcp.tool()
def capabilities() -> dict:
    """Read capability evidence; historical evaluations are not acceptance of this installation."""
    return read_capabilities()


@mcp.tool()
def integrate_task(task_id: str, review_note: str) -> dict:
    """Integrate independently reviewed allowed files; source conflicts and generated Galaxy are refused."""
    return manager.integrate(task_id, review_note)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
