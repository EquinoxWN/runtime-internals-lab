package portfolio.runtimeinternalslab.escape;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import portfolio.runtimeinternalslab.escape.EscapeCases.Variant;
import portfolio.runtimeinternalslab.workload.XorShift32;

class EscapeCasesTest {

    @Test
    void everyFixedVariantComputesTheSameResultAsItsEscapingVariant() {
        Random random = new Random(2026);
        Map<String, List<Variant>> byCase =
                EscapeCases.all().stream().collect(Collectors.groupingBy(Variant::caseName));
        for (int t = 0; t < 200; t++) {
            int ops = 1 + random.nextInt(3_000);
            int seed = 1 + random.nextInt(Integer.MAX_VALUE);
            for (List<Variant> variants : byCase.values()) {
                long expected = variants.get(0).kernel().run(ops, seed);
                for (Variant v : variants) {
                    assertEquals(expected, v.kernel().run(ops, seed), v + " ops=" + ops + " seed=" + seed);
                }
            }
        }
    }

    @Test
    void controlSumsSixTimesTheTwoHalvesOfEachRandomWord() {
        XorShift32 rng = new XorShift32(42);
        long expected = 0;
        for (int i = 0; i < 10_000; i++) {
            int r = rng.next();
            expected += 6L * ((r & 0xFFFF) + (r >>> 16));
        }
        assertEquals(expected, EscapeCases.temporaries(10_000, 42));
    }

    @Test
    void everyEscapingCaseHasAFixedVariant() {
        Map<String, List<String>> variants = EscapeCases.all().stream()
                .collect(Collectors.groupingBy(
                        Variant::caseName, Collectors.mapping(Variant::variant, Collectors.toList())));
        assertEquals(List.of("control"), variants.get("temporaries"));
        variants.forEach((name, list) -> {
            if (!name.equals("temporaries")) {
                assertEquals(List.of("escapes", "fixed"), list, name);
            }
        });
        assertTrue(variants.size() >= 4);
    }
}
