<script lang="ts">
  import {
    Background,
    Controls,
    MiniMap,
    Panel,
    SvelteFlow,
    useSvelteFlow,
    type Connection,
    type Edge,
    type Node,
  } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { untrack } from 'svelte';

  import Inspector from './components/Inspector.svelte';
  import TaskNode from './components/TaskNode.svelte';
  import { layoutGraph, type Pos } from './lib/layout';
  import type { Status } from './lib/protocol';
  import { GraphState } from './lib/ws.svelte';

  const g = new GraphState();
  g.connect(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);

  const { screenToFlowPosition } = useSvelteFlow();

  let nodes = $state.raw<Node[]>([]);
  let edges = $state.raw<Edge[]>([]);
  const nodeTypes = { task: TaskNode };

  let overrides = $state<Record<string, Pos>>({});
  let relayoutNonce = $state(0);
  let selectedId = $state<string | null>(null);
  let toast = $state<string | null>(null);

  let opCounter = 0;
  const pendingPos = new Map<string, Pos>();

  // Load persisted geometry from the sidecar.
  fetch('/api/layout')
    .then((r) => r.json())
    .then((d: { overrides?: Record<string, Pos> }) => {
      overrides = d.overrides ?? {};
    })
    .catch(() => {});

  g.onmessage = (msg) => {
    if (msg.type === 'patch' && msg.op_id && pendingPos.has(msg.op_id)) {
      const pos = pendingPos.get(msg.op_id)!;
      pendingPos.delete(msg.op_id);
      for (const n of msg.added) {
        overrides = { ...overrides, [n.id]: pos };
        g.send({ type: 'set_layout', id: n.id, x: pos.x, y: pos.y });
      }
    } else if (msg.type === 'error') {
      showToast(msg.message);
    }
  };

  function showToast(m: string): void {
    toast = m;
    setTimeout(() => {
      if (toast === m) toast = null;
    }, 4000);
  }

  // Rebuild flow nodes/edges whenever the server graph changes. ELK is
  // deterministic and manual positions (overrides) win on top, so status
  // changes don't move anything and dragged nodes stay put. `overrides` is
  // read untracked so a drag doesn't re-trigger a layout.
  let token = 0;
  $effect(() => {
    const data = g.nodes();
    const eds = g.edges();
    const frontier = new Set(g.frontier);
    const blocked = new Set(g.blocked);
    void relayoutNonce; // tracked: lets "Re-layout" force a rebuild
    const ov = untrack(() => overrides);
    const mine = ++token;
    void layoutGraph(
      data.map((n) => n.id),
      eds,
    ).then((pos) => {
      if (mine !== token) return;
      nodes = data.map((n) => ({
        id: n.id,
        type: 'task',
        position: ov[n.id] ?? pos[n.id] ?? { x: 0, y: 0 },
        data: { title: n.title, status: n.status, ready: frontier.has(n.id), blocked: blocked.has(n.id) },
      }));
      edges = eds.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: frontier.has(e.target),
      }));
    });
  });

  // --- editing handlers (all go through the server, which is the sole writer) ---
  function onconnect(c: Connection): void {
    // edge source -> target: target depends on source (dst.needs += src)
    g.send({ type: 'add_edge', src: c.source, dst: c.target, op_id: `edge-${++opCounter}` });
  }

  function ondelete(p: { nodes: Node[]; edges: Edge[] }): void {
    for (const e of p.edges) g.send({ type: 'remove_edge', src: e.source, dst: e.target });
    for (const n of p.nodes) {
      g.send({ type: 'remove_node', id: n.id });
      if (selectedId === n.id) selectedId = null;
    }
  }

  function onnodedragstop({ nodes: dragged }: { nodes: Node[] }): void {
    let next = overrides;
    for (const n of dragged) {
      next = { ...next, [n.id]: { x: n.position.x, y: n.position.y } };
      g.send({ type: 'set_layout', id: n.id, x: n.position.x, y: n.position.y });
    }
    overrides = next;
  }

  function onnodeclick({ node }: { node: Node }): void {
    selectedId = node.id;
  }

  function onpaneclick(): void {
    selectedId = null;
  }

  function addTask(pos?: Pos): void {
    const op = `add-${++opCounter}`;
    if (pos) pendingPos.set(op, pos);
    g.send({ type: 'add_node', title: 'new task', op_id: op });
  }

  function onPaneDblClick(e: MouseEvent): void {
    const target = e.target as HTMLElement;
    if (!target.closest('.svelte-flow__pane')) return; // only the empty canvas
    addTask(screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  }

  function reLayout(): void {
    overrides = {};
    void fetch('/api/layout', {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ overrides: {} }),
    });
    relayoutNonce++;
  }

  // inspector callbacks (capture current selection safely)
  function editTitle(v: string): void {
    if (selectedId) g.send({ type: 'set_fields', id: selectedId, title: v });
  }
  function editNotes(v: string): void {
    if (selectedId) g.send({ type: 'set_fields', id: selectedId, notes: v });
  }
  function editStatus(s: Status): void {
    if (selectedId) g.send({ type: 'set_status', id: selectedId, status: s });
  }
  function deleteSelected(): void {
    if (selectedId) {
      g.send({ type: 'remove_node', id: selectedId });
      selectedId = null;
    }
  }

  const selected = $derived(selectedId ? (g.nodesById[selectedId] ?? null) : null);
  const counts = $derived.by(() => {
    const ns = g.nodes();
    return {
      total: ns.length,
      ready: g.frontier.length,
      blocked: g.blocked.length,
      done: ns.filter((n) => n.status === 'done').length,
    };
  });
</script>

<div class="wrap" ondblclick={onPaneDblClick} role="application">
  <SvelteFlow
    bind:nodes
    bind:edges
    {nodeTypes}
    fitView
    zoomOnDoubleClick={false}
    {onconnect}
    {ondelete}
    {onnodedragstop}
    {onnodeclick}
    {onpaneclick}
  >
    <Background />
    <Controls />
    <MiniMap />
    <Panel position="top-left">
      <div class="hud">
        <strong>dagwood</strong>
        <span class={g.connected ? 'ok' : 'bad'}>{g.connected ? '● live' : '○ offline'}</span>
        <span class="muted">
          {counts.total} tasks · {counts.ready} ready · {counts.blocked} blocked · {counts.done} done
        </span>
        {#if !g.parseOk}<span class="bad">file unparseable</span>{/if}
      </div>
    </Panel>
    <Panel position="top-right">
      <div class="toolbar">
        <button onclick={() => addTask()}>+ Add task</button>
        <button onclick={reLayout}>Re-layout</button>
      </div>
    </Panel>
  </SvelteFlow>

  {#if selected}
    <Inspector
      node={selected}
      onTitle={editTitle}
      onNotes={editNotes}
      onStatus={editStatus}
      onClose={() => (selectedId = null)}
      onDeleteNode={deleteSelected}
    />
  {/if}

  {#if toast}
    <div class="toast">{toast}</div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    width: 100%;
    height: 100%;
  }
  .hud,
  .toolbar {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    background: rgba(255, 255, 255, 0.92);
    padding: 0.4rem 0.6rem;
    border-radius: 0.5rem;
    font-size: 0.85rem;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  }
  .toolbar button {
    cursor: pointer;
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 0.4rem;
    padding: 0.25rem 0.6rem;
    font-size: 0.8rem;
  }
  .toolbar button:hover {
    background: #f1f5f9;
  }
  .muted {
    color: #475569;
  }
  .ok {
    color: #16a34a;
  }
  .bad {
    color: #dc2626;
  }
  .toast {
    position: absolute;
    bottom: 1rem;
    left: 50%;
    transform: translateX(-50%);
    background: #dc2626;
    color: #fff;
    padding: 0.5rem 0.9rem;
    border-radius: 0.5rem;
    font-size: 0.85rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    z-index: 10;
  }
</style>
