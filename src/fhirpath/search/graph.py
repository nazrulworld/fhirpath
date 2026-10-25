# _*_ coding: utf-8 _*_
"""``_graph`` (FHIR R5 search, trial use): include the resources a
``GraphDefinition`` describes, starting from the matches of a search page.

Both shapes of GraphDefinition are understood: R4/R4B (``link.path`` /
``link.target.type`` / ``target.params`` / nested ``target.link``) and R5
(``node`` + ``link.sourceId`` / ``targetId``). A link with a ``path`` follows the
references the FHIRPath ``path`` selects; a link with ``params`` searches the
target type with them, ``{ref}`` standing for the source resource
(``patient={ref}``).
"""
from typing import Any, Dict, List, NamedTuple, Optional

from fhirpath.core import compile as fhirpath_compile
from fhirpath.search.engine.base import (
    parse_literal_reference,
    resolve_literal_reference,
)
from fhirpath.search.exceptions import ValidationError

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

# GraphDefinitions known by url or id (``register_graph_definition``); others
# are looked up with a search
GRAPH_DEFINITIONS: Dict[str, Dict[str, Any]] = {}
GRAPH_MAX_DEPTH = 10


class GraphLink(NamedTuple):
    path: Optional[str]
    target_type: Optional[str]
    params: Optional[str]
    links: List["GraphLink"]


def register_graph_definition(resource: Dict[str, Any]):
    """Make a GraphDefinition available to ``_graph`` by url and id."""
    if resource.get("url"):
        GRAPH_DEFINITIONS[resource["url"]] = resource
    if resource.get("id"):
        GRAPH_DEFINITIONS[f"GraphDefinition/{resource['id']}"] = resource
        GRAPH_DEFINITIONS[resource["id"]] = resource


def graph_links(graph: Dict[str, Any]) -> List[GraphLink]:
    """The links of the start node, as a tree."""
    if "node" in graph or any("sourceId" in link for link in graph.get("link", [])):
        return _r5_links(graph)
    return [_r4_link(link) for link in graph.get("link", [])]


def _r4_link(link) -> GraphLink:
    targets = link.get("target") or [{}]
    # one GraphLink per target type
    if len(targets) > 1:
        return GraphLink(
            None,
            None,
            None,
            [_r4_link({**link, "target": [target]}) for target in targets],
        )
    target = targets[0]
    return GraphLink(
        link.get("path"),
        target.get("type"),
        target.get("params"),
        [_r4_link(child) for child in target.get("link", [])],
    )


def _r5_links(graph) -> List[GraphLink]:
    nodes = {node.get("nodeId"): node for node in graph.get("node", [])}

    def links_from(node_id, depth=0) -> List[GraphLink]:
        if depth > GRAPH_MAX_DEPTH:
            return []
        result = []
        for link in graph.get("link", []):
            if link.get("sourceId") != node_id:
                continue
            target = nodes.get(link.get("targetId"), {})
            result.append(
                GraphLink(
                    link.get("path"),
                    target.get("type"),
                    link.get("params"),
                    links_from(link.get("targetId"), depth + 1),
                )
            )
        return result

    return links_from(graph.get("start"))


def start_type(graph: Dict[str, Any]) -> Optional[str]:
    start = graph.get("start")
    nodes = {node.get("nodeId"): node for node in graph.get("node", [])}
    if start in nodes:
        return nodes[start].get("type")
    return start


def lookup_graph(search, value: str):
    """The GraphDefinition named by ``_graph`` (generator: may search for it)."""
    if value in GRAPH_DEFINITIONS:
        return GRAPH_DEFINITIONS[value]
    from fhirpath.search.search import SearchContext

    context = SearchContext(search.context.engine, "GraphDefinition")
    name = "url" if "/" in value and "://" in value else "_id"
    raw = value.split("/")[-1] if name == "_id" else value
    terms: List = []
    try:
        search.add_term(context.normalize_param(name, [raw]), terms)
    except (ValidationError, NotImplementedError, KeyError, AttributeError):
        terms = []
    if terms:
        from fhirpath.search.query import Q_

        result = yield Q_("GraphDefinition", search.context.engine).where(*terms)(
            unrestricted=search.context.unrestricted
        )
        for row in result.body:
            return row[0]
    raise ValidationError(f"Unknown GraphDefinition ``{value}`` (_graph).")


def resolve_graph(search, rows, seen):
    """Rows of the resources the ``_graph`` of ``search`` adds to ``rows``
    (generator yielding the sub-queries)."""
    graph = yield from lookup_graph(search, search.result_params["_graph"])
    start = start_type(graph)
    sources = [row for row in rows if _row_type(row) == start]
    added: List = []
    yield from _follow(search, graph_links(graph), sources, seen, added, 0)
    return added


def _row_type(row):
    resource = row[0]
    if isinstance(resource, dict):
        return resource.get("resourceType")
    return resource.get_resource_type()


def _follow(search, links, sources, seen, added, depth):
    if depth > GRAPH_MAX_DEPTH or not sources:
        return
    for link in links:
        if link.path is None and link.params is None:
            # several targets: one link each
            yield from _follow(search, link.links, sources, seen, added, depth)
            continue
        found = yield from _link_rows(search, link, sources)
        new_rows = []
        for row in found:
            key = (_row_type(row), row[0].get("id"))
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(row)
        added.extend(new_rows)
        # nested links start from everything the link reached
        yield from _follow(search, link.links, found, seen, added, depth + 1)


def _link_rows(search, link, sources):
    from fhirpath.search.query import Q_
    from fhirpath.search.search import Search, SearchContext

    engine = search.context.engine
    if link.path:
        expression = fhirpath_compile(link.path)
        references: Dict[str, List[str]] = {}
        for row in sources:
            for value in expression.evaluate(row[0], resolver=resolve_literal_reference):
                parsed = parse_literal_reference(value)
                if parsed is None:
                    continue
                if link.target_type and parsed[0] != link.target_type:
                    continue
                references.setdefault(parsed[0], [])
                if parsed[1] not in references[parsed[0]]:
                    references[parsed[0]].append(parsed[1])
        rows: List = []
        for resource_type, ids in sorted(references.items()):
            context = SearchContext(engine, resource_type)
            terms: List = []
            search.add_term(context.normalize_param("_id", [",".join(ids)]), terms)
            result = yield Q_(resource_type, engine).where(*terms)(
                unrestricted=search.context.unrestricted
            )
            rows.extend(result.body)
        return rows

    # params: a search on the target type per source resource
    rows = []
    for row in sources:
        reference = f"{_row_type(row)}/{row[0].get('id')}"
        query_string = link.params.replace("{ref}", reference)
        context = SearchContext(engine, link.target_type)
        terms = []
        for name, value in Search.parse_query_string(query_string).items():
            search.add_term(context.normalize_param(name, [value]), terms)
        result = yield Q_(link.target_type, engine).where(*terms)(
            unrestricted=search.context.unrestricted
        )
        rows.extend(result.body)
    return rows
