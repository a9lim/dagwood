import type { FlowEdge } from './layout';
import type { NodeData, ServerMessage } from './protocol';

// Reactive client mirror of the server's graph. Applies snapshot/patch messages
// from the websocket; the canvas derives Svelte Flow nodes/edges from this.
export class GraphState {
  nodesById = $state.raw<Record<string, NodeData>>({});
  order = $state.raw<string[]>([]);
  meta = $state.raw<Record<string, string>>({});
  frontier = $state.raw<string[]>([]);
  blocked = $state.raw<string[]>([]);
  connected = $state(false);
  parseOk = $state(true);
  lastError = $state<string | null>(null);

  #ws: WebSocket | undefined;

  connect(url: string): void {
    const ws = new WebSocket(url);
    this.#ws = ws;
    ws.addEventListener('open', () => {
      this.connected = true;
    });
    ws.addEventListener('close', () => {
      this.connected = false;
      setTimeout(() => this.connect(url), 1000);
    });
    ws.addEventListener('message', (ev) => {
      this.#handle(JSON.parse(ev.data as string) as ServerMessage);
    });
  }

  #handle(msg: ServerMessage): void {
    if (msg.type === 'snapshot') {
      const by: Record<string, NodeData> = {};
      for (const n of msg.nodes) by[n.id] = n;
      this.nodesById = by;
      this.order = msg.nodes.map((n) => n.id);
      this.meta = msg.meta;
      this.frontier = msg.derived.frontier;
      this.blocked = msg.derived.blocked;
      this.parseOk = true;
    } else if (msg.type === 'patch') {
      const by = { ...this.nodesById };
      let order = this.order.slice();
      for (const id of msg.removed) {
        delete by[id];
        order = order.filter((x) => x !== id);
      }
      for (const n of msg.updated) by[n.id] = n;
      for (const n of msg.added) {
        by[n.id] = n;
        if (!order.includes(n.id)) order.push(n.id);
      }
      this.nodesById = by;
      this.order = order;
      this.frontier = msg.derived.frontier;
      this.blocked = msg.derived.blocked;
    } else if (msg.type === 'status') {
      this.parseOk = msg.parse_ok;
    } else if (msg.type === 'error') {
      this.lastError = msg.message;
    }
  }

  nodes(): NodeData[] {
    return this.order.map((id) => this.nodesById[id]).filter((n): n is NodeData => Boolean(n));
  }

  edges(): FlowEdge[] {
    const out: FlowEdge[] = [];
    for (const n of this.nodes()) {
      for (const dep of n.needs) {
        if (this.nodesById[dep]) out.push({ id: `${dep}->${n.id}`, source: dep, target: n.id });
      }
    }
    return out;
  }
}
