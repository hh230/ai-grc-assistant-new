"""Platform router — the Tool / Agent / Plugin registries (CLAUDE.md §10, §17, ADR-0006, 0010).

These are the extensibility catalogs: capabilities grow by *registering* here, not by editing the
core. The registries are global (not tenant-scoped); registration is a platform-admin operation.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.platform.enums import AgentType, ToolSideEffect
from grc_domain.shared.identifiers import AgentId, PluginId, ToolId
from grc_services.agents import commands as agents_c
from grc_services.agents import queries as agents_q
from grc_services.plugins import commands as plugins_c
from grc_services.plugins import queries as plugins_q
from grc_services.tools import commands as tools_c
from grc_services.tools import queries as tools_q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(tags=["platform"])


# ---------------- Tools ----------------
class ToolResponse(ApiModel):
    id: str
    name: str
    version: str
    side_effect: str
    status: str
    requires_approval: bool


class RegisterToolRequest(ApiModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    side_effect: ToolSideEffect
    required_permissions: list[str] = Field(default_factory=list)


@router.post(
    "/tools",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a tool",
    responses=problem_responses(403, 422),
)
async def register_tool(body: RegisterToolRequest, commands: Commands, context: Context) -> object:
    command = tools_c.RegisterTool(
        name=body.name,
        version=body.version,
        description=body.description,
        side_effect=body.side_effect,
        required_permissions=tuple(body.required_permissions),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "/tools",
    response_model=list[ToolResponse],
    summary="List active tools",
    responses=problem_responses(403),
)
async def list_tools(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(tools_q.ListActiveTools(), context))


@router.get(
    "/tools/{tool_id}",
    response_model=ToolResponse,
    summary="Get a tool",
    responses=problem_responses(403, 404),
)
async def get_tool(tool_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(tools_q.GetTool(tool_id=ToolId(tool_id)), context))


@router.post(
    "/tools/{tool_id}/deprecate",
    response_model=ToolResponse,
    summary="Deprecate a tool",
    responses=problem_responses(403, 404, 409),
)
async def deprecate_tool(tool_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(tools_c.DeprecateTool(tool_id=ToolId(tool_id)), context))


# ---------------- Agents ----------------
class AgentResponse(ApiModel):
    id: str
    name: str
    agent_type: str
    status: str
    allowed_tool_ids: list[str]
    data_scopes: list[str]


class RegisterAgentRequest(ApiModel):
    name: str = Field(min_length=1)
    agent_type: AgentType
    allowed_tool_ids: list[str] = Field(default_factory=list)
    data_scopes: list[str] = Field(default_factory=list)


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an agent",
    responses=problem_responses(403, 422),
)
async def register_agent(
    body: RegisterAgentRequest, commands: Commands, context: Context
) -> object:
    command = agents_c.RegisterAgent(
        name=body.name,
        agent_type=body.agent_type,
        allowed_tool_ids=tuple(ToolId(tool_id) for tool_id in body.allowed_tool_ids),
        data_scopes=tuple(body.data_scopes),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "/agents",
    response_model=list[AgentResponse],
    summary="List active agents",
    responses=problem_responses(403),
)
async def list_agents(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(agents_q.ListActiveAgents(), context))


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Get an agent",
    responses=problem_responses(403, 404),
)
async def get_agent(agent_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(agents_q.GetAgent(agent_id=AgentId(agent_id)), context))


# ---------------- Plugins ----------------
class PluginResponse(ApiModel):
    id: str
    name: str
    version: str
    status: str
    provided_tool_ids: list[str]
    provided_agent_ids: list[str]


class InstallPluginRequest(ApiModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provided_tool_ids: list[str] = Field(default_factory=list)
    provided_agent_ids: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)


@router.post(
    "/plugins",
    response_model=PluginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Install a plugin",
    responses=problem_responses(403, 422),
)
async def install_plugin(
    body: InstallPluginRequest, commands: Commands, context: Context
) -> object:
    command = plugins_c.InstallPlugin(
        name=body.name,
        version=body.version,
        provided_tool_ids=tuple(ToolId(tool_id) for tool_id in body.provided_tool_ids),
        provided_agent_ids=tuple(AgentId(agent_id) for agent_id in body.provided_agent_ids),
        required_permissions=tuple(body.required_permissions),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "/plugins",
    response_model=list[PluginResponse],
    summary="List installed plugins",
    responses=problem_responses(403),
)
async def list_plugins(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(plugins_q.ListPlugins(), context))


@router.get(
    "/plugins/{plugin_id}",
    response_model=PluginResponse,
    summary="Get a plugin",
    responses=problem_responses(403, 404),
)
async def get_plugin(plugin_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(plugins_q.GetPlugin(plugin_id=PluginId(plugin_id)), context))


@router.post(
    "/plugins/{plugin_id}/enable",
    response_model=PluginResponse,
    summary="Enable a plugin",
    responses=problem_responses(403, 404, 409),
)
async def enable_plugin(plugin_id: str, commands: Commands, context: Context) -> object:
    return unwrap(
        await commands.dispatch(plugins_c.EnablePlugin(plugin_id=PluginId(plugin_id)), context)
    )


@router.post(
    "/plugins/{plugin_id}/disable",
    response_model=PluginResponse,
    summary="Disable a plugin",
    responses=problem_responses(403, 404, 409),
)
async def disable_plugin(plugin_id: str, commands: Commands, context: Context) -> object:
    return unwrap(
        await commands.dispatch(plugins_c.DisablePlugin(plugin_id=PluginId(plugin_id)), context)
    )
