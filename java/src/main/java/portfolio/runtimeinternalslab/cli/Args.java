package portfolio.runtimeinternalslab.cli;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/** Strict {@code --name value} parser: unknown, repeated or valueless options are rejected. */
final class Args {
    private final Map<String, String> values = new HashMap<>();

    private Args() {}

    /** Parses {@code args}, accepting only the given option names (without dashes). */
    static Args parse(String[] args, Set<String> allowed) {
        if (args.length > 2 * allowed.size()) {
            throw new IllegalArgumentException("too many arguments");
        }
        Args parsed = new Args();
        for (int i = 0; i < args.length; i += 2) {
            String flag = args[i];
            if (!flag.startsWith("--") || !allowed.contains(flag.substring(2))) {
                throw new IllegalArgumentException("unknown option: " + flag);
            }
            if (i + 1 >= args.length) {
                throw new IllegalArgumentException("missing value for " + flag);
            }
            if (parsed.values.put(flag.substring(2), args[i + 1]) != null) {
                throw new IllegalArgumentException("repeated option: " + flag);
            }
        }
        return parsed;
    }

    /** Integer option in [min, max], or the default when absent. */
    long number(String name, long def, long min, long max) {
        String raw = values.get(name);
        if (raw == null) {
            return def;
        }
        long v;
        try {
            v = Long.parseLong(raw);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("--" + name + " must be an integer", e);
        }
        if (v < min || v > max) {
            throw new IllegalArgumentException("--" + name + " must be in [" + min + ", " + max + "]");
        }
        return v;
    }

    /** String option restricted to a set of choices, or the default when absent. */
    String choice(String name, String def, Set<String> choices) {
        String raw = values.getOrDefault(name, def);
        if (!choices.contains(raw)) {
            throw new IllegalArgumentException("--" + name + " must be one of " + choices);
        }
        return raw;
    }
}
