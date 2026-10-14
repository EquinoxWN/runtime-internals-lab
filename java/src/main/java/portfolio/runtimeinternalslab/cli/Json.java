package portfolio.runtimeinternalslab.cli;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Writes one flat JSON object per line; enough for the result lines the Python runner reads. */
final class Json {
    private Json() {}

    /** Serialises a map of strings, numbers, booleans, null, string lists and nested maps. */
    static String object(Map<String, ?> fields) {
        StringBuilder sb = new StringBuilder(256).append('{');
        boolean first = true;
        for (Map.Entry<String, ?> e : fields.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            string(sb, e.getKey());
            sb.append(':');
            value(sb, e.getValue());
        }
        return sb.append('}').toString();
    }

    /** Appends one JSON value. */
    private static void value(StringBuilder sb, Object v) {
        switch (v) {
            case null -> sb.append("null");
            case String s -> string(sb, s);
            case Boolean b -> sb.append(b);
            case Integer i -> sb.append(i);
            case Long l -> sb.append(l);
            case Double d -> {
                if (d.isNaN() || d.isInfinite()) {
                    throw new IllegalArgumentException("JSON has no NaN or infinity");
                }
                sb.append(String.format(Locale.ROOT, "%.4f", d));
            }
            case List<?> list -> {
                sb.append('[');
                for (int i = 0; i < list.size(); i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    value(sb, list.get(i));
                }
                sb.append(']');
            }
            case Map<?, ?> map -> {
                @SuppressWarnings("unchecked")
                Map<String, ?> typed = (Map<String, ?>) map;
                sb.append(object(typed));
            }
            default -> throw new IllegalArgumentException("unsupported JSON value: " + v.getClass());
        }
    }

    /** Appends a quoted, escaped string. */
    private static void string(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) {
                        sb.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        sb.append('"');
    }
}
