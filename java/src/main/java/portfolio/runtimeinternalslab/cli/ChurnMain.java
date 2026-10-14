package portfolio.runtimeinternalslab.cli;

import java.io.PrintStream;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import portfolio.runtimeinternalslab.workload.VectorChurn;

/**
 * Runs the shared vector-churn workload and prints one JSON result line.
 *
 * <p>Usage: {@code ChurnMain --ops N --window W --seed S --warmup K --rounds R}. Warm-up rounds let
 * the JIT compile the loop; only the measured rounds are counted. Exit code 2 means bad arguments.
 */
public final class ChurnMain {
    private static final Set<String> OPTIONS = Set.of("ops", "window", "seed", "warmup", "rounds");

    private ChurnMain() {}

    /** Command-line entry point. */
    public static void main(String[] args) {
        System.exit(run(args, System.out, System.err));
    }

    /** Runs with the given arguments and streams; returns the process exit code. */
    static int run(String[] args, PrintStream out, PrintStream err) {
        Args a;
        int ops;
        int window;
        int seed;
        int warmup;
        int rounds;
        try {
            a = Args.parse(args, OPTIONS);
            ops = (int) a.number("ops", 1_000_000, 1, VectorChurn.MAX_OPS);
            window = (int) a.number("window", 0, 0, VectorChurn.MAX_WINDOW);
            seed = (int) a.number("seed", 42, 1, 0xFFFF_FFFFL);
            warmup = (int) a.number("warmup", 20, 0, 1_000);
            rounds = (int) a.number("rounds", 20, 1, 1_000);
        } catch (IllegalArgumentException e) {
            err.println("error: " + e.getMessage());
            return 2;
        }
        VectorChurn churn = new VectorChurn(window);
        long checksum = -1;
        for (int i = 0; i < warmup; i++) {
            checksum = same(checksum, churn.run(ops, seed));
        }
        Meter.Snapshot before = Meter.snapshot();
        for (int i = 0; i < rounds; i++) {
            checksum = same(checksum, churn.run(ops, seed));
        }
        Meter.Delta d = Meter.between(before, Meter.snapshot());
        long total = (long) ops * rounds;
        Map<String, Object> line = new LinkedHashMap<>(Meter.runtimeInfo());
        line.put("workload", "vector-churn");
        line.put("ops", ops);
        line.put("window", window);
        line.put("seed", Integer.toUnsignedLong(seed));
        line.put("warmup", warmup);
        line.put("rounds", rounds);
        line.put("checksum", checksum);
        line.put("wall_ns", d.wallNanos());
        line.put("ns_per_op", (double) d.wallNanos() / total);
        line.put("alloc_bytes", d.allocatedBytes());
        line.put("alloc_bytes_per_op", (double) d.allocatedBytes() / total);
        line.put("gc_count", d.gcCount());
        line.put("gc_time_ms", (double) d.gcTimeMs());
        line.put("collectors", d.collectors());
        out.println(Json.object(line));
        return 0;
    }

    /** Every round from the same seed must give the same checksum ({@code -1} = none yet). */
    static long same(long previous, long actual) {
        if (previous != -1 && previous != actual) {
            throw new IllegalStateException("checksum changed between rounds: " + previous + " vs " + actual);
        }
        return actual;
    }
}
