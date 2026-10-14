package portfolio.runtimeinternalslab.workload;

/**
 * Marsaglia's xorshift32 generator (shifts 13, 17, 5), the random source every runtime shares.
 *
 * <p>Outputs are unsigned 32-bit values held in an {@code int}; callers use {@code >>>} and masks,
 * so the bits are identical to the Python and JavaScript versions.
 */
public final class XorShift32 {
    private int state;

    /** Starts from a seed, which must be non-zero (zero is a fixed point). */
    public XorShift32(int seed) {
        if (seed == 0) {
            throw new IllegalArgumentException("xorshift32 seed must be non-zero");
        }
        this.state = seed;
    }

    /** Next 32 random bits. */
    public int next() {
        int x = state;
        x ^= x << 13;
        x ^= x >>> 17;
        x ^= x << 5;
        state = x;
        return x;
    }
}
