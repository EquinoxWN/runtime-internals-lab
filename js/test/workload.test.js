import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Vec, VectorChurn, MAX_OPS, MAX_WINDOW } from "../src/workload.js";
import { XorShift32 } from "../src/xorshift.js";

/** @type {{ xorshift32: { seed: number, first: number[] }[],
 *   checksums: { ops: number, window: number, seed: number, checksum: number }[] }} */
const spec = JSON.parse(readFileSync(new URL("../../spec/workload.json", import.meta.url), "utf8"));

test("xorshift32 matches the shared reference sequences", () => {
  for (const { seed, first } of spec.xorshift32) {
    const rng = new XorShift32(seed);
    assert.deepEqual(
      first.map(() => rng.next()),
      first,
    );
  }
});

test("xorshift32 rejects seeds outside [1, 2**32 - 1]", () => {
  for (const bad of [0, -1, 2 ** 32, 1.5, Number.NaN]) {
    assert.throws(() => new XorShift32(bad), RangeError);
  }
});

test("every shared checksum matches", () => {
  for (const c of spec.checksums) {
    assert.equal(new VectorChurn(c.window).run(c.ops, c.seed), c.checksum, JSON.stringify(c));
  }
});

test("the ring is emptied at the start of every round", () => {
  const churn = new VectorChurn(64);
  const first = churn.run(1_000, 7);
  churn.run(500, 99);
  assert.equal(churn.run(1_000, 7), first);
});

test("retained objects change the checksum only once the ring wraps", () => {
  assert.equal(new VectorChurn(100).run(100, 5), new VectorChurn(0).run(100, 5));
  assert.notEqual(new VectorChurn(100).run(101, 5), new VectorChurn(0).run(101, 5));
});

test("checksums stay unsigned 32-bit integers for random inputs", () => {
  let state = 12345;
  for (let t = 0; t < 50; t++) {
    state = (state * 1103515245 + 12345) % 2 ** 31;
    const window = state % 50;
    const ops = 1 + (state % 5_000);
    const sum = new VectorChurn(window).run(ops, 1 + (state % 2_000_000_000));
    assert.ok(Number.isInteger(sum) && sum >= 0 && sum < 2 ** 32, String(sum));
  }
});

test("out-of-range arguments are rejected", () => {
  assert.throws(() => new VectorChurn(-1), RangeError);
  assert.throws(() => new VectorChurn(MAX_WINDOW + 1), RangeError);
  const churn = new VectorChurn(0);
  assert.throws(() => churn.run(0, 1), RangeError);
  assert.throws(() => churn.run(MAX_OPS + 1, 1), RangeError);
  assert.throws(() => churn.run(10, 0), RangeError);
});

test("Vec operations return new objects", () => {
  const a = new Vec(1, 2);
  const b = a.add(new Vec(3, 4));
  assert.deepEqual([b.x, b.y], [4, 6]);
  const c = b.scale(3);
  assert.deepEqual([c.x, c.y], [12, 18]);
  assert.deepEqual([a.x, a.y], [1, 2]);
  assert.notEqual(c, b);
});
