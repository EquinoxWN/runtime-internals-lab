import { XorShift32 } from "./xorshift.js";

export const MAX_OPS = 100_000_000;
export const MAX_WINDOW = 1_000_000;
const TWO_32 = 4294967296;

/** An immutable 2D integer vector: the small, short-lived object the workload allocates. */
export class Vec {
  /**
   * Store the two components.
   * @param {number} x
   * @param {number} y
   */
  constructor(x, y) {
    /** @readonly */
    this.x = x;
    /** @readonly */
    this.y = y;
  }

  /**
   * Component-wise sum, as a new object.
   * @param {Vec} o
   * @returns {Vec}
   */
  add(o) {
    return new Vec(this.x + o.x, this.y + o.y);
  }

  /**
   * Both components times k, as a new object.
   * @param {number} k
   * @returns {Vec}
   */
  scale(k) {
    return new Vec(this.x * k, this.y * k);
  }
}

/** The shared vector-churn workload (spec/workload.md): four Vec allocations per operation. */
export class VectorChurn {
  /** @type {(Vec | null)[]} */
  #ring;

  /**
   * Create the workload with a ring of `window` slots (0 = nothing retained).
   * @param {number} window
   */
  constructor(window) {
    if (!Number.isInteger(window) || window < 0 || window > MAX_WINDOW) {
      throw new RangeError(`window must be an integer in [0, ${MAX_WINDOW}]`);
    }
    this.window = window;
    this.#ring = new Array(window).fill(null);
  }

  /**
   * Run one round of `ops` operations from `seed`; return the 32-bit checksum.
   * @param {number} ops
   * @param {number} seed
   * @returns {number}
   */
  run(ops, seed) {
    if (!Number.isInteger(ops) || ops < 1 || ops > MAX_OPS) {
      throw new RangeError(`ops must be an integer in [1, ${MAX_OPS}]`);
    }
    const window = this.window;
    const ring = this.#ring;
    ring.fill(null);
    const rng = new XorShift32(seed);
    let checksum = 0;
    let slot = 0;
    for (let i = 0; i < ops; i++) {
      const r = rng.next();
      const a = new Vec(r & 0xffff, r >>> 16);
      const b = new Vec(r >>> 16, r & 0xffff);
      const c = a.add(b).scale(3);
      if (window > 0) {
        const old = ring[slot];
        if (old != null) {
          checksum = (checksum + old.x) % TWO_32;
        }
        ring[slot] = c;
        slot = slot + 1 === window ? 0 : slot + 1;
      }
      checksum = (checksum * 31 + c.x + c.y) % TWO_32;
    }
    return checksum;
  }
}
