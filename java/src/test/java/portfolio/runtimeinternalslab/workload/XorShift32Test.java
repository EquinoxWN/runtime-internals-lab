package portfolio.runtimeinternalslab.workload;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import portfolio.runtimeinternalslab.SpecJson;

class XorShift32Test {

    @Test
    void matchesTheSharedReferenceSequences() {
        for (Map<String, Object> vector : SpecJson.list("xorshift32")) {
            XorShift32 rng = new XorShift32((int) SpecJson.num(vector, "seed"));
            @SuppressWarnings("unchecked")
            List<Long> first = (List<Long>) vector.get("first");
            for (long expected : first) {
                assertEquals(expected, Integer.toUnsignedLong(rng.next()));
            }
        }
    }

    @Test
    void rejectsTheZeroSeed() {
        assertThrows(IllegalArgumentException.class, () -> new XorShift32(0));
    }

    @Test
    void neverReachesZeroFromANonZeroSeed() {
        XorShift32 rng = new XorShift32(0xFFFF_FFFF);
        for (int i = 0; i < 1_000_000; i++) {
            assertNotEquals(0, rng.next());
        }
    }
}
