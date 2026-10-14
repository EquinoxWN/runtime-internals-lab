// V8 escape-analysis probe: the same arithmetic with Vec methods, inline constructors, or no objects.
// usage: node src/escape-probe.js --ops N --warmup K --rounds R   (one JSON line per kernel)
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";
import { measure, runtimeInfo } from "./meter.js";
import { Vec } from "./workload.js";
import { XorShift32 } from "./xorshift.js";

/**
 * Four temporaries per operation built through add() and scale(), as in the shared workload.
 * @param {number} ops
 * @param {number} seed
 * @returns {number}
 */
export function methods(ops, seed) {
  const rng = new XorShift32(seed);
  let acc = 0;
  for (let i = 0; i < ops; i++) {
    const r = rng.next();
    const c = new Vec(r & 0xffff, r >>> 16).add(new Vec(r >>> 16, r & 0xffff)).scale(3);
    acc += c.x + c.y;
  }
  return acc;
}

/**
 * The same four temporaries, built with constructors in the loop body (no method calls).
 * @param {number} ops
 * @param {number} seed
 * @returns {number}
 */
export function inline(ops, seed) {
  const rng = new XorShift32(seed);
  let acc = 0;
  for (let i = 0; i < ops; i++) {
    const r = rng.next();
    const a = new Vec(r & 0xffff, r >>> 16);
    const b = new Vec(r >>> 16, r & 0xffff);
    const sum = new Vec(a.x + b.x, a.y + b.y);
    const c = new Vec(sum.x * 3, sum.y * 3);
    acc += c.x + c.y;
  }
  return acc;
}

/**
 * The same arithmetic with no objects at all: the floor for allocation.
 * @param {number} ops
 * @param {number} seed
 * @returns {number}
 */
export function none(ops, seed) {
  const rng = new XorShift32(seed);
  let acc = 0;
  for (let i = 0; i < ops; i++) {
    const r = rng.next();
    acc += 6 * ((r & 0xffff) + (r >>> 16));
  }
  return acc;
}

export const KERNELS = { methods, inline, none };

/**
 * Parse an option as an integer in [lo, hi].
 * @param {string | undefined} raw
 * @param {string} name
 * @param {number} def
 * @param {number} lo
 * @param {number} hi
 * @returns {number}
 */
function bounded(raw, name, def, lo, hi) {
  if (raw === undefined) return def;
  if (!/^\d{1,12}$/.test(raw)) throw new RangeError(`--${name} must be a non-negative integer`);
  const value = Number(raw);
  if (value < lo || value > hi) throw new RangeError(`--${name} must be in [${lo}, ${hi}]`);
  return value;
}

/**
 * Measure every kernel and print one JSON line each; returns the exit code.
 * @param {string[]} argv
 * @param {(line: string) => void} out
 * @param {(line: string) => void} err
 * @returns {number}
 */
export function probe(argv, out, err) {
  let ops, warmup, rounds;
  try {
    const { values } = parseArgs({
      args: argv,
      strict: true,
      allowPositionals: false,
      options: { ops: { type: "string" }, warmup: { type: "string" }, rounds: { type: "string" } },
    });
    ops = bounded(values.ops, "ops", 1_000_000, 1, 100_000_000);
    warmup = bounded(values.warmup, "warmup", 20, 0, 1_000);
    rounds = bounded(values.rounds, "rounds", 10, 1, 1_000);
  } catch (e) {
    err(`error: ${e instanceof Error ? e.message : String(e)}`);
    return 2;
  }
  let expected = -1;
  for (const [name, kernel] of Object.entries(KERNELS)) {
    let result = 0;
    for (let i = 0; i < warmup; i++) result = kernel(ops, 42);
    const m = measure(() => {
      for (let i = 0; i < rounds; i++) result = kernel(ops, 42);
    });
    const agrees = expected === -1 || expected === result;
    if (expected === -1) expected = result;
    const total = ops * rounds;
    out(
      JSON.stringify({
        ...runtimeInfo(),
        experiment: "v8-escape",
        kernel: name,
        ops,
        rounds,
        result,
        agrees,
        ns_per_op: m.wallNs / total,
        alloc_bytes_per_op: m.allocBytes / total,
        gc_count: m.gcCount,
      }),
    );
    if (!agrees) return 1;
  }
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exitCode = probe(
    process.argv.slice(2),
    (line) => console.log(line),
    (line) => console.error(line),
  );
}
