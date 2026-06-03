<script lang="ts">
  import { Handle, Position, type NodeProps } from '@xyflow/svelte';

  import type { Status } from '../lib/protocol';

  interface TaskData {
    title: string;
    status: Status;
    ready: boolean;
    blocked: boolean;
  }

  let { data }: NodeProps = $props();
  const d = $derived(data as unknown as TaskData);
  const tone = $derived(
    d.status === 'done' ? 'done' : d.ready ? 'ready' : d.blocked ? 'blocked' : d.status,
  );
</script>

<div class="task {tone}">
  <Handle type="target" position={Position.Top} />
  <div class="title">{d.title}</div>
  <div class="meta">
    {d.status}{d.ready ? ' · ready' : ''}{d.blocked ? ' · blocked' : ''}
  </div>
  <Handle type="source" position={Position.Bottom} />
</div>

<style>
  .task {
    width: 190px;
    min-height: 66px;
    padding: 0.5rem 0.7rem;
    border-radius: 0.6rem;
    border: 2px solid #cbd5e1;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  }
  .title {
    font-weight: 600;
    font-size: 0.9rem;
    line-height: 1.25;
    color: #0f172a;
  }
  .meta {
    margin-top: 0.3rem;
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .task.ready {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
  }
  .task.blocked {
    border-color: #e2e8f0;
    background: #f8fafc;
    opacity: 0.78;
  }
  .task.done {
    border-color: #16a34a;
    background: #f0fdf4;
  }
  .task.doing {
    border-color: #f59e0b;
  }
</style>
