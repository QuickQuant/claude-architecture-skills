#!/usr/bin/env python3
"""Render a self-contained expandable HTML program map from model + ledger JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


EDGE_FIELDS = {
    "id",
    "level",
    "from",
    "to",
    "label",
    "trigger",
    "mechanism",
    "payload",
    "guarantees",
    "hazards",
    "evidence",
    "freshness",
}


def class_id(record: dict[str, Any]) -> str:
    return f"{record['file']}:{record['line']}:{record['qualified_name']}"


def assign_memberships(model: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    classes = []
    for source_record in ledger["source_scan"]["classes"]:
        record = dict(source_record)
        memberships: dict[str, set[str]] = {}
        for component in model["components"]:
            for rule in component.get("class_rules", []):
                file_matches = not rule.get("file") or re.search(rule["file"], record["file"])
                name_matches = not rule.get("name") or re.search(
                    rule["name"], record["qualified_name"]
                )
                if file_matches and name_matches:
                    memberships.setdefault(component["id"], set()).add(rule.get("role", "member"))
        record["id"] = class_id(record)
        record["memberships"] = [
            {"component": component, "roles": sorted(roles)}
            for component, roles in sorted(memberships.items())
        ]
        classes.append(record)
    return classes


def validate(
    model: dict[str, Any],
    ledger: dict[str, Any],
    classes: list[dict[str, Any]],
    read_count: int,
) -> list[str]:
    errors: list[str] = []
    collections = {
        "system": model["systems"],
        "subsystem": model["subsystems"],
        "component": model["components"],
    }
    ids_by_level: dict[str, set[str]] = {}
    for level, records in collections.items():
        ids = [record["id"] for record in records]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {level} id")
        ids_by_level[level] = set(ids)

    for component in model["components"]:
        if component["subsystem"] not in ids_by_level["subsystem"]:
            errors.append(
                f"component {component['id']} references missing subsystem {component['subsystem']}"
            )

    all_edges = (
        model.get("system_edges", [])
        + model.get("subsystem_edges", [])
        + model.get("component_edges", [])
    )
    edge_ids = [edge["id"] for edge in all_edges]
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("duplicate edge id")
    for edge in all_edges:
        missing = EDGE_FIELDS - edge.keys()
        if missing:
            errors.append(f"edge {edge.get('id')} missing {sorted(missing)}")
            continue
        level_ids = ids_by_level.get(edge["level"], set())
        if edge["from"] not in level_ids or edge["to"] not in level_ids:
            errors.append(f"edge {edge['id']} references a missing {edge['level']} node")

    unmapped = [record["id"] for record in classes if not record["memberships"]]
    if unmapped:
        errors.append(f"{len(unmapped)} classes have no component membership")
    class_ids = [record["id"] for record in classes]
    if len(class_ids) != len(set(class_ids)):
        errors.append("duplicate canonical class id")

    architecture_count = ledger["architecture"]["file_count"]
    if read_count < 0 or read_count > architecture_count:
        errors.append("architecture read count is outside the inventory boundary")
    return errors


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>__TITLE__</title>
<style>
:root{--paper:#f3efe5;--paper-2:#fffdf7;--ink:#1f2822;--muted:#687168;--line:#c9c7ba;--green:#1e5638;--green-2:#dce9df;--sage:#78947e;--blue:#406b82;--amber:#a36a25;--plum:#75536f;--rose:#995f62;--slate:#59656c;--shadow:0 16px 42px rgba(38,44,38,.09);--radius:18px;--sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--serif:Iowan Old Style,Palatino Linotype,Book Antiqua,Georgia,serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans)}button,input,select{font:inherit}button{color:inherit}.shell{width:min(1540px,calc(100% - 32px));margin:auto}.hero{padding:54px 0 26px;border-bottom:1px solid rgba(31,40,34,.13);background:radial-gradient(circle at 80% 0,rgba(30,86,56,.12),transparent 35%),linear-gradient(180deg,#fbf8ef 0,var(--paper) 100%)}.eyebrow{text-transform:uppercase;letter-spacing:.17em;font-size:.72rem;font-weight:800;color:var(--green)}h1,h2,h3{font-family:var(--serif);letter-spacing:-.02em}h1{font-size:clamp(2.45rem,5vw,5.2rem);line-height:.95;margin:.22em 0 .3em;max-width:12ch;font-weight:650}.lede{font:1.08rem/1.7 var(--sans);max-width:76ch;color:#49534b}.hero-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}.badge{display:inline-flex;gap:7px;align-items:center;border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:rgba(255,253,247,.68);font-size:.8rem}.badge strong{color:var(--green)}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:26px 0 0}.metric{padding:16px;border:1px solid var(--line);border-radius:14px;background:rgba(255,253,247,.72)}.metric b{display:block;font:700 1.55rem/1 var(--serif);margin-bottom:6px}.metric span{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.freshness{margin-top:14px;border-left:4px solid var(--amber);background:#fff7e7;padding:12px 14px;border-radius:0 10px 10px 0;color:#6e511f}.toolbar-wrap{position:sticky;top:0;z-index:20;background:rgba(243,239,229,.93);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.toolbar{display:grid;grid-template-columns:auto minmax(220px,1fr) auto auto;gap:10px;align-items:center;padding:12px 0}.levels{display:flex;gap:4px;padding:4px;border:1px solid var(--line);border-radius:12px;background:var(--paper-2);overflow:auto}.levels button{border:0;border-radius:8px;background:transparent;padding:8px 11px;white-space:nowrap;cursor:pointer;font-size:.82rem;font-weight:750}.levels button[aria-pressed=true]{background:var(--green);color:white}.search-wrap{position:relative}.search-wrap input{width:100%;border:1px solid var(--line);border-radius:12px;background:var(--paper-2);padding:11px 13px 11px 38px}.search-wrap:before{content:"⌕";position:absolute;left:13px;top:5px;font:1.5rem var(--serif);color:var(--muted)}select,.tool-button{border:1px solid var(--line);border-radius:12px;background:var(--paper-2);padding:10px 12px}.tool-button{cursor:pointer;font-weight:700}.search-results{position:absolute;left:0;right:0;top:48px;max-height:60vh;overflow:auto;background:var(--paper-2);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:6px;display:none}.search-results.open{display:block}.search-result{width:100%;border:0;border-radius:9px;background:transparent;text-align:left;padding:9px 10px;cursor:pointer}.search-result:hover,.search-result:focus{background:var(--green-2)}.search-result small{display:block;color:var(--muted)}.breadcrumb{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:15px 0 6px;color:var(--muted);font-size:.82rem}.breadcrumb button{border:0;background:none;color:var(--green);font-weight:750;cursor:pointer;padding:2px}.main{padding:14px 0 70px}.panel{border:1px solid var(--line);border-radius:var(--radius);background:var(--paper-2);box-shadow:var(--shadow)}.stage{padding:20px;margin-bottom:18px;overflow:hidden}.stage-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:12px}.stage h2{font-size:1.7rem;margin:0}.stage-copy{color:var(--muted);max-width:76ch;margin:4px 0 0}.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:.76rem;color:var(--muted)}.legend i{display:inline-block;width:18px;border-top:2px solid var(--green);margin-right:5px;vertical-align:middle}.legend i.dash{border-top-style:dashed}.diagram{overflow:auto;min-height:400px;border:1px solid #dad7ca;background:linear-gradient(rgba(30,86,56,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(30,86,56,.035) 1px,transparent 1px),#fbf9f2;background-size:24px 24px;border-radius:14px}.diagram svg{display:block;min-width:900px;width:100%;height:auto}.node{cursor:pointer}.node rect{fill:#fffdf7;stroke:#969b91;stroke-width:1.4;filter:drop-shadow(0 5px 8px rgba(20,30,24,.08))}.node.primary rect,.node.selected rect{stroke:var(--green);stroke-width:3}.node .node-name{font:700 14px var(--sans);fill:var(--ink)}.node .node-kind{font:700 10px var(--sans);letter-spacing:.08em;text-transform:uppercase;fill:var(--muted)}.node .node-count{font:12px var(--sans);fill:var(--green)}.node:focus rect,.edge:focus .edge-visible{stroke:#111;stroke-width:4}.edge{cursor:pointer}.edge-visible{fill:none;stroke:#52675a;stroke-width:2;marker-end:url(#arrow)}.edge-hit{fill:none;stroke:transparent;stroke-width:18}.edge-label-bg{fill:#fffdf7;stroke:#c8c8bc}.edge-label{font:700 10px var(--sans);fill:#314038}.edge:hover .edge-visible{stroke:var(--green);stroke-width:3}.lower{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.75fr);gap:18px}.atlas,.inspector{padding:20px}.inspector{position:sticky;top:92px;align-self:start;max-height:calc(100vh - 115px);overflow:auto}.section-title{display:flex;justify-content:space-between;align-items:baseline;gap:12px}.section-title h2{margin:0;font-size:1.45rem}.section-title small{color:var(--muted)}.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:12px;margin-top:14px}.card{border:1px solid var(--line);border-radius:14px;background:#fbf9f2;padding:15px;text-align:left}.card button.card-main{border:0;background:none;padding:0;width:100%;text-align:left;cursor:pointer}.card h3{font:700 1.08rem var(--serif);margin:0 0 5px}.card p{margin:0;color:var(--muted);font-size:.86rem}.card-foot{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.pill{display:inline-flex;border-radius:999px;background:#e8e8df;padding:4px 8px;font-size:.7rem;color:#4c554e}.pill.green{background:var(--green-2);color:var(--green)}details.subsystem{border:1px solid var(--line);border-radius:14px;background:#fbf9f2;margin:10px 0;overflow:hidden}details.subsystem>summary{list-style:none;cursor:pointer;padding:15px 16px;font-weight:800;display:flex;justify-content:space-between;gap:14px}details.subsystem>summary::-webkit-details-marker{display:none}details.subsystem>summary:after{content:"+";font-size:1.2rem;color:var(--green)}details.subsystem[open]>summary:after{content:"−"}.details-body{border-top:1px solid var(--line);padding:14px 16px}.mini-list{display:grid;gap:7px}.mini-button{display:flex;justify-content:space-between;gap:12px;width:100%;border:1px solid var(--line);border-radius:10px;background:var(--paper-2);padding:9px 10px;text-align:left;cursor:pointer}.mini-button:hover,.mini-button:focus{border-color:var(--green);background:var(--green-2)}.list{margin-top:14px;border-top:1px solid var(--line)}.row{display:grid;grid-template-columns:minmax(180px,.8fr) minmax(240px,1.3fr) auto;gap:12px;align-items:center;padding:11px 5px;border-bottom:1px solid #deddd3}.row button{border:0;background:none;text-align:left;padding:0;color:var(--green);font-weight:800;cursor:pointer}.row .path{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);word-break:break-all}.row .count{font-size:.75rem;color:var(--muted)}.inspector h2{font-size:1.6rem;margin:.1em 0}.inspector h3{font:800 .78rem var(--sans);text-transform:uppercase;letter-spacing:.1em;color:var(--green);margin:22px 0 8px}.inspector p{color:#4c554e}.kv{display:grid;grid-template-columns:100px 1fr;gap:7px 12px;font-size:.84rem}.kv dt{color:var(--muted)}.kv dd{margin:0;word-break:break-word}.flow-list{display:grid;gap:7px}.flow-button{width:100%;border:1px solid var(--line);border-radius:10px;background:#fbf9f2;padding:9px 10px;text-align:left;cursor:pointer}.flow-button b{color:var(--green)}.var-table{width:100%;border-collapse:collapse;font-size:.78rem}.var-table th,.var-table td{text-align:left;border-bottom:1px solid var(--line);padding:7px 6px;vertical-align:top}.var-table th{color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.07em}.evidence{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-word}.empty{padding:28px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:12px;margin-top:14px}.coverage{margin-top:18px;padding:20px}.coverage h2{margin-top:0}.coverage details{border-top:1px solid var(--line);padding:12px 0}.coverage summary{cursor:pointer;font-weight:800}.source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:5px 16px;margin-top:10px}.source-row{font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#596159;word-break:break-all}.source-row b{color:var(--ink)}.scope-note{border:1px solid #d7caa8;background:#fff8e8;border-radius:12px;padding:12px 14px;margin-top:14px;font-size:.83rem}.tone-sage{border-top:4px solid var(--sage)}.tone-ink{border-top:4px solid var(--ink)}.tone-blue{border-top:4px solid var(--blue)}.tone-amber{border-top:4px solid var(--amber)}.tone-green{border-top:4px solid var(--green)}.tone-plum{border-top:4px solid var(--plum)}.tone-slate{border-top:4px solid var(--slate)}.tone-rose{border-top:4px solid var(--rose)}a{color:var(--green)}:focus-visible{outline:3px solid rgba(30,86,56,.35);outline-offset:2px}@media(max-width:980px){.metrics{grid-template-columns:repeat(2,1fr)}.toolbar{grid-template-columns:1fr auto}.levels{grid-column:1/-1}.search-wrap{grid-column:1/2}.lower{grid-template-columns:1fr}.inspector{position:static;max-height:none}.stage-head{display:block}.legend{margin-top:10px}}@media(max-width:620px){.shell{width:min(100% - 20px,1540px)}.hero{padding-top:34px}h1{font-size:2.65rem}.metrics{grid-template-columns:1fr 1fr}.metric{padding:12px}.toolbar{grid-template-columns:1fr 1fr}.search-wrap{grid-column:1/-1}.tool-button,select{width:100%}.stage,.atlas,.inspector,.coverage{padding:14px}.row{grid-template-columns:1fr}.diagram{margin-inline:-5px}.source-grid{grid-template-columns:1fr}}@media print{body{background:#fff;font-size:10pt}.toolbar-wrap,.tool-button,.search-results{display:none!important}.shell{width:100%}.panel{box-shadow:none;break-inside:avoid}.lower{display:block}.inspector{position:static;max-height:none;margin-top:12px}.diagram{overflow:visible}.diagram svg{min-width:0}.coverage details>*{display:block!important}.coverage details{break-inside:avoid}.hero{padding:20px 0}.card-grid{grid-template-columns:repeat(2,1fr)}}
.node .node-name{font-size:13px}.diagram svg[aria-label^="Component"] .node-name{font-size:11px}.edge-index-bg{fill:var(--green);stroke:#fffdf7;stroke-width:2}.edge-index{font:800 9px var(--sans);fill:white;pointer-events:none}.component-edge-key{border-top:1px solid var(--line);padding:13px;background:rgba(255,253,247,.82)}.component-edge-key>p{margin:0 0 9px;color:var(--muted);font-size:.76rem}.component-edge-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:6px}.component-edge-record{display:grid;grid-template-columns:28px 1fr;gap:8px;align-items:start;border:1px solid var(--line);border-radius:9px;background:#fffdf7;padding:7px 8px;text-align:left;cursor:pointer}.component-edge-record>b{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--green);color:white;font-size:.68rem}.component-edge-record span{font-size:.72rem;font-weight:750;line-height:1.25}.component-edge-record small{display:block;color:var(--muted);font-weight:500;margin-top:2px}.component-edge-record:hover,.component-edge-record:focus{border-color:var(--green);background:var(--green-2)}
</style>
</head>
<body>
<header class="hero"><div class="shell">
  <div class="eyebrow">Expandable architecture field guide · diagram-design grammar</div>
  <h1 id="page-title"></h1>
  <p class="lede" id="purpose"></p>
  <div class="hero-meta" id="hero-meta"></div>
  <div class="metrics" id="metrics"></div>
  <div class="freshness" id="freshness"></div>
</div></header>
<div class="toolbar-wrap"><div class="shell toolbar">
  <nav class="levels" aria-label="Abstraction level" id="levels"></nav>
  <div class="search-wrap"><input id="search" type="search" autocomplete="off" placeholder="Search systems, components, classes, variables, files…" aria-label="Search complete program map"><div id="search-results" class="search-results" role="listbox"></div></div>
  <select id="category" aria-label="Class category"><option value="all">All class categories</option><option value="runtime">Runtime</option><option value="frontend">Frontend</option><option value="test">Test</option><option value="tooling">Tooling</option><option value="root-support">Support/archive</option></select>
  <button class="tool-button" id="copy-link" type="button">Copy view link</button>
</div></div>
<main class="shell main">
  <nav class="breadcrumb" id="breadcrumb" aria-label="Current architecture context"></nav>
  <section class="panel stage" aria-labelledby="stage-title">
    <div class="stage-head"><div><div class="eyebrow" id="stage-eyebrow"></div><h2 id="stage-title"></h2><p class="stage-copy" id="stage-copy"></p></div><div class="legend"><span><i></i> runtime/control</span><span><i class="dash"></i> optional/async</span><span>Click arrows for payload + evidence</span></div></div>
    <div class="diagram" id="diagram"></div>
  </section>
  <div class="lower">
    <section class="panel atlas" aria-labelledby="atlas-title"><div class="section-title"><h2 id="atlas-title">Atlas</h2><small id="atlas-count"></small></div><div id="atlas"></div></section>
    <aside class="panel inspector" id="inspector" aria-live="polite"></aside>
  </div>
  <section class="panel coverage" aria-labelledby="coverage-title"><h2 id="coverage-title">Coverage, freshness, and limits</h2><div id="coverage"></div></section>
</main>
<script id="map-data" type="application/json">__DATA__</script>
<script>
(()=>{'use strict';
const D=JSON.parse(document.getElementById('map-data').textContent);const $=s=>document.querySelector(s);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LEVELS=['system','subsystem','component','class','variable'];const by=(arr,id)=>arr.find(x=>x.id===id);const compsBySub=id=>D.model.components.filter(x=>x.subsystem===id);const membershipsFor=cid=>D.classes.filter(c=>c.memberships.some(m=>m.component===cid));
const classById=id=>D.classes.find(c=>c.id===id);const edges=[...D.model.system_edges,...D.model.subsystem_edges,...D.model.component_edges];const edgeById=id=>edges.find(e=>e.id===id);
let state={level:'system',id:null,subsystem:D.model.subsystems[0]?.id||'',q:'',category:'all'};function parseHash(){const p=new URLSearchParams(location.hash.replace(/^#/,''));const level=p.get('level');state.level=LEVELS.includes(level)?level:'system';state.id=p.get('id');state.subsystem=p.get('subsystem')||state.subsystem;}
function setHash(next={},push=true){state={...state,...next};const p=new URLSearchParams();p.set('level',state.level);if(state.id)p.set('id',state.id);if(state.subsystem&&['component','class','variable'].includes(state.level))p.set('subsystem',state.subsystem);const h='#'+p.toString();if(push)location.hash=h;else history.replaceState(null,'',h);render();}
function setup(){document.title=D.model.project.title;$('#page-title').textContent=D.model.project.title;$('#purpose').textContent=D.model.project.purpose;$('#hero-meta').innerHTML=`<span class="badge"><strong>Current HEAD</strong> ${esc(D.model.project.current_head)}</span><span class="badge"><strong>Architecture map</strong> ${esc(D.model.project.architecture_commit)} · ${esc(D.model.project.architecture_generated)}</span><span class="badge"><strong>Generated</strong> ${esc(D.model.project.map_generated)}</span><span class="badge"><strong>Method</strong> bottom-up ↔ top-down</span>`;const c=D.coverage;$('#metrics').innerHTML=[[`${c.architecture_read}/${c.architecture_total}`,'architecture files read'],[c.class_total,'classes visible'],[c.variable_total,'variables recovered'],[`${c.component_total} / ${c.subsystem_total}`,'components / subsystems'],[c.edge_total,'clickable relations']].map(x=>`<div class="metric"><b>${esc(x[0])}</b><span>${esc(x[1])}</span></div>`).join('');$('#freshness').innerHTML=`<strong>Freshness boundary:</strong> architecture prose describes <code>${esc(D.model.project.architecture_commit)}</code>; the class/variable ledger is from current <code>${esc(D.model.project.current_head)}</code>. Mixed claims are labeled rather than silently merged.`;$('#levels').innerHTML=LEVELS.map(l=>`<button type="button" data-level="${l}">${l[0].toUpperCase()+l.slice(1)}</button>`).join('');$('#levels').addEventListener('click',e=>{const b=e.target.closest('[data-level]');if(b)setHash({level:b.dataset.level,id:null});});$('#category').addEventListener('change',e=>{state.category=e.target.value;renderAtlas();});$('#search').addEventListener('input',e=>{state.q=e.target.value.trim();renderSearch();renderAtlas();});$('#copy-link').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);$('#copy-link').textContent='Copied';setTimeout(()=>$('#copy-link').textContent='Copy view link',1300)}catch{prompt('Copy this link',location.href)}});window.addEventListener('hashchange',()=>{parseHash();render();});document.addEventListener('keydown',e=>{const target=e.target.closest('[data-action]');if(target&&(e.key==='Enter'||e.key===' ')){e.preventDefault();target.click()}});window.addEventListener('beforeprint',()=>document.querySelectorAll('details').forEach(d=>d.open=true));parseHash();if(!location.hash)setHash({},false);renderCoverage();render();}
function breadcrumb(){const items=[{label:D.model.project.name,level:'system'}];if(state.level!=='system'){if(['subsystem','component','class','variable'].includes(state.level))items.push({label:'Subsystems',level:'subsystem'});if(['component','class','variable'].includes(state.level)){const s=by(D.model.subsystems,state.subsystem);if(s)items.push({label:s.name,level:'component',subsystem:s.id});}if(['class','variable'].includes(state.level))items.push({label:'Classes',level:'class',subsystem:state.subsystem});if(state.level==='variable')items.push({label:'Variables',level:'variable',subsystem:state.subsystem});}$('#breadcrumb').innerHTML=items.map((x,i)=>`${i?' <span>›</span> ':''}<button type="button" data-i="${i}">${esc(x.label)}</button>`).join('');$('#breadcrumb').querySelectorAll('button').forEach((b,i)=>b.onclick=()=>setHash({level:items[i].level,id:null,subsystem:items[i].subsystem||state.subsystem}));}
function render(){document.querySelectorAll('[data-level]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.level===state.level)));$('#category').value=state.category;breadcrumb();renderStage();renderAtlas();renderInspector();}
function renderStage(){const meta={system:['System landscape',`What ${D.model.project.name} does and what crosses its boundary.`],subsystem:['Subsystem flow',`Cohesive responsibilities inside ${D.model.project.name}; arrows aggregate component relationships.`],component:['Component composition','Components in the selected subsystem plus their directly connected neighbors.'],class:['Class composition','Canonical source declarations, many-to-many component membership, and static state.'],variable:['Variable surface','Every statically recovered class/instance field with its source and owning class.']}[state.level];$('#stage-eyebrow').textContent=meta[0];$('#stage-title').textContent=state.level==='component'?(by(D.model.subsystems,state.subsystem)?.name||'Components'):meta[0];$('#stage-copy').textContent=meta[1];if(state.level==='system')drawNetwork(D.model.systems,D.model.system_edges,'system');else if(state.level==='subsystem')drawNetwork(D.model.subsystems,D.model.subsystem_edges,'subsystem');else if(state.level==='component')drawComponentNetwork();else renderIndexStage();}
function renderIndexStage(){const subset=D.classes.filter(catMatch);const vars=subset.flatMap(c=>c.variables.map(v=>({...v,classId:c.id,className:c.qualified_name,file:c.file,category:c.category})));const isVar=state.level==='variable';const total=isVar?vars.length:subset.length;$('#diagram').innerHTML=`<div style="min-height:400px;display:grid;place-items:center;padding:34px"><div style="max-width:720px;text-align:center"><div class="eyebrow">${isVar?'Static state inventory':'Canonical declaration inventory'}</div><h2 style="font-size:clamp(2rem,5vw,4.5rem);margin:.15em 0">${total.toLocaleString()} ${isVar?'variables':'classes'}</h2><p style="color:var(--muted)">${isVar?'Fields include class declarations, self/cls assignments, literal dynamic setattr calls, and properties where recoverable.':'A class appears once canonically here and may participate in several components. Use category and search filters; click a row for its composition and variables.'}</p><div class="card-foot" style="justify-content:center">${Object.entries(D.coverage.classes_by_category).map(([k,v])=>`<span class="pill">${esc(k)} · ${v}</span>`).join('')}</div></div></div>`;}
function edgeAnchor(cx,cy,tx,ty,w,h){const dx=tx-cx,dy=ty-cy;if(!dx&&!dy)return[cx,cy];const scale=1/Math.max(Math.abs(dx)/(w/2),Math.abs(dy)/(h/2));return[cx+dx*scale,cy+dy*scale]}
function drawNetwork(nodes,edgeSet,level){const w=190,h=92;const routePoints=edgeSet.flatMap(e=>[...(e.via||[]),...(e.label_position?[e.label_position]:[])]);const width=Math.max(level==='system'?900:960,...nodes.map(n=>n.x+w+40),...routePoints.map(p=>p[0]+90));const height=Math.max(level==='system'?640:650,...nodes.map(n=>n.y+h+40),...routePoints.map(p=>p[1]+40));let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(level)} relationship diagram"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#52675a"/></marker></defs>`;for(const e of edgeSet){const a=by(nodes,e.from),b=by(nodes,e.to);if(!a||!b)continue;const x1=a.x+w/2,y1=a.y+h/2,x2=b.x+w/2,y2=b.y+h/2;const via=e.via||[];const first=via[0]||[x2,y2],last=via.at(-1)||[x1,y1];const start=edgeAnchor(x1,y1,first[0],first[1],w,h),end=edgeAnchor(x2,y2,last[0],last[1],w,h);const points=[start,...via,end];const path=points.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');const fallback=[(start[0]+end[0])/2,(start[1]+end[1])/2];const label=e.label_position||fallback;const mx=label[0],my=label[1];const labelW=Math.min(156,Math.max(62,e.label.length*6.3));const dash=e.mechanism.toLowerCase().includes('async')?'stroke-dasharray="7 5"':'';svg+=`<g class="edge" tabindex="0" role="button" aria-label="Relationship ${esc(e.label)}" data-edge="${esc(e.id)}" data-action="edge"><path class="edge-hit" d="${path}"/><path class="edge-visible" ${dash} d="${path}"/><rect class="edge-label-bg" x="${mx-labelW/2}" y="${my-11}" width="${labelW}" height="22" rx="7"/><text class="edge-label" x="${mx}" y="${my+3}" text-anchor="middle">${esc(e.label)}</text></g>`;}for(const n of nodes){const count=level==='subsystem'?`${compsBySub(n.id).length} components`:n.kind||level;svg+=`<g class="node ${n.kind==='primary'?'primary':''} ${state.id===n.id?'selected':''}" tabindex="0" role="button" aria-label="Open ${esc(n.name)}" data-node="${esc(n.id)}" data-node-level="${level}" data-action="node" transform="translate(${n.x},${n.y})"><rect width="${w}" height="${h}" rx="15"/><text class="node-kind" x="14" y="19">${esc(count)}</text><text class="node-name" x="14" y="45">${esc(n.name)}</text><text class="node-count" x="14" y="69">click to inspect</text></g>`;}svg+='</svg>';$('#diagram').innerHTML=svg;wireDiagram();}
function drawComponentNetwork(){const local=compsBySub(state.subsystem),selected=new Set(local.map(c=>c.id));const relevant=D.model.component_edges.filter(e=>selected.has(e.from)||selected.has(e.to));const neighborIds=new Set;relevant.forEach(e=>{if(!selected.has(e.from))neighborIds.add(e.from);if(!selected.has(e.to))neighborIds.add(e.to)});const neighbors=[...neighborIds].map(id=>by(D.model.components,id)).filter(Boolean);const incoming=neighbors.filter(n=>relevant.some(e=>e.from===n.id&&selected.has(e.to)));const outgoing=neighbors.filter(n=>!incoming.includes(n));const w=190,h=84,width=Math.max(980,local.length*215+60,incoming.length*230+60,outgoing.length*230+60),height=650;const row=(records,y)=>records.map((n,i)=>({...n,x:records.length===1?(width-w)/2:30+i*(width-w-60)/(records.length-1),y,kind:selected.has(n.id)?'local':'neighbor'}));const nodes=[...row(incoming,34),...row(local,274),...row(outgoing,522)];let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Component relationship diagram with numbered flows"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#52675a"/></marker></defs><text class="node-kind" x="30" y="20">INBOUND NEIGHBORS</text><text class="node-kind" x="30" y="260">SELECTED SUBSYSTEM</text><text class="node-kind" x="30" y="508">OUTBOUND NEIGHBORS</text>`;for(const [i,e] of relevant.entries()){const a=by(nodes,e.from),b=by(nodes,e.to);if(!a||!b)continue;const aLocal=selected.has(e.from),bLocal=selected.has(e.to);let lane;if(aLocal&&bLocal)lane=215-(i%5)*16;else if(Math.min(a.y,b.y)<200)lane=160+(i%5)*15;else lane=420+(i%5)*15;const ac=[a.x+w/2,a.y+h/2],bc=[b.x+w/2,b.y+h/2],start=edgeAnchor(ac[0],ac[1],ac[0],lane,w,h),end=edgeAnchor(bc[0],bc[1],bc[0],lane,w,h);const path=`M${start[0]},${start[1]} C${start[0]},${lane} ${end[0]},${lane} ${end[0]},${end[1]}`;const mx=(start[0]+end[0])/2+(i%3-1)*12,my=lane;const num=String(i+1).padStart(2,'0');svg+=`<g class="edge" tabindex="0" role="button" aria-label="Flow ${num}: ${esc(e.label)}" data-edge="${esc(e.id)}" data-action="edge"><title>${num} · ${esc(nameFor('component',e.from))} → ${esc(nameFor('component',e.to))}: ${esc(e.label)}</title><path class="edge-hit" d="${path}"/><path class="edge-visible" d="${path}"/><circle class="edge-index-bg" cx="${mx}" cy="${my}" r="11"/><text class="edge-index" x="${mx}" y="${my+3}" text-anchor="middle">${num}</text></g>`;}for(const n of nodes){const count=membershipsFor(n.id).length;svg+=`<g class="node ${selected.has(n.id)?'primary':''} ${state.id===n.id?'selected':''}" tabindex="0" role="button" aria-label="Open ${esc(n.name)}" data-node="${esc(n.id)}" data-node-level="component" data-action="node" transform="translate(${n.x},${n.y})"><rect width="${w}" height="${h}" rx="14"/><text class="node-kind" x="13" y="18">${selected.has(n.id)?'component':'neighbor'}</text><text class="node-name" x="13" y="43">${esc(n.name)}</text><text class="node-count" x="13" y="65">${count} classes</text></g>`;}svg+='</svg>';const key=`<div class="component-edge-key"><p><strong>Numbered relationships.</strong> Select a line or record for trigger, payload, mechanism, guarantees, hazards, evidence, and freshness.</p><div class="component-edge-grid">${relevant.map((e,i)=>`<button class="component-edge-record" data-edge="${esc(e.id)}"><b>${String(i+1).padStart(2,'0')}</b><span>${esc(nameFor('component',e.from))} → ${esc(nameFor('component',e.to))}<small>${esc(e.label)}</small></span></button>`).join('')}</div></div>`;$('#diagram').innerHTML=svg+key;wireDiagram();}
function wireDiagram(){$('#diagram').querySelectorAll('[data-edge]').forEach(g=>g.addEventListener('click',()=>setHash({id:'edge:'+g.dataset.edge})));$('#diagram').querySelectorAll('[data-node]').forEach(g=>g.addEventListener('click',()=>{const l=g.dataset.nodeLevel;if(l==='component'){const c=by(D.model.components,g.dataset.node);setHash({level:'component',id:g.dataset.node,subsystem:c.subsystem});}else setHash({level:l,id:g.dataset.node});}));}
function catMatch(c){return state.category==='all'||c.category===state.category}function textMatch(text){return !state.q||String(text).toLowerCase().includes(state.q.toLowerCase())}
function renderAtlas(){const atlas=$('#atlas');if(state.level==='system'){const records=D.model.systems.filter(x=>textMatch(x.name+' '+x.summary));$('#atlas-title').textContent='System landscape';$('#atlas-count').textContent=`${records.length} systems / actors`;atlas.innerHTML=`<div class="card-grid">${records.map(x=>`<article class="card ${x.kind==='primary'?'tone-green':''}"><button class="card-main" data-open="system:${esc(x.id)}"><h3>${esc(x.name)}</h3><p>${esc(x.summary)}</p></button><div class="card-foot"><span class="pill">${esc(x.kind)}</span></div></article>`).join('')}</div>`;}else if(state.level==='subsystem'){const records=D.model.subsystems.filter(x=>textMatch(x.name+' '+x.summary));$('#atlas-title').textContent='Expandable subsystem atlas';$('#atlas-count').textContent=`${records.length} subsystems`;atlas.innerHTML=records.map(s=>{const cs=compsBySub(s.id);return `<details class="subsystem" ${state.id===s.id?'open':''}><summary><span>${esc(s.name)}</span><span class="pill">${cs.length} components</span></summary><div class="details-body"><p>${esc(s.summary)}</p><div class="mini-list">${cs.map(c=>`<button class="mini-button" data-open="component:${esc(c.id)}"><span>${esc(c.name)}</span><span>${membershipsFor(c.id).length} classes</span></button>`).join('')}</div></div></details>`}).join('');}else if(state.level==='component'){const s=by(D.model.subsystems,state.subsystem);const records=compsBySub(state.subsystem).filter(x=>textMatch(x.name+' '+x.summary+' '+x.key_files.join(' ')));$('#atlas-title').textContent=s?`${s.name} components`:'Components';$('#atlas-count').textContent=`${records.length} shown`;atlas.innerHTML=`<div style="margin-top:12px"><label class="eyebrow" for="subsystem-select">Component scope</label><select id="subsystem-select" style="width:100%;margin-top:6px">${D.model.subsystems.map(x=>`<option value="${x.id}" ${x.id===state.subsystem?'selected':''}>${esc(x.name)}</option>`).join('')}</select></div><div class="card-grid">${records.map(c=>`<article class="card tone-${esc(s?.tone||'green')}"><button class="card-main" data-open="component:${esc(c.id)}"><div class="eyebrow">${esc(c.kind)}</div><h3>${esc(c.name)}</h3><p>${esc(c.summary)}</p></button><div class="card-foot"><span class="pill green">${membershipsFor(c.id).length} classes</span><span class="pill">${c.key_files.length} key paths</span></div></article>`).join('')}</div>`;const sel=$('#subsystem-select');if(sel)sel.onchange=()=>setHash({subsystem:sel.value,id:null});}else if(state.level==='class')renderClassAtlas(atlas);else renderVariableAtlas(atlas);wireAtlas();}
function renderClassAtlas(atlas){const records=D.classes.filter(c=>catMatch(c)&&textMatch(c.qualified_name+' '+c.file+' '+c.variables.map(v=>v.name).join(' ')));$('#atlas-title').textContent='Canonical class index';$('#atlas-count').textContent=`${records.length} of ${D.classes.length}`;atlas.innerHTML=records.length?`<div class="list">${records.map(c=>`<div class="row"><button data-open="class:${esc(c.id)}">${esc(c.qualified_name)}</button><span class="path">${esc(c.file)}:${c.line}</span><span class="count">${c.variables.length} vars · ${c.memberships.length} components</span></div>`).join('')}</div>`:`<div class="empty">No classes match the current filters.</div>`;wireAtlas();}
function renderVariableAtlas(atlas){const records=D.classes.filter(catMatch).flatMap(c=>c.variables.map(v=>({...v,classId:c.id,className:c.qualified_name,file:c.file,category:c.category}))).filter(v=>textMatch(v.name+' '+v.annotation+' '+v.className+' '+v.file));$('#atlas-title').textContent='Static variable index';$('#atlas-count').textContent=`${records.length} of ${D.coverage.variable_total}`;atlas.innerHTML=records.length?`<div class="list">${records.map(v=>`<div class="row"><button data-open="class:${esc(v.classId)}">${esc(v.name)}</button><span class="path">${esc(v.className)} · ${esc(v.file)}:${v.line}</span><span class="count">${esc(v.kind)}${v.annotation?' · '+esc(v.annotation):''}</span></div>`).join('')}</div>`:`<div class="empty">No variables match the current filters.</div>`;wireAtlas();}
function wireAtlas(){$('#atlas').querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>{const [type,...rest]=b.dataset.open.split(':');const id=rest.join(':');if(type==='component'){const c=by(D.model.components,id);setHash({level:'component',id,subsystem:c.subsystem});}else setHash({level:type,id});});}
function renderInspector(){const root=$('#inspector');if(state.id?.startsWith('edge:')){const e=edgeById(state.id.slice(5));if(e){root.innerHTML=edgeInspector(e);return}}if(state.level==='system'&&state.id){const x=by(D.model.systems,state.id);if(x){root.innerHTML=nodeInspector(x,'System / actor',D.model.system_edges);return}}if(state.level==='subsystem'&&state.id){const x=by(D.model.subsystems,state.id);if(x){root.innerHTML=subsystemInspector(x);wireInspector();return}}if(state.level==='component'&&state.id){const x=by(D.model.components,state.id);if(x){root.innerHTML=componentInspector(x);wireInspector();return}}if((state.level==='class'||state.level==='variable')&&state.id){const x=classById(state.id);if(x){root.innerHTML=classInspector(x);wireInspector();return}}root.innerHTML=defaultInspector();wireInspector();}
function defaultInspector(){return `<div class="eyebrow">Inspector</div><h2>Select a block or arrow</h2><p>Blocks reveal composition. Arrows reveal trigger, mechanism, payload, guarantees, hazards, evidence, and freshness.</p><div class="scope-note"><strong>Reading rule:</strong> the architecture prose is mapped-commit evidence; classes and variables are current-source evidence. “Mixed” means the page reconciles both.</div>`;}
function nodeInspector(x,label,es){const rel=es.filter(e=>e.from===x.id||e.to===x.id);return `<div class="eyebrow">${esc(label)}</div><h2>${esc(x.name)}</h2><p>${esc(x.summary)}</p><h3>Relationships</h3><div class="flow-list">${rel.map(e=>flowButton(e)).join('')||'None recorded'}</div>`;}
function subsystemInspector(s){const cs=compsBySub(s.id),rel=D.model.subsystem_edges.filter(e=>e.from===s.id||e.to===s.id);return `<div class="eyebrow">Subsystem</div><h2>${esc(s.name)}</h2><p>${esc(s.summary)}</p><dl class="kv"><dt>Components</dt><dd>${cs.length}</dd><dt>Classes</dt><dd>${new Set(cs.flatMap(c=>membershipsFor(c.id).map(x=>x.id))).size}</dd></dl><h3>Components</h3><div class="mini-list">${cs.map(c=>`<button class="mini-button" data-inspect-component="${esc(c.id)}"><span>${esc(c.name)}</span><span>${membershipsFor(c.id).length}</span></button>`).join('')}</div><h3>Aggregated flows</h3><div class="flow-list">${rel.map(flowButton).join('')}</div>`;}
function componentInspector(c){const members=membershipsFor(c.id),rel=D.model.component_edges.filter(e=>e.from===c.id||e.to===c.id);return `<div class="eyebrow">${esc(c.kind)} component</div><h2>${esc(c.name)}</h2><p>${esc(c.summary)}</p><dl class="kv"><dt>Subsystem</dt><dd>${esc(by(D.model.subsystems,c.subsystem)?.name)}</dd><dt>Classes</dt><dd>${members.length}</dd><dt>Evidence</dt><dd class="evidence">${esc(c.architecture_source)}</dd></dl><h3>Key files / function modules</h3><div class="evidence">${c.key_files.map(esc).join('<br>')}</div><h3>Constituent + used classes</h3><div class="mini-list">${members.length?members.map(k=>{const m=k.memberships.find(x=>x.component===c.id);return `<button class="mini-button" data-inspect-class="${esc(k.id)}"><span>${esc(k.qualified_name)}</span><span>${esc(m.roles.join(', '))}</span></button>`}).join(''):'<span class="scope-note">Function-oriented component: no class declaration matched its source surface.</span>'}</div><h3>Component flows</h3><div class="flow-list">${rel.map(flowButton).join('')||'No explicit edge'}</div>`;}
function classInspector(c){return `<div class="eyebrow">${esc(c.category)} · ${esc(c.language)} class</div><h2>${esc(c.qualified_name)}</h2><dl class="kv"><dt>Source</dt><dd class="evidence">${esc(c.file)}:${c.line}–${c.end_line}</dd><dt>Bases</dt><dd>${esc(c.bases.filter(Boolean).join(', ')||'none')}</dd><dt>Components</dt><dd>${c.memberships.map(m=>`<button class="pill" data-inspect-component="${esc(m.component)}">${esc(by(D.model.components,m.component)?.name)} · ${esc(m.roles.join('/'))}</button>`).join(' ')}</dd></dl><h3>Variables</h3>${c.variables.length?`<table class="var-table"><thead><tr><th>Name</th><th>Kind</th><th>Type</th><th>Assigned in</th><th>Line</th></tr></thead><tbody>${c.variables.map(v=>`<tr><td><strong>${esc(v.name)}</strong></td><td>${esc(v.kind)}</td><td class="evidence">${esc(v.annotation||'—')}</td><td>${esc(v.assigned_in||'—')}</td><td>${v.line}</td></tr>`).join('')}</tbody></table>`:'<p>No explicit class/instance variables were statically recovered.</p>'}${c.properties.length?`<h3>Properties</h3><div class="card-foot">${c.properties.map(p=>`<span class="pill">${esc(p.name)} · L${p.line}</span>`).join('')}</div>`:''}<div class="scope-note">Static limit: metaclass/decorator injection, nonliteral setattr, monkey patches, and runtime-generated fields are not proven by this ledger.</div>`;}
function edgeInspector(e){const from=nameFor(e.level,e.from),to=nameFor(e.level,e.to);return `<div class="eyebrow">${esc(e.level)} relationship · ${esc(e.freshness)}</div><h2>${esc(e.label)}</h2><p><strong>${esc(from)}</strong> → <strong>${esc(to)}</strong></p><dl class="kv"><dt>Trigger</dt><dd>${esc(e.trigger)}</dd><dt>Mechanism</dt><dd>${esc(e.mechanism)}</dd></dl><h3>Payload / contracts</h3>${bullet(e.payload)}<h3>Guarantees</h3>${bullet(e.guarantees)}<h3>Hazards / caveats</h3>${bullet(e.hazards)}<h3>Evidence</h3><div class="evidence">${e.evidence.map(esc).join('<br>')}</div>`;}
function nameFor(level,id){const map={system:D.model.systems,subsystem:D.model.subsystems,component:D.model.components};return by(map[level],id)?.name||id}function bullet(xs){return xs.length?`<ul>${xs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p>None recorded.</p>'}function flowButton(e){return `<button class="flow-button" data-inspect-edge="${esc(e.id)}"><b>${esc(nameFor(e.level,e.from))}</b> → <b>${esc(nameFor(e.level,e.to))}</b><br><span>${esc(e.label)} · ${esc(e.mechanism)}</span></button>`;}
function wireInspector(){$('#inspector').querySelectorAll('[data-inspect-edge]').forEach(b=>b.onclick=()=>setHash({id:'edge:'+b.dataset.inspectEdge}));$('#inspector').querySelectorAll('[data-inspect-component]').forEach(b=>b.onclick=()=>{const c=by(D.model.components,b.dataset.inspectComponent);setHash({level:'component',id:c.id,subsystem:c.subsystem})});$('#inspector').querySelectorAll('[data-inspect-class]').forEach(b=>b.onclick=()=>setHash({level:'class',id:b.dataset.inspectClass}));}
function renderSearch(){const root=$('#search-results');if(state.q.length<2){root.classList.remove('open');root.innerHTML='';return}const q=state.q.toLowerCase(),results=[];D.model.systems.forEach(x=>{if((x.name+' '+x.summary).toLowerCase().includes(q))results.push({type:'system',id:x.id,label:x.name,sub:'System'})});D.model.subsystems.forEach(x=>{if((x.name+' '+x.summary).toLowerCase().includes(q))results.push({type:'subsystem',id:x.id,label:x.name,sub:'Subsystem'})});D.model.components.forEach(x=>{if((x.name+' '+x.summary+' '+x.key_files.join(' ')).toLowerCase().includes(q))results.push({type:'component',id:x.id,label:x.name,sub:'Component · '+by(D.model.subsystems,x.subsystem)?.name,subsystem:x.subsystem})});for(const c of D.classes){if(!catMatch(c))continue;if((c.qualified_name+' '+c.file).toLowerCase().includes(q))results.push({type:'class',id:c.id,label:c.qualified_name,sub:'Class · '+c.file});for(const v of c.variables){if(v.name.toLowerCase().includes(q))results.push({type:'variable',id:c.id,label:v.name,sub:'Variable · '+c.qualified_name})}if(results.length>40)break}root.innerHTML=results.slice(0,40).map((r,i)=>`<button class="search-result" role="option" data-result="${i}">${esc(r.label)}<small>${esc(r.sub)}</small></button>`).join('')||'<div class="empty">No matches</div>';root.classList.add('open');root.querySelectorAll('[data-result]').forEach((b,i)=>b.onclick=()=>{const r=results[i];state.q='';$('#search').value='';root.classList.remove('open');if(r.type==='component')setHash({level:'component',id:r.id,subsystem:r.subsystem});else if(r.type==='variable')setHash({level:'variable',id:r.id});else setHash({level:r.type,id:r.id});});}
function renderCoverage(){const c=D.coverage,a=D.ledger.architecture;$('#coverage').innerHTML=`<div class="card-grid"><article class="card"><div class="eyebrow">Architecture corpus</div><h3>${c.architecture_read} / ${c.architecture_total} read</h3><p>${a.line_count.toLocaleString()} lines · SHA-256 <span class="evidence">${esc(a.corpus_sha256)}</span></p></article><article class="card"><div class="eyebrow">Source declarations</div><h3>${c.class_total} / ${c.class_total} classes</h3><p>${c.variable_total} statically recovered variables · ${D.ledger.source_scan.files_scanned} Git-scoped source files · zero parser failures.</p></article><article class="card"><div class="eyebrow">Composition</div><h3>${c.unmapped_classes} unmapped classes</h3><p>${c.component_total} components in ${c.subsystem_total} subsystems; ${c.edge_total} relationship records have detail payloads.</p></article></div><div class="scope-note"><strong>Not implied:</strong> this is class-complete against the declared Git source scan, not a complete function call graph or runtime heap map. Function-only modules remain listed in their components. Runtime-created fields require instrumentation.</div><details><summary>All ${a.file_count} architecture sources</summary><div class="source-grid">${a.files.map(f=>`<div class="source-row"><b>${esc(f.path)}</b><br>${f.lines} lines · ${f.sha256.slice(0,14)}…</div>`).join('')}</div></details><details><summary>Protocol and generated evidence</summary><p>Generated beside this page: <code>architecture-map-protocol.md</code> · <code>architecture-map-ledger.json</code> · <code>architecture-map-model.json</code></p><p>${esc(D.model.project.interpretation)}</p></details>`;}
setup();})();
</script>
</body></html>'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--architecture-read-count", type=int, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    classes = assign_memberships(model, ledger)
    errors = validate(model, ledger, classes, args.architecture_read_count)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if args.strict:
            return 1
    variable_total = sum(len(record["variables"]) for record in classes)
    data = {
        "model": model,
        "ledger": {
            "inventory_sha256": ledger["inventory_sha256"],
            "architecture": ledger["architecture"],
            "source_scan": {
                key: value
                for key, value in ledger["source_scan"].items()
                if key != "classes"
            },
        },
        "classes": classes,
        "coverage": {
            "architecture_total": ledger["architecture"]["file_count"],
            "architecture_read": args.architecture_read_count,
            "class_total": len(classes),
            "variable_total": variable_total,
            "unmapped_classes": sum(not record["memberships"] for record in classes),
            "component_total": len(model["components"]),
            "subsystem_total": len(model["subsystems"]),
            "edge_total": len(model.get("system_edges", []))
            + len(model.get("subsystem_edges", []))
            + len(model.get("component_edges", [])),
            "classes_by_category": ledger["source_scan"]["classes_by_category"],
            "validation_errors": errors,
        },
    }
    print(
        json.dumps(
            {
                "architecture": f"{data['coverage']['architecture_read']}/{data['coverage']['architecture_total']}",
                "classes": data["coverage"]["class_total"],
                "variables": data["coverage"]["variable_total"],
                "unmapped": data["coverage"]["unmapped_classes"],
                "components": data["coverage"]["component_total"],
                "subsystems": data["coverage"]["subsystem_total"],
                "edges": data["coverage"]["edge_total"],
                "errors": errors,
            },
            indent=2,
        )
    )
    if args.validate_only:
        return 0 if not errors else 1
    if not args.output:
        print("ERROR: --output is required unless --validate-only is used", file=sys.stderr)
        return 2
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    rendered = HTML.replace("__TITLE__", model["project"]["title"]).replace("__DATA__", payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
