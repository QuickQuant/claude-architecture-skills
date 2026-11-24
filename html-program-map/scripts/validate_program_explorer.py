#!/usr/bin/env python3
"""Exercise the workflow-driven program explorer through Chrome DevTools."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import time
import urllib.request

import websocket


class CDP:
    def __init__(self, url: str) -> None:
        self.socket = websocket.create_connection(url, timeout=5, suppress_origin=True)
        self.sequence = 0
        self.events: list[dict] = []

    def call(self, method: str, params: dict | None = None) -> dict:
        self.sequence += 1
        request_id = self.sequence
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            self.events.append(message)

    def evaluate(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        remote = result.get("result", {})
        if remote.get("subtype") == "error" or "exceptionDetails" in result:
            raise RuntimeError(remote.get("description", "browser evaluation failed"))
        return remote.get("value")


def page_socket(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
        targets = json.load(response)
    page = next((target for target in targets if target.get("type") == "page"), None)
    check(page is not None, "Chrome DevTools has no page target")
    return page["webSocketDebuggerUrl"]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def settle() -> None:
    time.sleep(0.18)


def resolved_targets(symbol: dict, records: dict) -> list[tuple[str, str]]:
    """Unique resolved destinations, rejecting dangling static references."""
    targets = []
    for call in symbol["calls"]:
        for target in call.get("resolved", []):
            key = (target["kind"], target["id"])
            check(key in records, f"{symbol['id']} invokes missing {key}")
            if key not in targets:
                targets.append(key)
    return targets


def select_search_symbol(data: dict) -> dict | None:
    """Choose a deterministic callable exposed by the template's bounded search.

    Mirror renderSearch's group order, label/file/summary matching and inner-loop
    break at 35 results. In particular, once full, a later group still examines
    its first item. Do not turn a broken rendered search into a passing SKIP.
    """
    symbols = data["symbols"]
    counts = Counter(symbol["name"].lower() for symbol in symbols)
    candidates = sorted(
        (symbol for symbol in symbols if len(symbol["name"].strip()) >= 2),
        key=lambda symbol: (counts[symbol["name"].lower()] != 1, -len(symbol["name"]),
                            symbol["name"], symbol["file"], symbol["id"]),
    )
    groups = (
        ("subsystem", data["model"]["subsystems"]),
        ("component", data["model"]["components"]),
        ("class", data["classes"]), ("symbol", symbols), ("module", data["modules"]),
    )
    for candidate in candidates:
        query = candidate["name"].strip().lower()
        results = []
        for kind, rows in groups:
            for record in rows:
                label = (record["file"] if kind == "module" else
                         record.get("name") or record.get("qualified_name") or record["id"])
                haystack = f"{label} {record.get('file') or ''} {record.get('summary') or ''}".lower()
                if query in haystack:
                    results.append((kind, record))
                if len(results) >= 35:
                    break
        first_match = next((record for kind, record in results
                            if kind == "symbol" and record["name"] == candidate["name"]
                            and record["file"] == candidate["file"]), None)
        if first_match is not None and first_match["id"] == candidate["id"]:
            return candidate
    return None


def exercise(cdp: CDP, result: dict, full_deep_links: bool = False) -> None:
    data = cdp.evaluate(
        "(()=>{const node=document.querySelector('#explorer-data');"
        "return node?JSON.parse(node.textContent):null})()"
    )
    check(isinstance(data, dict), "page lacks #explorer-data; expected a rendered program explorer")
    model = data["model"]
    records = {
        (kind, record["id"]): record
        for kind, rows in (
            ("system", model["systems"]), ("subsystem", model["subsystems"]),
            ("component", model["components"]), ("class", data["classes"]),
            ("symbol", data["symbols"]), ("module", data["modules"]),
            ("edge", model["system_edges"] + model["subsystem_edges"] + model["component_edges"]),
        )
        for record in rows
    }
    workflows = model.get("workflows", [])
    workflow = workflows[0] if workflows else None

    def skip(reason: str) -> None:
        result["skips"].append(reason)
        print(f"SKIP {reason}")

    def label(kind: str, record: dict, inspector: bool = False) -> str:
        if kind == "module":
            return record["file"]
        if kind == "edge":
            return record["label"]
        if inspector and kind in {"class", "symbol"}:
            return record["qualified_name"]
        return record.get("name") or record.get("qualified_name") or record["id"]

    def selected(kind: str, record: dict) -> bool:
        actual = cdp.evaluate(
            "({focus:document.querySelector('#focus-panel h2')?.textContent,"
            "title:document.querySelector('#inspector h2')?.textContent,"
            "source:document.querySelector('#inspector .source')?.textContent||''})"
        )
        return (actual["focus"] == label(kind, record)
                and actual["title"] == label(kind, record, inspector=True)
                and (kind not in {"class", "symbol", "module"}
                     or record["file"] in actual["source"] or kind == "module"))

    def navigate(kind: str, record: dict, *, current: dict | None = None, step: int = 0) -> None:
        current = current or workflow
        params = {"mode": "architecture", "type": kind, "id": record["id"]}
        if current:
            params.update(workflow=current["id"], step=str(step))
        cdp.evaluate(f"location.hash=new URLSearchParams({json.dumps(params)}).toString()")
        settle()

    def click(selector: str) -> None:
        found = cdp.evaluate(
            f"(()=>{{const x=document.querySelector({json.dumps(selector)});"
            "if(!x)return false;x.click();return true})()"
        )
        check(found, f"missing interaction control: {selector}")
        settle()

    def stats(selector: str) -> dict:
        return cdp.evaluate(
            f"Object.fromEntries([...document.querySelectorAll({json.dumps(selector)})]"
            ".map(x=>[x.querySelector('span')?.textContent,Number(x.querySelector('b')?.textContent)]))"
        )

    # Verify every authored reference before exercising it. Empty collections are
    # legitimate; a nonempty collection with a dangling ID is always a failure.
    plurals = {"systems": "system", "subsystems": "subsystem", "components": "component",
               "classes": "class", "symbols": "symbol"}
    for current in workflows:
        for plural, kind in plurals.items():
            for record_id in current["touched"].get(plural, []):
                check((kind, record_id) in records, f"workflow {current['id']} has missing {kind}: {record_id}")
        for step in current["steps"]:
            check(("symbol", step["symbol"]) in records, f"workflow step {step['id']} has missing callable")
            for plural in ("subsystems", "components"):
                for record_id in step[plural]:
                    check((plurals[plural], record_id) in records, f"workflow step {step['id']} has missing {plural}: {record_id}")
    guide = model.get("guide")
    if guide:
        for section in ("operating_loop", "boundaries", "start_here"):
            for item in guide[section]:
                target = item["target"]
                if target["type"] == "workflow":
                    target_workflow = next((w for w in workflows if w["id"] == target["id"]), None)
                    check(target_workflow is not None, f"guide references missing workflow: {target['id']}")
                    check(0 <= target.get("step", 0) < len(target_workflow["steps"]), "guide workflow step is out of range")
                else:
                    check((target["type"], target["id"]) in records, f"guide target does not resolve: {target}")
    for kind in ("system", "subsystem", "component"):
        for edge in model[f"{kind}_edges"]:
            check((kind, edge["from"]) in records and (kind, edge["to"]) in records,
                  f"{kind} relationship {edge['id']} has a missing endpoint")
    for kind, rows in (("component", model["components"]), ("class", data["classes"]), ("module", data["modules"])):
        for record in rows:
            for plural in ("classes", "symbols", "modules"):
                target_kind = {"classes": "class", "symbols": "symbol", "modules": "module"}[plural]
                for record_id in record.get(plural, []):
                    check((target_kind, record_id) in records, f"{kind} {record['id']} references missing {target_kind}: {record_id}")
    for symbol in data["symbols"]:
        resolved_targets(symbol, records)
        for caller in symbol["called_by"]:
            check(("symbol", caller) in records, f"{symbol['id']} has missing inbound caller: {caller}")
    coverage = data["coverage"]
    for field, expected in (
        ("class_count", len(data["classes"])),
        ("variable_count", sum(len(c["variables"]) for c in data["classes"])),
        ("python_symbol_count", len(data["symbols"])),
        ("call_site_count", sum(s["call_count"] for s in data["symbols"])),
        ("component_count", len(model["components"])),
        ("subsystem_count", len(model["subsystems"])),
    ):
        check(coverage[field] == expected, f"embedded coverage {field} disagrees with map records")

    initial = cdp.evaluate(
        "({title:document.title,mapNodes:document.querySelectorAll('.map-node').length,"
        "mapEdges:document.querySelectorAll('.map-edge').length,step:document.querySelector('#step-count')?.textContent,"
        "guideTitle:document.querySelector('#guide-title')?.textContent,guideSteps:document.querySelectorAll('.loop-step').length,"
        "guideLinks:document.querySelectorAll('.start-link').length,focus:document.querySelector('#focus-panel h2')?.textContent,"
        "workflow:document.querySelector('#workflow-select')?.selectedOptions[0]?.textContent,ready:document.body.dataset.ready})"
    )
    result["initial"] = initial
    check(initial["title"] == model["project"]["title"], "document title drifted")
    check(initial["mapNodes"] == len(model["subsystems"]), "subsystem landscape is incomplete")
    check(initial["mapEdges"] == len(model["subsystem_edges"]), "subsystem relationships are incomplete")
    header_counts = cdp.evaluate("[...document.querySelectorAll('#header-metrics b')].map(x=>Number(x.textContent))")
    check(header_counts == [len(model["subsystems"]), len(model["components"]),
                            sum(s["category"] == "runtime" for s in data["symbols"])], "header counts disagree with map records")
    check(initial["ready"] == "true", "interface never reached ready state")
    check(bool(initial.get("focus")) or not records, "default selection does not resolve to an architecture object")
    if guide:
        check(initial.get("guideTitle") == guide["title"], "cohesive system overview is missing")
        check(initial["guideSteps"] == len(guide["operating_loop"]), "operating loop is incomplete")
        check(initial["guideLinks"] == len(guide["start_here"]), "start-here links are incomplete")
    else:
        skip("map has no authored orientation guide")

    # Check the untouched initial load before any start link or chooser event.
    if workflow and workflow["steps"]:
        check(initial["step"] == f"1 / {len(workflow['steps'])}", "happy path did not initialize")
        check(initial["workflow"] == workflow["name"], "workflow chooser drifted")
        time.sleep(0.55)
        check(cdp.evaluate("document.querySelector('#step-count').textContent") == initial["step"],
              "workflow autoplayed without operator intent")
    else:
        skip("map has no authored workflow steps for initial player checks")

    if guide:
        for index, item in enumerate(guide["start_here"]):
            click(f".start-link:nth-child({index+1})")
            target = item["target"]
            if target["type"] == "workflow":
                current = next(w for w in workflows if w["id"] == target["id"])
                step = current["steps"][target.get("step", 0)]
                check(selected("symbol", records[("symbol", step["symbol"])]), "start-here workflow link missed its callable")
            else:
                check(selected(target["type"], records[(target["type"], target["id"])]), "start-here link missed its target")

    # Drive all workflows through every step with the public player controls.
    cdp.evaluate(
        "(()=>{window.__programMapStepTransitions=0;if(!document.startViewTransition)return;"
        "const original=document.startViewTransition;document.startViewTransition=function(...args){"
        "window.__programMapStepTransitions++;return original.apply(this,args)}})()"
    )
    result["workflows"] = []
    for current in workflows:
        if not current["steps"]:
            skip(f"workflow {current['id']} has no steps")
            continue
        cdp.evaluate(
            "(()=>{const x=document.querySelector('#workflow-select');"
            f"x.value={json.dumps(current['id'])};x.dispatchEvent(new Event('change',{{bubbles:true}}))}})()"
        )
        settle()
        check(cdp.evaluate("document.querySelectorAll('#step-track [data-step]').length") == len(current["steps"]),
              f"step controls disagree with workflow {current['id']}")
        for index, step in enumerate(current["steps"]):
            if index:
                click("#next-step")
            actual = cdp.evaluate(
                "({step:document.querySelector('#step-count').textContent,title:document.querySelector('#inspector h2')?.textContent,"
                "condition:document.querySelector('#step-detail .condition-cell p')?.textContent,"
                "guard:document.querySelector('#step-detail .source-guard')?.textContent,"
                "hot:[...document.querySelectorAll('.map-node.hot')].map(x=>x.dataset.id),"
                "inputs:[...document.querySelectorAll('#step-detail .flow-cell:not(.output-cell) [data-object]')].map(x=>x.textContent),"
                "outputs:[...document.querySelectorAll('#step-detail .output-cell [data-object]')].map(x=>x.textContent),"
                "viewTransitions:window.__programMapStepTransitions})"
            )
            check(actual["step"] == f"{index+1} / {len(current['steps'])}", f"player missed step {step['id']}")
            symbol = records[("symbol", step["symbol"])]
            check(selected("symbol", symbol), f"step {step['id']} did not select its callable")
            check(actual["condition"] == step["condition"], f"step {step['id']} lost its passing condition")
            if step.get("source_guard"):
                check(actual.get("guard") == f"Source guard: {step['source_guard']}", "source guard is missing")
            check(actual["inputs"] == step["input"] and actual["outputs"] == step["output"], "trace inputs/outputs drifted")
            check(set(actual["hot"]) == set(step["subsystems"]), "current workflow footprint is incomplete")
            check(actual["viewTransitions"] == 0, "step navigation invoked a document View Transition")
            if current is workflow and index == 1:
                result["step_two"] = actual
        check(cdp.evaluate("document.querySelector('#next-step').disabled"), "next-step enabled past final step")
        if len(current["steps"]) > 1:
            click("#prev-step")
            previous = current["steps"][-2]
            check(selected("symbol", records[("symbol", previous["symbol"])]), "previous-step control failed")
        result["workflows"].append({"id": current["id"], "steps_checked": len(current["steps"])})
    if not workflows:
        skip("map has no workflows for end-to-end player checks")
    elif workflow and len(workflow["steps"]) < 2:
        skip("first workflow has fewer than two steps; next/previous transition check unavailable")

    # Exercise play/pause on the first workflow that can actually advance.
    playable = next((w for w in workflows if len(w["steps"]) > 1), None)
    if playable:
        navigate("symbol", records[("symbol", playable["steps"][0]["symbol"])], current=playable)
        click("#play-step")
        check(cdp.evaluate("document.querySelector('#play-step').getAttribute('aria-label')") == "Pause workflow", "play did not start")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cdp.evaluate("document.querySelector('#step-count').textContent") != f"1 / {len(playable['steps'])}":
                break
            time.sleep(0.1)
        check(selected("symbol", records[("symbol", playable["steps"][1]["symbol"])]), "play did not advance to the next callable")
        click("#play-step")
        check(cdp.evaluate("document.querySelector('#play-step').getAttribute('aria-label')") == "Play workflow", "pause did not stop playback")
        paused = cdp.evaluate("document.querySelector('#step-count').textContent")
        time.sleep(0.55)
        check(cdp.evaluate("document.querySelector('#step-count').textContent") == paused, "paused player advanced")
    else:
        skip("no multi-step workflow for play/pause advancement")

    # Choose same-level context from actual relationships, never from names.
    result["contexts"] = []
    for kind in ("system", "subsystem", "component"):
        edges = model[f"{kind}_edges"]
        if not edges:
            skip(f"map has no {kind} relationships for contextual navigation")
            continue
        record = records[(kind, edges[0]["from"])]
        navigate(kind, record)
        contextual = cdp.evaluate(
            "({title:document.querySelector('#focus-panel h2')?.textContent,"
            "place:document.querySelector('#focus-panel').textContent.includes('Place in the system'),"
            "flows:document.querySelector('#focus-panel').textContent.includes('Connected flows'),"
            "relations:document.querySelectorAll('#focus-panel .relation-link').length})"
        )
        check(selected(kind, record), f"{kind} selection missed its target")
        check(contextual["place"] and contextual["flows"] and contextual["relations"] > 0,
              f"{kind} context is incomplete: {contextual}")
        counts = stats("#focus-panel .brief-metric")
        check(counts.get("inputs") == sum(e["to"] == record["id"] for e in edges), "inbound relationship count drifted")
        check(counts.get("outputs") == sum(e["from"] == record["id"] for e in edges), "outbound relationship count drifted")
        plural = {"system": "systems", "subsystem": "subsystems", "component": "components"}[kind]
        check(counts.get("workflows") == sum(record["id"] in w["touched"].get(plural, []) for w in workflows), "workflow participation count drifted")
        if kind == "subsystem":
            check(counts.get("inside") == sum(c["subsystem"] == record["id"] for c in model["components"]), "subsystem composition count drifted")
        result["contexts"].append({"level": kind, **contextual, "counts": counts})
        if kind == "component":
            result["contextual"] = contextual
        edge_id = cdp.evaluate("document.querySelector('#focus-panel .relation-link').dataset.id")
        click("#focus-panel .relation-link")
        check(selected("edge", records[("edge", edge_id)]), "relationship control did not open its record")
        check(cdp.evaluate("document.querySelector('#inspector').textContent.includes('Guarantees')"), "relationship contract is missing")

    if model["subsystem_edges"]:
        edge_id = cdp.evaluate("document.querySelector('.map-edge').dataset.edge")
        cdp.evaluate("document.querySelector('.map-edge').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
        settle()
        check(selected("edge", records[("edge", edge_id)]), "map arrow did not open its relationship")
    else:
        skip("map has no subsystem arrow to click")

    def inspection_score(symbol: dict) -> tuple:
        inputs = [p for p in symbol["parameters"] if p["name"] not in {"self", "cls"}]
        return (any(p.get("uses") and p.get("annotation") for p in inputs),
                bool(symbol["conditions"]), len(inputs))

    candidates = [s for s in data["symbols"] if s["called_by"] and resolved_targets(s, records)]
    rich = max(candidates, key=inspection_score, default=None)
    if rich is None:
        skip("no callable has both inbound callers and resolved outgoing targets")
    symbol = rich or max(data["symbols"], key=inspection_score, default=None)
    if symbol:
        navigate("symbol", symbol)
        inputs = [p for p in symbol["parameters"] if p["name"] not in {"self", "cls"}]
        targets = resolved_targets(symbol, records)
        view = cdp.evaluate(
            "({title:document.querySelector('#focus-panel h2')?.textContent,"
            "inputs:document.querySelectorAll('#focus-panel .input-row').length,"
            "invokes:document.querySelectorAll('#focus-panel .invoke-row').length,"
            "guards:document.querySelectorAll('#inspector .condition').length,"
            "falseComposition:document.querySelector('#focus-panel .composition-head')!==null,"
            "bindingNote:document.querySelector('#focus-panel .callable-intro p')?.textContent})"
        )
        result["callable_view"] = view
        result["emit"] = {"id": symbol["id"], "title": symbol["qualified_name"], "resolved_targets": len(targets)}
        check(selected("symbol", symbol), "callable selection missed its target")
        check(view["inputs"] == len(inputs) and view["invokes"] == len(targets), f"callable relationship counts drifted: {view}")
        check(not view["falseComposition"], "callable renders false composition language")
        check("does not imply" in (view.get("bindingNote") or ""), "parameter ownership boundary is missing")
        counts = stats("#focus-panel .callable-fact")
        for field, caption in (("call_count", "outgoing call expressions"), ("called_by_count", "inbound callers"),
                               ("condition_count", "branches"), ("mutation_count", "visible assignments")):
            check(counts.get(caption) == symbol[field], f"callable {caption} count drifted")
        check(view["guards"] == len(symbol["conditions"]) + len(symbol["returns"]), "guards or return paths were hidden")
        if not symbol["conditions"]:
            skip("selected callable has no guards/branches to inspect")
        if targets:
            kind, target_id = targets[0]
            click("#focus-panel .invoke-row")
            target = records[(kind, target_id)]
            check(selected(kind, target), "outgoing target drill-down failed")
            result["factory"] = {"id": target_id, "title": label(kind, target, inspector=True)}
            navigate("symbol", symbol)
        else:
            skip("selected callable has no resolved target to drill into")
        if inputs:
            parameter = next((p for p in inputs if p.get("uses") and p.get("annotation")), inputs[0])
            signature = cdp.evaluate("document.querySelector('#inspector .source')?.firstChild?.textContent||''")
            check(parameter["name"] in signature, "callable signature omitted its parameter name")
            selector = cdp.evaluate(
                "(()=>{const rows=[...document.querySelectorAll('#focus-panel .input-row')];"
                f"return rows.findIndex(x=>x.querySelector('strong')?.textContent==={json.dumps(parameter['name'])})}})()"
            )
            check(selector >= 0, "input binding is not reachable")
            inline = cdp.evaluate(
                f"document.querySelectorAll('#focus-panel .input-row')[{selector}].textContent"
            )
            if parameter.get("annotation"):
                check(parameter["annotation"] in inline, "inline input annotation was hidden")
            if parameter.get("uses"):
                check(parameter["uses"][0]["expression"] in inline, "inline first observed input use was hidden")
            click(f"#focus-panel .input-row:nth-child({selector+1})")
            binding = cdp.evaluate(
                "({title:document.querySelector('#inspector h2')?.textContent,"
                "text:document.querySelector('#inspector').textContent,"
                "uses:[...document.querySelectorAll('#inspector .data-row code')].map(x=>x.textContent)})"
            )
            check(binding["title"] == parameter["name"], "input binding selection drifted")
            check("does not imply" in binding["text"], "input binding implies retained ownership")
            if parameter.get("annotation"):
                check(parameter["annotation"] in binding["text"], "parameter type was hidden")
            else:
                skip("selected input has no declared type")
            uses = parameter.get("uses", [])
            if uses:
                check(binding["uses"] == [u["expression"] for u in uses[:16]], "observed input uses were hidden")
            else:
                skip("selected input has no statically recovered body uses")
            result["binding"] = {"title": binding["title"], "type": parameter.get("annotation"), "uses": len(binding["uses"])}
        else:
            skip("selected callable has no inputs beyond its receiver")
    else:
        skip("map has no callables to inspect")

    cls = next((c for c in data["classes"] if c["symbols"] and c["variables"]), None)
    if cls:
        navigate("class", cls)
        counts = stats("#inspector .stat")
        check(selected("class", cls), "class selection missed its target")
        check(counts.get("methods") == len(cls["symbols"]) and counts.get("fields") == len(cls["variables"]), "class methods/fields count drifted")
        result["entry"] = {"title": cls["qualified_name"], **counts}
        if cls["symbols"]:
            click("#inspector .call-button")
            check(selected("symbol", records[("symbol", cls["symbols"][0])]), "class method drill-down failed")
    else:
        skip("map has no class with both methods and fields")
    occurrence = next(((w, i, c) for w in workflows for i, step in enumerate(w["steps"])
                       for c in data["classes"] if c["name"] in step["input"] + step["output"]), None)
    if occurrence:
        current, index, cls = occurrence
        navigate("symbol", records[("symbol", current["steps"][index]["symbol"])], current=current, step=index)
        cdp.evaluate(
            "[...document.querySelectorAll('#step-detail [data-object]')]"
            f".find(x=>x.dataset.object==={json.dumps(cls['name'])}).click()"
        )
        settle()
        check(selected("class", cls), "trace data object did not open its source class")
    else:
        skip("workflow inputs/outputs contain no source class for object drill-down")

    # Search by data-derived name and disambiguate by file when names repeat.
    search_symbol = select_search_symbol(data)
    if search_symbol:
        search = cdp.evaluate(
            "(()=>{const x=document.querySelector('#search');"
            f"x.value={json.dumps(search_symbol['name'])};x.dispatchEvent(new Event('input',{{bubbles:true}}));"
            "return {open:document.querySelector('#search-results').classList.contains('open'),"
            "count:document.querySelectorAll('#search-results .search-result').length}})()"
        )
        result["search"] = search
        check(search["open"] and search["count"] > 0, "global object search found no callable")
        clicked = cdp.evaluate(
            "(()=>{const x=[...document.querySelectorAll('#search-results .search-result')].find(x=>"
            f"x.querySelector('b')?.textContent==={json.dumps(search_symbol['name'])}&&"
            f"x.querySelector('small')?.textContent==='symbol · '+{json.dumps(search_symbol['file'])});"
            "if(!x)return false;x.click();return true})()"
        )
        check(clicked, "global object search did not expose the data-derived callable")
        settle()
        check(selected("symbol", search_symbol), "search result did not navigate to its callable")
    else:
        skip("map has no callable name of at least two characters exposed unambiguously by the 35-result search")

    # Navigate canonical records and reject dangling links actually emitted by the UI
    # (including breadcrumb ancestors), rather than trusting hash text. Every reference in
    # the data was already checked above without a browser, so by default this visits every
    # system, subsystem, component and edge, everything the workflows touch, and an even,
    # deterministic sample of classes, modules and callables. --full-deep-links visits all.
    structural_kinds = ("system", "subsystem", "component", "edge")
    detail = sorted(key for key in records if key[0] not in structural_kinds)
    if full_deep_links:
        chosen_detail = detail
    else:
        touched = {("symbol", step["symbol"]) for current in workflows for step in current["steps"]}
        touched |= {(plurals[plural], record_id) for current in workflows
                    for plural in plurals for record_id in current["touched"].get(plural, [])}
        stride = max(1, len(detail) // 60)
        chosen_detail = sorted({key for key in detail if key in touched} | set(detail[::stride]))
    visit = [key for key in records if key[0] in structural_kinds] + chosen_detail
    broken = []
    for kind, record_id in visit:
        record = records[(kind, record_id)]
        navigate(kind, record)
        if not selected(kind, record):
            broken.append(f"{kind}:{record_id}")
        links = cdp.evaluate(
            "[...document.querySelectorAll('[data-select]')].map(x=>[x.dataset.select,x.dataset.id])"
        )
        for target_kind, target_id in links:
            if target_kind != "object" and (target_kind, target_id) not in records:
                broken.append(f"{target_kind}:{target_id}")
    result["deep_links"] = {"checked": len(visit), "of": len(records), "broken": sorted(set(broken))}
    check(not broken, f"deep links do not resolve: {result['deep_links']['broken']}")
    if not records:
        skip("map has no canonical records for deep-link navigation")

    cdp.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    settle()
    mobile = cdp.evaluate(
        "({viewport:innerWidth,body:document.documentElement.scrollWidth,"
        "trace:document.querySelector('.trace-player')?.scrollWidth,header:document.querySelector('.app-header')?.scrollWidth})"
    )
    result["mobile"] = mobile
    check(mobile["body"] <= mobile["viewport"] + 1, "mobile page has horizontal overflow")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--full-deep-links", action="store_true",
                        help="navigate every record instead of a structural set plus a sample (slow on big maps)")
    args = parser.parse_args()
    # Preserve the original JSON result sections; absent capabilities are explicit
    # SKIPs, while malformed data, broken interactions and connection errors fail.
    result = {key: {} for key in ("initial", "contextual", "step_two", "emit", "factory", "entry",
                                  "search", "callable_view", "binding", "mobile")}
    result.update(skips=[], browser_errors=None)
    cdp = None
    try:
        cdp = CDP(page_socket(args.port))
        cdp.call("Runtime.enable")
        cdp.call("Log.enable")
        cdp.call("Page.enable")
        cdp.events.clear()
        navigation = cdp.call("Page.navigate", {"url": args.url})
        check(not navigation.get("errorText"), f"navigation failed: {navigation.get('errorText')}")
        loaded = False
        for _ in range(60):
            # The explorer writes a deep-link hash on load, so compare without the fragment.
            loaded = cdp.evaluate(
                "document.readyState==='complete'&&"
                "location.href.split('#')[0]==="
                f"new URL({json.dumps(args.url)}).href.split('#')[0]"
            )
            if loaded:
                break
            time.sleep(0.1)
        check(loaded, f"page did not finish loading: {args.url}")
        settle()
        exercise(cdp, result, full_deep_links=args.full_deep_links)
    except (AssertionError, RuntimeError, OSError, ValueError, KeyError, TypeError,
            websocket.WebSocketException) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        if cdp is not None:
            try:
                cdp.call("Runtime.evaluate", {"expression": "0"})
                errors = [event for event in cdp.events if (
                    event.get("method") == "Runtime.exceptionThrown"
                    or (event.get("method") == "Log.entryAdded"
                        and event.get("params", {}).get("entry", {}).get("level") == "error")
                    or (event.get("method") == "Runtime.consoleAPICalled"
                        and event.get("params", {}).get("type") == "error")
                )]
                result["browser_errors"] = len(errors)
                check(not errors, f"browser emitted errors: {errors}")
            except (AssertionError, RuntimeError, OSError, websocket.WebSocketException) as error:
                result["error"] = result.get("error", f"{type(error).__name__}: {error}")
            finally:
                cdp.socket.close()
    print(json.dumps(result, indent=2))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
