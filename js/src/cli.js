import { parseArgs } from "node:util";
import { measure, runtimeInfo } from "./meter.js";
import { MAX_OPS, MAX_WINDOW, VectorChurn } from "./workload.js";

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
  if (!/^-?\d{1,12}$/.test(raw)) throw new RangeError(`--${name} must be an integer`);
  const value = Number(raw);
  if (value < lo || value > hi) throw new RangeError(`--${name} must be in [${lo}, ${hi}]`);
  return value;
}

/**
 * Every round from the same seed must give the same checksum (-1 = none yet).
 * @param {number} previous
 * @param {number} actual
 * @returns {number}
 */
export function same(previous, actual) {
  if (previous !== -1 && previous !== actual) {
    throw new Error(`checksum changed between rounds: ${previous} vs ${actual}`);
  }
  return actual;
}

/**
 * Run the workload with command-line options and print one JSON result line; returns the exit code.
 * @param {string[]} argv
 * @param {(line: string) => void} out
 * @param {(line: string) => void} err
 * @returns {number}
 */
export function main(argv, out, err) {
  let ops, window, seed, warmup, rounds;
  try {
    const { values } = parseArgs({
      args: argv,
      strict: true,
      allowPositionals: false,
      options: {
        ops: { type: "string" },
        window: { type: "string" },
        seed: { type: "string" },
        warmup: { type: "string" },
        rounds: { type: "string" },
      },
    });
    ops = bounded(values.ops, "ops", 1_000_000, 1, MAX_OPS);
    window = bounded(values.window, "window", 0, 0, MAX_WINDOW);
    seed = bounded(values.seed, "seed", 42, 1, 0xffffffff);
    warmup = bounded(values.warmup, "warmup", 20, 0, 1_000);
    rounds = bounded(values.rounds, "rounds", 20, 1, 1_000);
  } catch (e) {
    err(`error: ${e instanceof Error ? e.message : String(e)}`);
    return 2;
  }
  const churn = new VectorChurn(window);
  let checksum = -1;
  for (let i = 0; i < warmup; i++) checksum = same(checksum, churn.run(ops, seed));
  const m = measure(() => {
    for (let i = 0; i < rounds; i++) checksum = same(checksum, churn.run(ops, seed));
  });
  const total = ops * rounds;
  out(
    JSON.stringify({
      ...runtimeInfo(),
      workload: "vector-churn",
      ops,
      window,
      seed,
      warmup,
      rounds,
      checksum,
      wall_ns: m.wallNs,
      ns_per_op: m.wallNs / total,
      alloc_bytes: m.allocBytes,
      alloc_bytes_per_op: m.allocBytes / total,
      gc_count: m.gcCount,
      gc_time_ms: m.gcTimeMs,
      collectors: m.collectors,
    }),
  );
  return 0;
}
