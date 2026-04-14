"""Main agent implementation using LangGraph."""
from typing import Literal

from langgraph.graph import StateGraph, END

from minicode.agent.state import AgentState
from minicode.services.model_provider import create_provider
from minicode.tools.registry import ALL_TOOLS


def create_agent_graph(
    model_provider: str = "anthropic",
    model_name: str = "claude-sonnet-4-7",
):
    """Create the main agent graph."""

    provider = create_provider(provider=model_provider, model=model_name)

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        """Determine if agent should continue or end."""
        messages = state.get("messages", [])
        if not messages:
            return "__end__"
        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"
        return "__end__"

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", lambda state: {"messages": []})
    workflow.add_node("tools", lambda state: {"messages": []})

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")
    workflow.add_edge("agent", END)

    return workflow.compile()
