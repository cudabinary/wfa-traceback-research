#include "bench_common.hpp"
#include "utils/wfa_cpu.h"
#include <dlfcn.h>
extern "C" int compute_distance_cpu_threaded(int batch,int from,alignment_result_t*r,wfa_alignment_result_t*ar,const sequence_pair_t*sm,char*buf,int x,int o,int e,bool adaptive){
    using F=int(*)(int,int,alignment_result_t*,wfa_alignment_result_t*,const sequence_pair_t*,char*,int,int,int,bool);
    static auto real=(F)dlsym(RTLD_NEXT,"compute_distance_cpu_threaded");if(!real)abort();
    nvtxRangePushA("cpu_fallback_score");double start=now_ms();
    int n=real(batch,from,r,ar,sm,buf,x,o,e,adaptive);
    double ms=now_ms()-start;nvtxRangePop();
    std::cerr<<"FALLBACK score from="<<from<<" batch="<<batch<<" n="<<n<<" ms="<<ms<<std::endl;return n;
}
extern "C" int compute_alignments_cpu_threaded(int batch,int from,alignment_result_t*r,wfa_alignment_result_t*ar,const sequence_pair_t*sm,char*buf,wfa_backtrace_t*bt,uint32_t off,int x,int o,int e,bool adaptive){
    using F=int(*)(int,int,alignment_result_t*,wfa_alignment_result_t*,const sequence_pair_t*,char*,wfa_backtrace_t*,uint32_t,int,int,int,bool);
    static auto real=(F)dlsym(RTLD_NEXT,"compute_alignments_cpu_threaded");if(!real)abort();
    nvtxRangePushA("cpu_fallback_and_cigar");double start=now_ms();
    int n=real(batch,from,r,ar,sm,buf,bt,off,x,o,e,adaptive);
    double ms=now_ms()-start;nvtxRangePop();
    std::cerr<<"FALLBACK cigar from="<<from<<" batch="<<batch<<" n="<<n<<" ms="<<ms<<std::endl;return n;
}
