void copyInResults (alignment_result_t* const results,
                    const alignment_result_t* const results_d,
                    wfa_backtrace_t* const backtraces,
                    const wfa_backtrace_t* const bt_offloaded_d,
                    const size_t num_alignments,
                    const int max_steps,
                    const int num_blocks,
                    cudaStream_t stream) {
    const size_t bt_offloaded_results_size = BT_OFFLOADED_RESULT_ELEMENTS(max_steps)
                                             * num_alignments;
    const size_t bt_offloaded_size = BT_WORKER_ELEMENTS(max_steps) * num_blocks;

    const wfa_backtrace_t* const bt_offloaded_results_d = bt_offloaded_d
                                              + bt_offloaded_size;

    cudaMemcpyAsync(results, results_d, num_alignments * sizeof(alignment_result_t),
               cudaMemcpyDeviceToHost, stream);
    CUDA_CHECK_ERR
    cudaMemcpyAsync(backtraces, bt_offloaded_results_d,
               bt_offloaded_results_size * sizeof(wfa_backtrace_t),
               cudaMemcpyDeviceToHost, stream);
    CUDA_CHECK_ERR
}
