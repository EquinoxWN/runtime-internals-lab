package portfolio.runtimeinternalslab.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class JsonTest {

    @Test
    void writesEveryValueKindTheResultLinesUse() {
        Map<String, Object> inner = new LinkedHashMap<>();
        inner.put("count", 3L);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("s", "a\"b\\c\n" + (char) 1);
        m.put("i", 1);
        m.put("l", 4_294_967_295L);
        m.put("d", 2.5);
        m.put("b", true);
        m.put("n", null);
        m.put("list", List.of("-Xmx512m", "x"));
        m.put("map", inner);
        String expected = "{\"s\":\"a\\\"b\\\\c\\n\\u0001\",\"i\":1,\"l\":4294967295,\"d\":2.5000,\"b\":true,"
                + "\"n\":null,\"list\":[\"-Xmx512m\",\"x\"],\"map\":{\"count\":3}}";
        assertEquals(expected, Json.object(m));
    }

    @Test
    void refusesValuesJsonCannotRepresent() {
        assertThrows(IllegalArgumentException.class, () -> Json.object(Map.of("d", Double.NaN)));
        assertThrows(IllegalArgumentException.class, () -> Json.object(Map.of("o", new Object())));
    }
}
