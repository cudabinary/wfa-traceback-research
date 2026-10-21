#include "bench_common.hpp"
extern "C" {
#include "wavefront/wavefront_align.h"
}
#include <omp.h>
int main(int argc,char**argv){
    if(argc!=7){std::cerr<<"input scores cigar reps threads memory(high/ultralow)\n";return 2;}
    auto pairs=load(argv[1]);int cigar=std::stoi(argv[3]),reps=std::stoi(argv[4]),threads=std::stoi(argv[5]);
    double prep_start=now_ms();
    omp_set_num_threads(threads);std::vector<int>scores(pairs.size());
    std::vector<std::vector<char>>cigars(pairs.size());
    if(cigar)for(size_t i=0;i<pairs.size();i++)cigars[i].resize(2*(pairs[i].first.size()+pairs[i].second.size())+64);
    wavefront_aligner_attr_t attr=wavefront_aligner_attr_default;
    attr.distance_metric=gap_affine;attr.affine_penalties={0,2,3,1};
    attr.heuristic.strategy=wf_heuristic_none;
    attr.alignment_scope=cigar?compute_alignment:compute_score;
    std::string mode=argv[6];attr.memory_mode=mode=="ultralow"?wavefront_memory_ultralow:(mode=="low"?wavefront_memory_low:(mode=="med"?wavefront_memory_med:wavefront_memory_high));
    std::vector<wavefront_aligner_t*> aligners;
    for(int t=0;t<threads;t++)aligners.push_back(wavefront_aligner_new(&attr));
    std::cout<<"CONFIG pairs="<<pairs.size()<<" threads="<<threads<<" memory="<<argv[6]<<" cigar="<<cigar<<" prep_ms="<<now_ms()-prep_start<<std::endl;
    for(int r=-1;r<reps;r++){
        nvtxRangePushA(r<0?"warmup":"measure_cpu");double start=now_ms();int failed=0;
        #pragma omp parallel for schedule(dynamic,1) reduction(+:failed)
        for(size_t i=0;i<pairs.size();i++){
            auto*a=aligners[omp_get_thread_num()];auto&p=pairs[i];
            int rc=wavefront_align(a,p.first.c_str(),p.first.size(),p.second.c_str(),p.second.size());
            if(rc!=0)failed++;
            scores[i]=-a->cigar->score;
            if(cigar)cigar_sprint(cigars[i].data(),a->cigar,true);
        }
        double elapsed=now_ms()-start;nvtxRangePop();
        if(failed){std::cerr<<"CPU_FAILURE "<<failed<<std::endl;return 3;}
        std::cout<<"ROW "<<r<<" "<<elapsed<<std::endl;
    }
    write_scores(argv[2],scores);
    if(cigar){std::ofstream out(std::string(argv[2])+".cigar");for(auto&c:cigars)out<<c.data()<<'\n';}
    for(auto*a:aligners)wavefront_aligner_delete(a);
}
