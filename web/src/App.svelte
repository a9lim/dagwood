<script lang="ts">
  import { Background, Controls, MiniMap, Panel, SvelteFlow, type Edge, type Node } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';

  import TaskNode from './components/TaskNode.svelte';
  import { layoutGraph } from './lib/layout';
  import { GraphState } from './lib/ws.svelte';

  const g = new GraphState();
  g.connect(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);

  let nodes = $state.raw<Node[]>([]);
  let edges = $state.raw<Edge[]>([]);
  const nodeTypes = { task: TaskNode };

  // Re-layout whenever the graph changes. ELK is deterministic, so status-only
  // updates keep positions stable; the async token drops stale layout results.
  let token = 0;
  $effect(() => {
    const data = g.nodes();
    const eds = g.edges();
    const frontier = new Set(g.frontier);
    const blocked = new Set(g.blocked);
    const mine = ++token;
    void layoutGraph(
      data.map((n) => n.id),
      eds,
    ).then((pos) => {
      if (mine !== token) return;
      nodes = data.map((n) => ({
        id: n.id,
        type: 'task',
        position: pos[n.id] ?? { x: 0, y: 0 },
        data: {
          title: n.title,
          status: n.status,
          ready: frontier.has(n.id),
          blocked: blocked.has(n.id),
        },
      }));
      edges = eds.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: frontier.has(e.target),
      }));
    });
  });

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

<div class="wrap">
  <SvelteFlow bind:nodes bind:edges {nodeTypes} fitView nodesDraggable={false} nodesConnectable={false}>
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
  </SvelteFlow>
</div>

<style>
  .wrap {
    width: 100%;
    height: 100%;
  }
  .hud {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    background: rgba(255, 255, 255, 0.9);
    padding: 0.4rem 0.7rem;
    border-radius: 0.5rem;
    font-size: 0.85rem;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
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
</style>
