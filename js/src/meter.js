import v8 from "node:v8";

/**
 * @typedef {{ count: number, time_ms: number }} CollectorTotals
 * @typedef {{ wallNs: number, allocBytes: number, gcCount: number, gcTimeMs: number,
 *   collectors: Record<string, CollectorTotals> }} Measurement
 */

/**
 * Measure a function with V8's GCProfiler: wall time, every GC with its cost, and the bytes
 * allocated, derived from the used heap size before and after each collection.
 * @param {() => void} fn
 * @returns {Measurement}
 */
export function measure(fn) {
  const profiler = new v8.GCProfiler();
  profiler.start();
  const usedBefore = v8.getHeapStatistics().used_heap_size;
  const start = process.hrtime.bigint();
  fn();
  const wallNs = Number(process.hrtime.bigint() - start);
  const usedAfter = v8.getHeapStatistics().used_heap_size;
  const report = profiler.stop();
  /** @type {Record<string, CollectorTotals>} */
  const collectors = {};
  let allocBytes = 0;
  let previous = usedBefore;
  let gcTimeUs = 0;
  const statistics = report?.statistics ?? [];
  for (const gc of statistics) {
    allocBytes += gc.beforeGC.heapStatistics.usedHeapSize - previous;
    previous = gc.afterGC.heapStatistics.usedHeapSize;
    gcTimeUs += gc.cost;
    const totals = (collectors[gc.gcType] ??= { count: 0, time_ms: 0 });
    totals.count += 1;
    totals.time_ms += gc.cost / 1000;
  }
  allocBytes += usedAfter - previous;
  return { wallNs, allocBytes, gcCount: statistics.length, gcTimeMs: gcTimeUs / 1000, collectors };
}

/**
 * Runtime facts recorded with every result: Node and V8 versions and the flags in effect.
 * @returns {{ runtime: string, version: string, vm: string, flags: string[], max_heap_bytes: number }}
 */
export function runtimeInfo() {
  return {
    runtime: "node",
    version: process.version,
    vm: `V8 ${process.versions.v8}`,
    flags: [...process.execArgv],
    max_heap_bytes: v8.getHeapStatistics().heap_size_limit,
  };
}
