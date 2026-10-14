package portfolio.runtimeinternalslab.escape;

import java.util.List;
import portfolio.runtimeinternalslab.workload.Vec;
import portfolio.runtimeinternalslab.workload.XorShift32;

/**
 * Escape-analysis cases: each pair computes the same result, but in the "escapes" variant the
 * {@link Vec} reaches the heap and in the "fixed" variant a small change lets C2 scalar-replace it.
 *
 * <p>Methods are static and small on purpose, so their allocation sites are easy to find in a
 * {@code -XX:+LogCompilation} log (method name plus bytecode index).
 */
public final class EscapeCases {

    /** One measurable variant: a case name, a variant name and the method that runs it. */
    public record Variant(String caseName, String variant, Kernel kernel) {}

    /** A kernel runs {@code ops} operations from a seed and returns a 64-bit result. */
    @FunctionalInterface
    public interface Kernel {
        /** Runs the kernel. */
        long run(int ops, int seed);
    }

    /** Last vector seen, kept "for debugging": the static store that makes it escape. */
    private static Vec lastSeen = new Vec(0, 0);

    /** Last components seen, the fixed variant's replacement for {@link #lastSeen}. */
    private static int lastX;

    private static int lastY;

    private EscapeCases() {}

    /** Every variant, in the order the experiment reports them. */
    public static List<Variant> all() {
        return List.of(
                new Variant("temporaries", "control", EscapeCases::temporaries),
                new Variant("branch-merge", "escapes", EscapeCases::branchMergeEscapes),
                new Variant("branch-merge", "fixed", EscapeCases::branchMergeFixed),
                new Variant("loop-accumulator", "escapes", EscapeCases::loopAccumulatorEscapes),
                new Variant("loop-accumulator", "fixed", EscapeCases::loopAccumulatorFixed),
                new Variant("static-store", "escapes", EscapeCases::staticStoreEscapes),
                new Variant("static-store", "fixed", EscapeCases::staticStoreFixed));
    }

    /** Control: four temporaries per operation that never leave the loop body. */
    public static long temporaries(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        long acc = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec a = new Vec(r & 0xFFFF, r >>> 16);
            Vec b = new Vec(r >>> 16, r & 0xFFFF);
            Vec c = a.add(b).scale(3);
            acc += c.x() + c.y();
        }
        return acc;
    }

    /** Two allocations merge at a control-flow join, so neither is scalar-replaced. */
    public static long branchMergeEscapes(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        long acc = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec v;
            if ((r & 1) == 0) {
                v = new Vec(r & 0xFFFF, r >>> 16);
            } else {
                v = new Vec(r >>> 16, r & 0xFFFF);
            }
            acc += 3L * v.x() + v.y();
        }
        return acc;
    }

    /** The fix: choose the fields in the branches, then allocate once after the join. */
    public static long branchMergeFixed(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        long acc = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            int x;
            int y;
            if ((r & 1) == 0) {
                x = r & 0xFFFF;
                y = r >>> 16;
            } else {
                x = r >>> 16;
                y = r & 0xFFFF;
            }
            Vec v = new Vec(x, y);
            acc += 3L * v.x() + v.y();
        }
        return acc;
    }

    /** An immutable accumulator carried around the loop: each new sum is a heap object. */
    public static long loopAccumulatorEscapes(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        Vec sum = new Vec(0, 0);
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            sum = sum.add(new Vec(r & 0xFF, (r >>> 8) & 0xFF));
        }
        return 31L * sum.x() + sum.y();
    }

    /** The fix: accumulate the components in locals and build one vector after the loop. */
    public static long loopAccumulatorFixed(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        int sx = 0;
        int sy = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec step = new Vec(r & 0xFF, (r >>> 8) & 0xFF);
            sx += step.x();
            sy += step.y();
        }
        Vec sum = new Vec(sx, sy);
        return 31L * sum.x() + sum.y();
    }

    /** Keeping a reference in a static field makes the object globally reachable. */
    public static long staticStoreEscapes(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        long acc = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec v = new Vec(r & 0xFFFF, r >>> 16);
            lastSeen = v;
            acc += v.x() ^ v.y();
        }
        return acc + lastSeen.x() + lastSeen.y();
    }

    /** The fix: keep the two components, not the reference. */
    public static long staticStoreFixed(int ops, int seed) {
        XorShift32 rng = new XorShift32(seed);
        long acc = 0;
        for (int i = 0; i < ops; i++) {
            int r = rng.next();
            Vec v = new Vec(r & 0xFFFF, r >>> 16);
            lastX = v.x();
            lastY = v.y();
            acc += v.x() ^ v.y();
        }
        return acc + lastX + lastY;
    }
}
