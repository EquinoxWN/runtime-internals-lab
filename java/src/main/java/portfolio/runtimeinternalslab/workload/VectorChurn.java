package portfolio.runtimeinternalslab.workload;

import java.util.Arrays;

/**
 * The shared allocation-heavy workload ("vector-churn", spec/workload.md), Java version.
 *
 * <p>Each operation allocates four {@link Vec} objects. With a window greater than zero the last
 * one is also kept in a ring of that many slots, so it lives for {@code window} operations and
 * escapes to the heap; with a window of zero every object is garbage at the end of its operation.
 */
public final class VectorChurn {
    /** Upper bound for operations per round, so a typo cannot run for hours. */
    public static final int MAX_OPS = 100_000_000;
    /** Upper bound for the ring size (one million references). */
    public static final int MAX_WINDOW = 1_000_000;

    private static final long MASK = 0xFFFF_FFFFL;

    private final int window;
    private final Vec[] ring;

    /** Creates a workload whose ring keeps the last {@code window} results (0 = none). */
    public VectorChurn(int window) {
        if (window < 0 || window > MAX_WINDOW) {
            throw new IllegalArgumentException("window must be in [0, " + MAX_WINDOW + "]");
        }
        this.window = window;
        this.ring = new Vec[window];
    }

    /** Runs one round of {@code ops} operations from {@code seed}; returns the 32-bit checksum. */
    public long run(int ops, int seed) {
        if (ops < 1 || ops > MAX_OPS) {
            throw new IllegalArgumentException("ops must be in [1, " + MAX_OPS + "]");
        }
        Arrays.fill(ring, null);
        XorShift32 rng = new XorShift32(seed);
        long checksum = 0;
        int slot = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec a = new Vec(r & 0xFFFF, r >>> 16);
            Vec b = new Vec(r >>> 16, r & 0xFFFF);
            Vec c = a.add(b).scale(3);
            if (window > 0) {
                Vec old = ring[slot];
                if (old != null) {
                    checksum = (checksum + old.x()) & MASK;
                }
                ring[slot] = c;
                slot = slot + 1 == window ? 0 : slot + 1;
            }
            checksum = (checksum * 31 + c.x() + c.y()) & MASK;
        }
        return checksum;
    }

    /** The configured ring size. */
    public int window() {
        return window;
    }
}
