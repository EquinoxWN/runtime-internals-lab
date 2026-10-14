import test from "node:test";
import assert from "node:assert/strict";
import { KERNELS, probe } from "../src/escape-probe.js";

test("the three probe kernels compute the same result for random seeds", () => {
  let state = 7;
  for (let t = 0; t < 100; t++) {
    state = (state * 1103515245 + 12345) % 2 ** 31;
    const ops = 1 + (state % 3_000);
    const seed = 1 + (state % 2_000_000_000);
    const expected = KERNELS.none(ops, seed);
    assert.equal(KERNELS.methods(ops, seed), expected);
    assert.equal(KERNELS.inline(ops, seed), expected);
  }
});

test("the probe prints one agreeing JSON line per kernel", () => {
  /** @type {string[]} */
  const out = [];
  assert.equal(
    probe(["--ops", "2000", "--warmup", "1", "--rounds", "1"], (l) => out.push(l), () => {}),
    0,
  );
  const lines = out.map((l) => JSON.parse(l));
  assert.deepEqual(
    lines.map((l) => l.kernel),
    ["methods", "inline", "none"],
  );
  for (const line of lines) {
    assert.equal(line.experiment, "v8-escape");
    assert.equal(line.agrees, true);
    assert.equal(typeof line.alloc_bytes_per_op, "number");
  }
});

test("probe arguments are validated", () => {
  /** @type {string[]} */
  const err = [];
  assert.equal(
    probe(["--ops", "0"], () => {}, (l) => err.push(l)),
    2,
  );
  assert.equal(
    probe(["--rounds", "-3"], () => {}, (l) => err.push(l)),
    2,
  );
  assert.match(err.join("\n"), /error: --ops must be in/);
});
