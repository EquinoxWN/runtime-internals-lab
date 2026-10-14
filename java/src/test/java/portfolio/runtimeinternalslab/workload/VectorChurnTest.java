package portfolio.runtimeinternalslab.workload;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import java.util.Random;
import org.junit.jupiter.api.Test;
import portfolio.runtimeinternalslab.SpecJson;

class VectorChurnTest {

    @Test
    void everySharedChecksumMatches() {
        for (Map<String, Object> c : SpecJson.list("checksums")) {
            VectorChurn churn = new VectorChurn((int) SpecJson.num(c, "window"));
            long actual = churn.run((int) SpecJson.num(c, "ops"), (int) SpecJson.num(c, "seed"));
            assertEquals(SpecJson.num(c, "checksum"), actual, c.toString());
        }
    }

    @Test
    void theRingIsEmptiedAtTheStartOfEveryRound() {
        VectorChurn churn = new VectorChurn(64);
        long first = churn.run(1_000, 7);
        churn.run(500, 99);
        assertEquals(first, churn.run(1_000, 7));
    }

    @Test
    void retainedObjectsChangeTheChecksumOnlyOnceTheRingWraps() {
        assertEquals(new VectorChurn(0).run(100, 5), new VectorChurn(100).run(100, 5));
        assertNotEquals(new VectorChurn(0).run(101, 5), new VectorChurn(100).run(101, 5));
    }

    @Test
    void checksumsStayUnsigned32BitForRandomInputs() {
        Random random = new Random(1);
        for (int t = 0; t < 50; t++) {
            int window = random.nextInt(50);
            long sum = new VectorChurn(window).run(1 + random.nextInt(5_000), 1 + random.nextInt(Integer.MAX_VALUE));
            assertTrue(sum >= 0 && sum <= 0xFFFF_FFFFL, "checksum " + sum);
        }
    }

    @Test
    void rejectsOutOfRangeArguments() {
        assertThrows(IllegalArgumentException.class, () -> new VectorChurn(-1));
        assertThrows(IllegalArgumentException.class, () -> new VectorChurn(VectorChurn.MAX_WINDOW + 1));
        VectorChurn churn = new VectorChurn(0);
        assertThrows(IllegalArgumentException.class, () -> churn.run(0, 1));
        assertThrows(IllegalArgumentException.class, () -> churn.run(VectorChurn.MAX_OPS + 1, 1));
        assertThrows(IllegalArgumentException.class, () -> churn.run(10, 0));
    }

    @Test
    void vecOperationsReturnNewObjects() {
        Vec a = new Vec(1, 2);
        Vec b = a.add(new Vec(3, 4));
        assertEquals(new Vec(4, 6), b);
        assertEquals(new Vec(12, 18), b.scale(3));
        assertEquals(new Vec(1, 2), a);
    }
}
