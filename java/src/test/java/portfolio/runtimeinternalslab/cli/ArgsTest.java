package portfolio.runtimeinternalslab.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Set;
import org.junit.jupiter.api.Test;

class ArgsTest {
    private static final Set<String> ALLOWED = Set.of("ops", "case");

    @Test
    void readsNumbersAndChoicesWithDefaults() {
        Args a = Args.parse(new String[] {"--ops", "500"}, ALLOWED);
        assertEquals(500, a.number("ops", 1, 1, 1_000));
        assertEquals("all", a.choice("case", "all", Set.of("all", "x")));
        assertEquals(7, Args.parse(new String[0], ALLOWED).number("ops", 7, 1, 10));
    }

    @Test
    void rejectsUnknownRepeatedAndValuelessOptions() {
        assertThrows(IllegalArgumentException.class, () -> Args.parse(new String[] {"--nope", "1"}, ALLOWED));
        assertThrows(IllegalArgumentException.class, () -> Args.parse(new String[] {"ops", "1"}, ALLOWED));
        assertThrows(IllegalArgumentException.class, () -> Args.parse(new String[] {"--ops"}, ALLOWED));
        assertThrows(
                IllegalArgumentException.class, () -> Args.parse(new String[] {"--ops", "1", "--ops", "2"}, ALLOWED));
        assertThrows(
                IllegalArgumentException.class,
                () -> Args.parse(new String[] {"--ops", "1", "--case", "x", "--ops", "2"}, ALLOWED));
    }

    @Test
    void rejectsNonIntegersOutOfRangeValuesAndUnknownChoices() {
        Args a = Args.parse(new String[] {"--ops", "12x", "--case", "y"}, ALLOWED);
        assertThrows(IllegalArgumentException.class, () -> a.number("ops", 1, 1, 100));
        assertThrows(IllegalArgumentException.class, () -> a.choice("case", "all", Set.of("all", "x")));
        Args big = Args.parse(new String[] {"--ops", "101"}, ALLOWED);
        assertThrows(IllegalArgumentException.class, () -> big.number("ops", 1, 1, 100));
        Args negative = Args.parse(new String[] {"--ops", "-1"}, ALLOWED);
        assertThrows(IllegalArgumentException.class, () -> negative.number("ops", 1, 0, 100));
    }
}
