// Mirror of dagwood/live/protocol.py. Keep the two in sync.

export type Status = 'todo' | 'doing' | 'done';

export interface NodeData {
  id: string;
  title: string;
  status: Status;
  notes: string;
  needs: string[];
  created: string | null;
  updated: string | null;
}

export interface Derived {
  frontier: string[];
  blocked: string[];
}

export interface Snapshot {
  type: 'snapshot';
  nodes: NodeData[];
  meta: Record<string, string>;
  derived: Derived;
}

export interface Patch {
  type: 'patch';
  added: NodeData[];
  updated: NodeData[];
  removed: string[];
  derived: Derived;
  op_id?: string;
}

export interface ErrorMsg {
  type: 'error';
  code: string;
  message: string;
  op_id?: string;
}

export interface StatusMsg {
  type: 'status';
  parse_ok: boolean;
  source: string;
}

export type ServerMessage = Snapshot | Patch | ErrorMsg | StatusMsg;
