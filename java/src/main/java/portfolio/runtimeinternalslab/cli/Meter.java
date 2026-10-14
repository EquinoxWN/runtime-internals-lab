package portfolio.runtimeinternalslab.cli;

import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Reads the JVM's own counters around a measured window: bytes allocated by this thread (exact,
 * from the TLAB accounting) and per-collector GC counts and accumulated times (milliseconds).
 */
final class Meter {
    private static final com.sun.management.ThreadMXBean THREADS = threads();

    /** Counters at one moment. */
    record Snapshot(long nanos, long allocatedBytes, Map<String, long[]> collectors) {}

    /** What happened between two snapshots. */
    record Delta(
            long wallNanos,
            long allocatedBytes,
            long gcCount,
            long gcTimeMs,
            Map<String, Map<String, Long>> collectors) {}

    private Meter() {}

    /** Fails fast when the JVM cannot count allocated bytes per thread. */
    private static com.sun.management.ThreadMXBean threads() {
        if (!(ManagementFactory.getThreadMXBean() instanceof com.sun.management.ThreadMXBean bean)
                || !bean.isThreadAllocatedMemorySupported()) {
            throw new IllegalStateException("this JVM does not report per-thread allocated bytes");
        }
        bean.setThreadAllocatedMemoryEnabled(true);
        return bean;
    }

    /** Takes a snapshot of the current thread's allocation counter and every collector. */
    static Snapshot snapshot() {
        Map<String, long[]> gcs = new LinkedHashMap<>();
        for (GarbageCollectorMXBean gc : collectors()) {
            gcs.put(gc.getName(), new long[] {gc.getCollectionCount(), gc.getCollectionTime()});
        }
        long allocated = THREADS.getCurrentThreadAllocatedBytes();
        return new Snapshot(System.nanoTime(), allocated, gcs);
    }

    /** Differences between {@code before} and {@code after}. */
    static Delta between(Snapshot before, Snapshot after) {
        Map<String, Map<String, Long>> per = new LinkedHashMap<>();
        long count = 0;
        long time = 0;
        for (Map.Entry<String, long[]> e : after.collectors().entrySet()) {
            long[] b = before.collectors().getOrDefault(e.getKey(), new long[] {0, 0});
            long c = e.getValue()[0] - b[0];
            long t = e.getValue()[1] - b[1];
            count += c;
            time += t;
            Map<String, Long> one = new LinkedHashMap<>();
            one.put("count", c);
            one.put("time_ms", t);
            per.put(e.getKey(), one);
        }
        return new Delta(
                after.nanos() - before.nanos(), after.allocatedBytes() - before.allocatedBytes(), count, time, per);
    }

    /** The JVM's collectors (for G1: young, old and concurrent). */
    private static List<GarbageCollectorMXBean> collectors() {
        return ManagementFactory.getGarbageCollectorMXBeans();
    }

    /** Runtime facts recorded with every result: version, VM name and the JVM flags in effect. */
    static Map<String, Object> runtimeInfo() {
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("runtime", "java");
        info.put("version", System.getProperty("java.vm.version"));
        info.put("vm", System.getProperty("java.vm.name"));
        info.put("flags", List.copyOf(ManagementFactory.getRuntimeMXBean().getInputArguments()));
        info.put("max_heap_bytes", Runtime.getRuntime().maxMemory());
        return info;
    }
}
