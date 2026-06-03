<script lang="ts">
  import { untrack } from 'svelte';

  import type { NodeData, Status } from '../lib/protocol';

  let {
    node,
    onTitle,
    onNotes,
    onStatus,
    onClose,
    onDeleteNode,
  }: {
    node: NodeData;
    onTitle: (v: string) => void;
    onNotes: (v: string) => void;
    onStatus: (s: Status) => void;
    onClose: () => void;
    onDeleteNode: () => void;
  } = $props();

  // Local editable copies; resync only when the selected node *identity* changes,
  // so a live server update to this node doesn't clobber an in-progress edit.
  let title = $state(untrack(() => node.title));
  let notes = $state(untrack(() => node.notes));
  let lastId = $state(untrack(() => node.id));
  $effect(() => {
    if (node.id !== lastId) {
      lastId = node.id;
      title = node.title;
      notes = node.notes;
    }
  });
</script>

<aside class="inspector">
  <header>
    <strong>{node.id}</strong>
    <button class="x" onclick={onClose} aria-label="close">×</button>
  </header>

  <label>
    Title
    <input value={title} oninput={(e) => (title = e.currentTarget.value)} onblur={() => onTitle(title)} />
  </label>

  <label>
    Status
    <select value={node.status} onchange={(e) => onStatus(e.currentTarget.value as Status)}>
      <option value="todo">todo</option>
      <option value="doing">doing</option>
      <option value="done">done</option>
    </select>
  </label>

  <label>
    Notes
    <textarea
      rows="6"
      value={notes}
      oninput={(e) => (notes = e.currentTarget.value)}
      onblur={() => onNotes(notes)}
    ></textarea>
  </label>

  {#if node.needs.length > 0}
    <div class="needs">depends on: {node.needs.join(', ')}</div>
  {/if}

  <button class="danger" onclick={onDeleteNode}>Delete task</button>
</aside>

<style>
  .inspector {
    position: absolute;
    top: 0;
    right: 0;
    width: 280px;
    height: 100%;
    background: #fff;
    border-left: 1px solid #e2e8f0;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.08);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    z-index: 5;
    overflow-y: auto;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  header strong {
    font-family: ui-monospace, monospace;
    color: #475569;
  }
  .x {
    border: none;
    background: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: #94a3b8;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  input,
  select,
  textarea {
    font: inherit;
    text-transform: none;
    letter-spacing: normal;
    color: #0f172a;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.4rem;
  }
  textarea {
    resize: vertical;
  }
  .needs {
    font-size: 0.75rem;
    color: #64748b;
  }
  .danger {
    margin-top: auto;
    border: 1px solid #fca5a5;
    background: #fef2f2;
    color: #dc2626;
    padding: 0.45rem;
    border-radius: 0.4rem;
    cursor: pointer;
  }
  .danger:hover {
    background: #fee2e2;
  }
</style>
