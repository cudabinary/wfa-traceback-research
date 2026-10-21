"""Allocation model for the fixed WFA-GPU exact-CIGAR runner.

No CUDA, files, environment variables, timing, or mutable global state are used.
The model describes one fresh GPU child, one alignment call, 64-bit WSL ABI,
penalties (2, 3, 1), tblock=256, initialized final status, diagnostics disabled,
and the max-batch/padding/size_t fixes inherited from long_exact v3.

The result is tracked CUDA API reservation, assuming allocations succeed.  It
excludes CUDA driver/context/module allocations, pinned/ordinary host memory,
physical residency, and paging.  It does not predict runtime or GPU completion.
"""

from collections.abc import Iterable, Sequence
from operator import index

__all__ = ["footprint"]


def footprint(
    pairs: Iterable[tuple[str, str]],
    cfg: Sequence[object],
) -> int:
    """Return the successful-path peak CUDA reservation in integer bytes.

    ``pairs`` is the actual order of the GPU child's input, before batching.
    ``cfg`` is [variant, E, workers, batch, requested_cap, mode], where variant
    is 'base', 'guarded', or 'gc'.  E/workers/batch must be explicit positives.
    The batch is clipped to the input count, just as the runner/API does.

    'base' ignores requested_cap.  'guarded'/'gc' use the lesser positive cap
    and the source bound; cap=0 selects the source bound.  A 'gc' binary reserves
    bitmap/rank even in mode=0.  The current full/prefix helper has no extra
    relocation arena.  No-GC modes do not change allocation.

    This function requires nonempty, source-representable ASCII input without
    embedded NULs.  It does not reinterpret DNA characters or route unsupported
    inputs to the CPU; those are the caller's separate correctness contract.
    Empty GPU groups must be skipped by the caller rather than launched.

    ValueError identifies an invalid explicit configuration/source begin check;
    OverflowError identifies an intermediate outside the audited source ABI.
    Neither exception represents an observed device OOM.
    """
    if len(cfg) != 6:
        raise ValueError("cfg must be [variant, E, W, B, C, mode]")
    variant = cfg[0]
    if variant not in ("base", "guarded", "gc"):
        raise ValueError("variant must be 'base', 'guarded', or 'gc'")

    numbers = []
    for label, value in zip(("E", "W", "B", "C", "mode"), cfg[1:]):
        if isinstance(value, bool):
            raise TypeError(f"{label} must be an integer, not bool")
        try:
            numbers.append(index(value))
        except TypeError as exc:
            raise TypeError(f"{label} must be an integer") from exc
    error, workers, requested_batch, requested_cap, _mode = numbers
    if error <= 0 or workers <= 0 or requested_batch <= 0 or requested_cap < 0:
        raise ValueError("E, W and B must be positive; C must be nonnegative")

    int_max = (1 << 31) - 1
    uint_max = (1 << 32) - 1
    size_max = (1 << 64) - 1
    width = 2 * error + 1
    q = 5 * width
    # Source padding is strict: an already aligned count gets another four.
    offsets = q + 4 - q % 4
    if workers > int_max or width > int_max or 3 * offsets > int_max:
        raise OverflowError("configuration exceeds source int intermediates")
    working_per_worker = 30 * offsets  # 3 * (int16 offset + u32 vector + u32 prev)
    result_blocks = (2 * error) // 16
    source_cap = width * result_blocks
    capacity = source_cap
    if variant != "base" and requested_cap:
        capacity = min(requested_cap, source_cap)
    if capacity >= 1 << 32:
        raise OverflowError("source cannot address this many worker records")

    scratch = 0
    if variant == "gc":
        headroom = 3 * width
        if capacity + 31 > uint_max or 3 * capacity > uint_max:
            raise OverflowError("configuration exceeds GC unsigned intermediates")
        trigger = 3 * capacity // 4
        if capacity <= headroom or trigger >= capacity - headroom or trigger < 32:
            raise ValueError("source GC begin rejects capacity/default trigger")
        scratch = 8 * ((capacity + 31) // 32) * workers

    count = 0
    previous_text_end = 0
    batch_first_pattern = 0
    batch_packed = 0
    max_unpacked = 0
    max_packed = 0
    for pair in pairs:
        if isinstance(pair, (str, bytes)) or len(pair) != 2:
            raise TypeError("each pair must contain two str sequences")
        pattern, text = pair
        if not isinstance(pattern, str) or not isinstance(text, str):
            raise TypeError("each sequence must be str")
        if not pattern.isascii() or not text.isascii() or "\0" in pattern or "\0" in text:
            raise ValueError("source byte lengths require ASCII without NULs")
        plen, tlen = len(pattern), len(text)
        if max(plen, tlen) >= 32768:
            raise ValueError("source add_sequences rejects length >= 32768")

        # aligner.h: WFA_ALIGN_32_BITS(x) = x + 4 - x % 4.
        pattern_offset = (
            previous_text_end + 4 - previous_text_end % 4 if count else 0
        )
        before_text = pattern_offset + plen + 1
        text_offset = before_text + 4 - before_text % 4
        previous_text_end = text_offset + tlen + 1
        if count % requested_batch == 0:
            batch_first_pattern = pattern_offset
            batch_packed = 0
        pa, pb = plen // 4, tlen // 4
        batch_packed += pa + 4 - pa % 4 + pb + 4 - pb % 4
        count += 1
        # Updating maxima within a batch also covers the final partial batch.
        max_unpacked = max(max_unpacked, previous_text_end - batch_first_pattern)
        max_packed = max(max_packed, batch_packed)

    if not count:
        raise ValueError("empty GPU group must be skipped by the caller")
    if count > uint_max:
        raise OverflowError("pair count exceeds source uint32 indexing")
    batch = min(requested_batch, count)
    other = (
        8 * result_blocks * batch  # final traceback result tail
        + 68 * batch  # sizeof(sequence_pair_t)=48, alignment_result_t=20
        + 40 * count  # RunRow=32 and size_t pattern-offset lookup=8
        + max_unpacked + 3
        + max_packed + 4
        + 4  # queue cursor following the working arrays
    )
    total = workers * (8 * capacity + working_per_worker) + scratch + other
    if total > size_max:
        raise OverflowError("reservation exceeds source size_t address range")
    return total
