import ELK from 'elkjs/lib/elk.bundled.js';

const elk = new ELK();

export const NODE_W = 190;
export const NODE_H = 66;

export interface Pos {
  x: number;
  y: number;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
}

// ELK layered, top-down — the natural layout for a dependency DAG. Deterministic
// for a given node/edge set, so status-only changes don't move anything.
export async function layoutGraph(nodeIds: string[], edges: FlowEdge[]): Promise<Record<string, Pos>> {
  if (nodeIds.length === 0) return {};
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.layered.spacing.nodeNodeBetweenLayers': '90',
      'elk.spacing.nodeNode': '45',
    },
    children: nodeIds.map((id) => ({ id, width: NODE_W, height: NODE_H })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };
  const res = await elk.layout(graph);
  const pos: Record<string, Pos> = {};
  for (const c of res.children ?? []) pos[c.id] = { x: c.x ?? 0, y: c.y ?? 0 };
  return pos;
}
