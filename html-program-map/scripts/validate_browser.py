#!/usr/bin/env python3
"""Exercise a rendered program map through an existing Chrome DevTools page."""

from __future__ import annotations

import argparse
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
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        remote = result.get("result", {})
        if remote.get("subtype") == "error":
            raise RuntimeError(remote.get("description", "browser evaluation failed"))
        return remote.get("value")


def assert_browser(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def page_socket(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
        targets = json.load(response)
    page = next(target for target in targets if target.get("type") == "page")
    return page["webSocketDebuggerUrl"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    cdp = CDP(page_socket(args.port))
    cdp.call("Runtime.enable")
    cdp.call("Log.enable")
    cdp.call("Page.enable")
    base_url = cdp.evaluate("location.href.split('#')[0]")
    cdp.call("Page.navigate", {"url": base_url})

    for _ in range(40):
        if cdp.evaluate("document.readyState") == "complete":
            break
        time.sleep(0.1)

    expected = cdp.evaluate(
        "(()=>{const D=JSON.parse(document.querySelector('#map-data').textContent);"
        "const subsystem=D.model.subsystems[0];"
        "const components=D.model.components.filter(x=>x.subsystem===subsystem.id);"
        "const componentIds=new Set(components.map(x=>x.id));"
        "D.model.component_edges.filter(e=>componentIds.has(e.from)||componentIds.has(e.to))"
        ".forEach(e=>{componentIds.add(e.from);componentIds.add(e.to)});"
        "const klass=D.classes[0];const edge=D.model.subsystem_edges[0];"
        "return {title:D.model.project.title,systems:D.model.systems.length,"
        "systemEdges:D.model.system_edges.length,subsystems:D.model.subsystems.length,"
        "subsystem:subsystem.id,componentCount:components.length,"
        "componentNodes:componentIds.size,component:components[0],"
        "classes:D.classes.length,variables:D.coverage.variable_total,"
        "metrics:[`${D.coverage.architecture_read}/${D.coverage.architecture_total}`,"
        "String(D.coverage.class_total),String(D.coverage.variable_total)],"
        "searchTerm:klass.qualified_name.split('.').at(-1),edge};})()"
    )

    initial = cdp.evaluate(
        "({title:document.title,nodes:document.querySelectorAll('.node').length,"
        "edges:document.querySelectorAll('.edge').length,"
        "metrics:[...document.querySelectorAll('.metric b')].map(x=>x.textContent)})"
    )
    assert_browser(initial["title"] == expected["title"], "title did not render")
    assert_browser(initial["nodes"] == expected["systems"], "system diagram is incomplete")
    assert_browser(initial["edges"] == expected["systemEdges"], "system relationships are incomplete")
    assert_browser(initial["metrics"][:3] == expected["metrics"], "coverage metrics drifted")

    cdp.evaluate("document.querySelector('[data-level=subsystem]').click()")
    time.sleep(0.15)
    subsystem = cdp.evaluate(
        "({nodes:document.querySelectorAll('.node').length,"
        "blocks:document.querySelectorAll('details.subsystem').length})"
    )
    assert_browser(
        subsystem == {"nodes": expected["subsystems"], "blocks": expected["subsystems"]},
        "subsystem view is incomplete",
    )

    cdp.evaluate(
        "document.querySelector('.edge').dispatchEvent(new MouseEvent('click',{bubbles:true}))"
    )
    time.sleep(0.1)
    assert_browser(
        cdp.evaluate("document.querySelector('#inspector').textContent.includes('Payload / contracts')"),
        "arrow did not open relationship details",
    )

    cdp.evaluate("document.querySelector('[data-level=component]').click()")
    time.sleep(0.15)
    component = cdp.evaluate(
        "({nodes:document.querySelectorAll('.node').length,"
        "cards:document.querySelectorAll('#atlas .card').length,"
        "scope:document.querySelector('#subsystem-select').value})"
    )
    assert_browser(
        component["nodes"] == expected["componentNodes"],
        "component graph did not include the accepted local and neighbor set",
    )
    assert_browser(component["cards"] == expected["componentCount"], "default component scope drifted")
    assert_browser(component["scope"] == expected["subsystem"], "component scope did not persist")

    cdp.evaluate(
        "document.querySelector('.node').dispatchEvent(new MouseEvent('click',{bubbles:true}))"
    )
    time.sleep(0.1)
    assert_browser(
        cdp.evaluate("document.querySelector('#inspector').textContent.includes('Constituent + used classes')"),
        "component did not reveal class composition",
    )

    cdp.evaluate("document.querySelector('[data-level=class]').click()")
    time.sleep(0.15)
    class_rows = cdp.evaluate("document.querySelectorAll('#atlas .row').length")
    assert_browser(class_rows == expected["classes"], "class index does not expose all declarations")
    cdp.evaluate("document.querySelector('#atlas .row button').click()")
    time.sleep(0.1)
    assert_browser(
        cdp.evaluate("document.querySelector('#inspector').textContent.includes('Variables')"),
        "class did not reveal variables",
    )

    cdp.evaluate("document.querySelector('[data-level=variable]').click()")
    time.sleep(0.2)
    assert_browser(
        cdp.evaluate("document.querySelectorAll('#atlas .row').length") == expected["variables"],
        "variable index does not expose all recovered fields",
    )

    search_count = cdp.evaluate(
        f"(()=>{{const x=document.querySelector('#search');x.value={json.dumps(expected['searchTerm'])};"
        "x.dispatchEvent(new Event('input',{bubbles:true}));"
        "return document.querySelectorAll('#search-results .search-result').length})()"
    )
    assert_browser(search_count > 0, "global search found no class result")

    component_hash = (
        "#level=component&id="
        + expected["component"]["id"]
        + "&subsystem="
        + expected["component"]["subsystem"]
    )
    cdp.evaluate(f"location.hash={json.dumps(component_hash)}")
    time.sleep(0.15)
    assert_browser(
        cdp.evaluate("document.querySelector('#inspector h2').textContent")
        == expected["component"]["name"],
        "component deep link did not restore selection",
    )
    edge_hash = "#level=subsystem&id=edge%3A" + expected["edge"]["id"]
    cdp.evaluate(f"location.hash={json.dumps(edge_hash)}")
    time.sleep(0.15)
    assert_browser(
        cdp.evaluate("document.querySelector('#inspector h2').textContent")
        == expected["edge"]["label"],
        "edge deep link did not restore relationship inspector",
    )

    cdp.call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
    )
    time.sleep(0.15)
    mobile = cdp.evaluate(
        "({viewport:innerWidth,body:document.body.scrollWidth,"
        "toolbar:document.querySelector('.toolbar').scrollWidth})"
    )
    assert_browser(mobile["body"] <= mobile["viewport"] + 1, "mobile page has horizontal overflow")

    exceptions = [
        event
        for event in cdp.events
        if event.get("method") in {"Runtime.exceptionThrown", "Log.entryAdded"}
        and (
            event.get("method") == "Runtime.exceptionThrown"
            or event.get("params", {}).get("entry", {}).get("level") == "error"
        )
    ]
    assert_browser(not exceptions, f"browser emitted errors: {exceptions}")
    print(
        json.dumps(
            {
                "initial": initial,
                "subsystem": subsystem,
                "component": component,
                "class_rows": class_rows,
                "variable_rows": expected["variables"],
                "search_results": search_count,
                "mobile": mobile,
                "browser_errors": len(exceptions),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
