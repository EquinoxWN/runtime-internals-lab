package portfolio.runtimeinternalslab.workload;

/**
 * An immutable 2D integer vector: the small, short-lived object every workload allocates.
 *
 * <p>On 64-bit HotSpot with compressed class pointers an instance takes 24 bytes (12-byte header,
 * two 4-byte fields, padding to 8), which is what the allocation counters measure per object.
 */
public record Vec(int x, int y) {

    /** Component-wise sum, as a new object. */
    public Vec add(Vec o) {
        return new Vec(x + o.x, y + o.y);
    }

    /** Both components times k, as a new object. */
    public Vec scale(int k) {
        return new Vec(x * k, y * k);
    }
}
