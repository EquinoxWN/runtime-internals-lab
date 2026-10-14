package portfolio.runtimeinternalslab.cli;

import java.io.PrintStream;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import portfolio.runtimeinternalslab.escape.EscapeCases;
import portfolio.runtimeinternalslab.escape.EscapeCases.Variant;

/**
 * Measures bytes allocated per operation for every escape-analysis variant and prints one JSON
 * line each. Run it with {@code -XX:-DoEscapeAnalysis} to see what the same code costs without
 * escape analysis, or with {@code -XX:+LogCompilation} to see which allocations C2 removed.
 *
 * <p>Usage: {@code EscapeMain --ops N --seed S --warmup K --rounds R --case NAME|all}. Exit code 1
 * means an "escapes" and a "fixed" variant disagreed; 2 means bad arguments.
 */
public final class EscapeMain {
    private static final Set<String> OPTIONS = Set.of("ops", "seed", "warmup", "rounds", "case");

    private EscapeMain() {}

    /** Command-line entry point. */
    public static void main(String[] args) {
        System.exit(run(args, System.out, System.err));
    }

    /** Runs with the given arguments and streams; returns the process exit code. */
    static int run(String[] args, PrintStream out, PrintStream err) {
        Set<String> names = new LinkedHashSet<>();
        names.add("all");
        EscapeCases.all().forEach(v -> names.add(v.caseName()));
        int ops;
        int seed;
        int warmup;
        int rounds;
        String only;
        try {
            Args a = Args.parse(args, OPTIONS);
            ops = (int) a.number("ops", 1_000_000, 1, 100_000_000);
            seed = (int) a.number("seed", 42, 1, 0xFFFF_FFFFL);
            warmup = (int) a.number("warmup", 30, 0, 1_000);
            rounds = (int) a.number("rounds", 10, 1, 1_000);
            only = a.choice("case", "all", names);
        } catch (IllegalArgumentException e) {
            err.println("error: " + e.getMessage());
            return 2;
        }
        List<Variant> selected = EscapeCases.all().stream()
                .filter(v -> only.equals("all") || v.caseName().equals(only))
                .toList();
        Map<String, Long> resultByCase = new HashMap<>();
        int status = 0;
        for (Variant v : selected) {
            long result = 0;
            for (int i = 0; i < warmup; i++) {
                result = v.kernel().run(ops, seed);
            }
            Meter.Snapshot before = Meter.snapshot();
            for (int i = 0; i < rounds; i++) {
                result = v.kernel().run(ops, seed);
            }
            Meter.Delta d = Meter.between(before, Meter.snapshot());
            long total = (long) ops * rounds;
            Long previous = resultByCase.putIfAbsent(v.caseName(), result);
            boolean agrees = previous == null || previous == result;
            if (!agrees) {
                status = 1;
            }
            Map<String, Object> line = new LinkedHashMap<>(Meter.runtimeInfo());
            line.put("experiment", "escape");
            line.put("case", v.caseName());
            line.put("variant", v.variant());
            line.put("ops", ops);
            line.put("seed", Integer.toUnsignedLong(seed));
            line.put("warmup", warmup);
            line.put("rounds", rounds);
            line.put("result", result);
            line.put("agrees", agrees);
            line.put("wall_ns", d.wallNanos());
            line.put("ns_per_op", (double) d.wallNanos() / total);
            line.put("alloc_bytes", d.allocatedBytes());
            line.put("alloc_bytes_per_op", (double) d.allocatedBytes() / total);
            line.put("gc_count", d.gcCount());
            line.put("gc_time_ms", (double) d.gcTimeMs());
            out.println(Json.object(line));
        }
        if (status != 0) {
            err.println("error: an escapes and a fixed variant returned different results");
        }
        return status;
    }
}
