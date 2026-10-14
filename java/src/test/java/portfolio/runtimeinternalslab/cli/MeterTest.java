package portfolio.runtimeinternalslab.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class MeterTest {
    private static volatile byte[] sink;

    @Test
    void countsTheBytesThisThreadAllocates() {
        Meter.Snapshot before = Meter.snapshot();
        sink = new byte[1 << 20];
        Meter.Delta d = Meter.between(before, Meter.snapshot());
        assertTrue(d.allocatedBytes() >= (1 << 20), "allocated " + d.allocatedBytes());
        assertTrue(d.allocatedBytes() < (1 << 20) + 64 * 1024, "allocated " + d.allocatedBytes());
        assertEquals(1 << 20, sink.length);
    }

    @Test
    void reportsEveryCollectorAndTheRuntimeFlags() {
        Meter.Delta d = Meter.between(Meter.snapshot(), Meter.snapshot());
        assertFalse(d.collectors().isEmpty());
        Map<String, Object> info = Meter.runtimeInfo();
        assertEquals("java", info.get("runtime"));
        assertTrue(((List<?>) info.get("flags")).contains("-Xmx512m"), info.toString());
    }
}
