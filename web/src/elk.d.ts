// elkjs ships the bundled entry without bundler-friendly types for this path.
declare module 'elkjs/lib/elk.bundled.js' {
  export interface ElkLayoutNode {
    id: string;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    children?: ElkLayoutNode[];
  }
  export interface ElkResult {
    children?: ElkLayoutNode[];
  }
  export default class ELK {
    constructor(options?: unknown);
    layout(graph: unknown): Promise<ElkResult>;
  }
}
