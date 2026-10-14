/** Marsaglia's xorshift32 generator (shifts 13, 17, 5), bit-for-bit the same as Java and Python. */
export class XorShift32 {
  /** @type {number} */
  #state;

  /**
   * Start from a non-zero unsigned 32-bit seed (zero is a fixed point).
   * @param {number} seed
   */
  constructor(seed) {
    if (!Number.isInteger(seed) || seed < 1 || seed > 0xffffffff) {
      throw new RangeError("xorshift32 seed must be an integer in [1, 2**32 - 1]");
    }
    this.#state = seed | 0;
  }

  /**
   * Next 32 random bits as an unsigned integer.
   * @returns {number}
   */
  next() {
    let x = this.#state;
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    this.#state = x;
    return x >>> 0;
  }
}
