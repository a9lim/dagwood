<script lang="ts">
  import { SvelteFlowProvider } from '@xyflow/svelte';

  import Flow from './Flow.svelte';
</script>

<!-- The provider lets Flow call useSvelteFlow() (for screenToFlowPosition). -->
<SvelteFlowProvider>
  <Flow />
</SvelteFlowProvider>
