package portfolio.runtimeinternalslab;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Reads spec/workload.json, the reference values all three runtimes are tested against. */
public final class SpecJson {
    private static final Map<String, Object> ROOT = load();

    private final String s;
    private int i;

    private SpecJson(String s) {
        this.s = s;
    }

    /** The parsed spec root. */
    public static Map<String, Object> root() {
        return ROOT;
    }

    /** A list of objects under a top-level key. */
    @SuppressWarnings("unchecked")
    public static List<Map<String, Object>> list(String key) {
        return (List<Map<String, Object>>) ROOT.get(key);
    }

    /** Integer field of an object. */
    public static long num(Map<String, Object> obj, String key) {
        return (Long) obj.get(key);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> load() {
        try {
            return (Map<String, Object>) new SpecJson(Files.readString(Path.of("../spec/workload.json"))).value();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** Just enough JSON for the spec: objects, arrays, strings and integers. */
    private Object value() {
        skip();
        char c = s.charAt(i);
        if (c == '{') {
            i++;
            Map<String, Object> m = new LinkedHashMap<>();
            skip();
            if (s.charAt(i) == '}') {
                i++;
                return m;
            }
            while (true) {
                String key = (String) value();
                skip();
                expect(':');
                m.put(key, value());
                skip();
                if (s.charAt(i++) == '}') {
                    return m;
                }
            }
        }
        if (c == '[') {
            i++;
            List<Object> list = new ArrayList<>();
            skip();
            if (s.charAt(i) == ']') {
                i++;
                return list;
            }
            while (true) {
                list.add(value());
                skip();
                if (s.charAt(i++) == ']') {
                    return list;
                }
            }
        }
        if (c == '"') {
            int end = s.indexOf('"', i + 1);
            String str = s.substring(i + 1, end);
            i = end + 1;
            return str;
        }
        int start = i;
        while (i < s.length() && (Character.isDigit(s.charAt(i)) || s.charAt(i) == '-')) {
            i++;
        }
        return Long.parseLong(s.substring(start, i));
    }

    private void skip() {
        while (Character.isWhitespace(s.charAt(i))) {
            i++;
        }
    }

    private void expect(char c) {
        if (s.charAt(i++) != c) {
            throw new IllegalStateException("expected " + c + " at " + (i - 1));
        }
    }
}
