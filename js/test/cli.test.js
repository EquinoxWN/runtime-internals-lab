import test from "node:test";
import assert from "node:assert/strict";
import { main, same } from "../src/cli.js";
import { measure } from "../src/meter.js";

/**
 * Run the CLI in-process and collect what it prints.
 * @param {string[]} argv
 */
function run(argv) {
  /** @type {string[]} */
  const out = [];
  /** @type {string[]} */
  const err = [];
  const code = main(argv, (l) => out.push(l), (l) => err.push(l));
  return { code, out, err };
}

test("churn prints one JSON result line with the shared checksum", () => {
  const { code, out } = run(["--ops", "1000", "--window", "10", "--seed", "42", "--warmup", "1", "--rounds", "2"]);
  assert.equal(code, 0);
  assert.equal(out.length, 1);
  const line = JSON.parse(out[0] ?? "");
  assert.equal(line.runtime, "node");
  assert.equal(line.workload, "vector-churn");
  assert.equal(line.checksum, 1706363773);
  assert.equal(line.rounds, 2);
  assert.ok(line.alloc_bytes_per_op > 0);
  assert.ok(Array.isArray(line.flags));
  assert.equal(typeof line.collectors, "object");
});

test("the largest seed and zero warm-up rounds are accepted", () => {
  const { code, out } = run(["--ops", "1000", "--window", "100", "--seed", "4294967295", "--warmup", "0"]);
  assert.equal(code, 0);
  const line = JSON.parse(out[0] ?? "");
  assert.equal(line.checksum, 166371539);
  assert.equal(line.seed, 4294967295);
});

test("bad arguments exit with 2 and say why", () => {
  for (const argv of [["--ops", "0"], ["--seed", "0"], ["--window", "1000001"], ["--ops", "1e3"], ["--nope", "1"], ["x"]]) {
    const { code, out, err } = run(argv);
    assert.equal(code, 2, argv.join(" "));
    assert.equal(out.length, 0);
    assert.match(err[0] ?? "", /^error: /);
  }
});

test("rounds that disagree are reported", () => {
  assert.equal(same(-1, 5), 5);
  assert.equal(same(5, 5), 5);
  assert.throws(() => same(5, 6), /checksum changed/);
});

test("the meter counts allocated bytes and garbage collections", () => {
  /** @type {unknown[]} */
  let keep = [];
  const m = measure(() => {
    for (let i = 0; i < 400_000; i++) keep.push({ i });
    keep = [];
  });
  assert.ok(m.allocBytes > 400_000 * 12, `allocated ${m.allocBytes}`);
  assert.ok(m.gcCount >= 1, `gc count ${m.gcCount}`);
  assert.ok(m.wallNs > 0);
});
