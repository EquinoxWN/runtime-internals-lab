package portfolio.runtimeinternalslab.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;

class CliTest {
    private final ByteArrayOutputStream out = new ByteArrayOutputStream();
    private final ByteArrayOutputStream err = new ByteArrayOutputStream();

    private int churn(String... args) {
        return ChurnMain.run(args, stream(out), stream(err));
    }

    private int escape(String... args) {
        return EscapeMain.run(args, stream(out), stream(err));
    }

    private static PrintStream stream(ByteArrayOutputStream bytes) {
        return new PrintStream(bytes, true, StandardCharsets.UTF_8);
    }

    private static String text(ByteArrayOutputStream bytes) {
        return bytes.toString(StandardCharsets.UTF_8);
    }

    @Test
    void churnPrintsOneResultLineWithTheSharedChecksum() {
        assertEquals(0, churn("--ops", "1000", "--window", "10", "--seed", "42", "--warmup", "1", "--rounds", "2"));
        String line = text(out).strip();
        assertEquals(1, line.lines().count());
        assertTrue(line.startsWith("{\"runtime\":\"java\""), line);
        assertTrue(line.contains("\"checksum\":1706363773"), line);
        assertTrue(line.contains("\"alloc_bytes_per_op\":"), line);
        assertTrue(line.contains("\"collectors\":{"), line);
    }

    @Test
    void churnAcceptsTheLargestSeedAndZeroWarmUp() {
        assertEquals(0, churn("--ops", "1000", "--window", "100", "--seed", "4294967295", "--warmup", "0"));
        assertTrue(text(out).contains("\"checksum\":166371539"), text(out));
        assertTrue(text(out).contains("\"seed\":4294967295"), text(out));
    }

    @Test
    void badArgumentsExitWithTwoAndSayWhy() {
        assertEquals(2, churn("--ops", "0"));
        assertEquals(2, churn("--seed", "0"));
        assertEquals(2, churn("--window", "1000001"));
        assertEquals(2, escape("--case", "nope"));
        assertTrue(text(err).contains("error: --ops must be in"), text(err));
        assertEquals("", text(out));
    }

    @Test
    void escapePrintsOneAgreeingLinePerVariant() {
        assertEquals(0, escape("--ops", "2000", "--warmup", "1", "--rounds", "1"));
        List<String> lines = text(out).strip().lines().toList();
        assertEquals(7, lines.size());
        for (String line : lines) {
            assertTrue(line.contains("\"experiment\":\"escape\""), line);
            assertTrue(line.contains("\"agrees\":true"), line);
        }
        assertEquals(0, escape("--ops", "10", "--case", "branch-merge", "--rounds", "1"));
        assertEquals(9, text(out).strip().lines().count());
    }

    @Test
    void roundsThatDisagreeAreReported() {
        assertEquals(5L, ChurnMain.same(-1, 5));
        assertEquals(5L, ChurnMain.same(5, 5));
        assertThrows(IllegalStateException.class, () -> ChurnMain.same(5, 6));
    }
}
