// CPU-only ABI and deferred-copy mock. This is not a CUDA runtime test.
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <functional>
#include <iostream>
#include <vector>

#ifdef __CUDACC__
#error "Build this mock with a CPU C++ compiler, not nvcc."
#endif
// Select the exact header's host guard branch; CUDA annotations are mock-only.
#define __CUDACC__ 1
#define __host__
#define __device__
#define WFA_BT_CAP 1
#include "lib/alignment_results.h"
#include "utils/sequences.h"

static_assert(sizeof(alignment_result_t) == 20);
static_assert(sizeof(wfa_backtrace_t) == 8);
static_assert(sizeof(sequence_pair_t) == 48);
static_assert(offsetof(alignment_result_t, finished) == 0);
static_assert(offsetof(alignment_result_t, distance) == 4);
static_assert(offsetof(alignment_result_t, backtrace) == 8);
static_assert(offsetof(alignment_result_t, num_bt_blocks) == 16);
static_assert(BT_OFFLOADED_RESULT_ELEMENTS(16384) == 2048);

struct Copy { void* dst; const void* src; size_t bytes; };
struct MockStream {
    std::deque<Copy> pending;
    std::vector<Copy> recorded;
    void one() { auto c = pending.front(); pending.pop_front(); std::memcpy(c.dst, c.src, c.bytes); }
    void synchronize() { while (!pending.empty()) one(); }
};
using cudaStream_t = MockStream*;
constexpr int cudaMemcpyDeviceToHost = 2;
int cudaMemcpyAsync(void* dst, const void* src, size_t bytes, int kind, cudaStream_t stream) {
    assert(kind == cudaMemcpyDeviceToHost);
    stream->pending.push_back({dst, src, bytes});
    stream->recorded.push_back({dst, src, bytes});
    return 0;
}
#define CUDA_CHECK_ERR do {} while (0);
#include "copyInResults.inc"

static void run_case(int E, int workers, int allocated_batch, int count, const char* capacity) {
    setenv("WFA_BT_CAP_RECORDS", capacity, 1);
    const size_t C = BT_WORKER_ELEMENTS(E);
    const size_t K = BT_OFFLOADED_RESULT_ELEMENTS(E);
    std::vector<alignment_result_t> device_results(allocated_batch);
    std::vector<wfa_backtrace_t> device_bt(C * workers + K * allocated_batch);
    std::vector<alignment_result_t> host_results(allocated_batch);
    std::vector<wfa_backtrace_t> host_bt(K * allocated_batch, {0xfeedu, 0xbeefu});
    for (int i = 0; i < allocated_batch; ++i) {
        device_results[i] = {bool(i % 2), 100 + i, {unsigned(300 + i), unsigned(i)}, int(K)};
        host_results[i] = {false, -777, {0xfeedu, 0xbeefu}, -1};
    }
    for (size_t i = 0; i < K * allocated_batch; ++i)
        device_bt[C * workers + i] = {unsigned(1000 + i), unsigned(i)};
    MockStream stream;
    copyInResults(host_results.data(), device_results.data(), host_bt.data(), device_bt.data(), count, E, workers, &stream);
    assert(stream.recorded.size() == 2 && stream.pending.size() == 2);
    assert(stream.recorded[0].bytes == size_t(count) * sizeof(alignment_result_t));
    assert(stream.recorded[1].bytes == size_t(count) * K * sizeof(wfa_backtrace_t));
    assert(stream.recorded[1].src == device_bt.data() + C * workers);
    // Return from the actual helper has not made either mock copy complete.
    assert(host_results[0].distance == -777 && host_bt[0].backtrace == 0xfeedu);
    stream.one();
    // Results alone are insufficient: the normal-RLE tail remains stale.
    assert(host_results[0].distance == 100 && host_bt[0].backtrace == 0xfeedu);
    assert(!stream.pending.empty());
    stream.synchronize();
    assert(stream.pending.empty());
    assert(std::memcmp(host_results.data(), device_results.data(), count * sizeof(alignment_result_t)) == 0);
    assert(std::memcmp(host_bt.data(), device_bt.data() + C * workers, count * K * sizeof(wfa_backtrace_t)) == 0);
    if (count < allocated_batch) {
        assert(host_results[count].distance == -777);
        assert(host_bt[count * K].backtrace == 0xfeedu);
    }
}

int main() {
    run_case(8, 2, 3, 3, "0");
    run_case(256, 2, 3, 3, "8192");
    run_case(256, 2, 3, 1, "8192");
    run_case(9, 1, 3, 2, "999999");
    const size_t one = 512 * (sizeof(alignment_result_t) + 2048 * sizeof(wfa_backtrace_t));
    assert(one == 8398848 && 4 * one == 33595392 && 3 * one == 25196544);
    std::cout << "{\"status\":\"CPU_ABI_AND_COPY_MOCK_PASS\",\"cases\":4,"
              << "\"alignment_result_bytes\":" << sizeof(alignment_result_t)
              << ",\"backtrace_bytes\":" << sizeof(wfa_backtrace_t)
              << ",\"sequence_pair_bytes\":" << sizeof(sequence_pair_t)
              << ",\"alignment_result_alignment\":" << alignof(alignment_result_t)
              << ",\"public_result_bytes\":" << sizeof(wfa_alignment_result_t)
              << ",\"tail_records_E16384\":2048,\"one_slot_payload_bytes\":" << one
              << ",\"four_slot_payload_bytes\":" << 4 * one
              << ",\"extra_payload_bytes\":" << 3 * one
              << ",\"native_CUDA_runtime_test\":false}" << std::endl;
}
