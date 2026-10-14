package portfolio.runtimeinternalslab.escape;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.lang.management.ManagementFactory;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Checks the M1 claim inside the test JVM: once C2 has compiled them, the fixed variants allocate
 * nothing per operation while the escaping ones still allocate a 24-byte {@code Vec} each time.
 */
class EscapeAnalysisTest {
    private static final com.sun.management.ThreadMXBean THREADS =
            (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
    private static final int OPS = 100_000;

    /** Bytes per operation of the cheapest of up to {@code rounds} calls. */
    private static double minBytesPerOp(EscapeCases.Kernel kernel, int rounds) {
        double best = Double.MAX_VALUE;
        for (int i = 0; i < rounds; i++) {
            long before = THREADS.getCurrentThreadAllocatedBytes();
            kernel.run(OPS, 42);
            best = Math.min(best, (double) (THREADS.getCurrentThreadAllocatedBytes() - before) / OPS);
            if (best < 0.01) {
                break;
            }
        }
        return best;
    }

    private static void assumeEscapeAnalysisIsOn() {
        List<String> flags = ManagementFactory.getRuntimeMXBean().getInputArguments();
        assumeTrue(!flags.contains("-XX:-DoEscapeAnalysis") && !flags.contains("-Xint"));
    }

    @Test
    void fixedVariantsEndUpAllocatingNothingPerOperation() {
        assumeEscapeAnalysisIsOn();
        assertTrue(minBytesPerOp(EscapeCases::temporaries, 400) < 0.01, "temporaries");
        assertTrue(minBytesPerOp(EscapeCases::branchMergeFixed, 400) < 0.01, "branch-merge fixed");
        assertTrue(minBytesPerOp(EscapeCases::loopAccumulatorFixed, 400) < 0.01, "loop-accumulator fixed");
        assertTrue(minBytesPerOp(EscapeCases::staticStoreFixed, 400) < 0.01, "static-store fixed");
    }

    @Test
    void escapingVariantsKeepAllocatingAfterWarmUp() {
        assumeEscapeAnalysisIsOn();
        assertTrue(minBytesPerOp(EscapeCases::branchMergeEscapes, 100) >= 23.9, "branch-merge escapes");
        assertTrue(minBytesPerOp(EscapeCases::loopAccumulatorEscapes, 100) >= 23.9, "loop-accumulator escapes");
        assertTrue(minBytesPerOp(EscapeCases::staticStoreEscapes, 100) >= 23.9, "static-store escapes");
    }
}
