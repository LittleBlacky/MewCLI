"""Graph builder - LangGraph integration."""

from __future__ import annotations

from typing import Any, Callable, Literal, Type, Union

from langgraph.graph import StateGraph, END


class GraphBuilder:
    """Builder for creating LangGraph state graphs."""

    def __init__(self, state_schema: Type):
        self.schema = state_schema
        self._graph = StateGraph(state_schema)
        self._nodes: dict[str, Callable] = {}
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: dict[str, tuple[Callable, list[str]]] = {}

    def add_node(self, name: str, fn: Callable) -> "GraphBuilder":
        """Add a node to the graph."""
        self._nodes[name] = fn
        self._graph.add_node(name, fn)
        return self

    def add_edge(self, from_node: str, to_node: str) -> "GraphBuilder":
        """Add a directed edge."""
        self._edges.append((from_node, to_node))
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        condition: Callable,
        mapping: dict[str, str],
    ) -> "GraphBuilder":
        self._conditional_edges[from_node] = (condition, list(mapping.keys()))
        return self

    def set_entry_point(self, node: str) -> "GraphBuilder":
        """Set entry point."""
        self._graph.set_entry_point(node)
        return self

    def set_finish_point(self, node: Union[str, type[END]] = END) -> "GraphBuilder":
        """Set finish point."""
        if node == END:
            self._graph.set_finish_point(END)
        else:
            self._graph.add_edge(node, END)
        return self

    def compile(self) -> Any:
        """Compile the graph."""
        # Add regular edges
        for from_node, to_node in self._edges:
            self._graph.add_edge(from_node, to_node)

        # Add conditional edges
        for from_node, (condition, path_mapping) in self._conditional_edges.items():
            self._graph.add_conditional_edges(
                from_node,
                condition,
                path_mapping,
            )

        return self._graph.compile()
