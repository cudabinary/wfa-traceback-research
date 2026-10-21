#include "bench_common.hpp"
#include "lib/aligner.h"
#include <cuda_runtime.h>
#include <omp.h>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
int main(int argc,char**argv){
    if(argc!=10){std::cerr<<"input scores maxerror tblock workers batch cigar reps cpu_threads\n";return 2;}
    auto pairs=load(argv[1]);
    omp_set_num_threads(std::stoi(argv[9]));
    cudaFree(0); // Context creation excluded from the library interval, included by process timer.
    size_t free_bytes,total_bytes;cudaMemGetInfo(&free_bytes,&total_bytes);std::cout<<"DEVICE_FREE bytes="<<free_bytes<<" total="<<total_bytes<<std::endl;
    wfagpu_aligner_t a;
    double start=now_ms();nvtxRangePushA("input_prepare");
    if(!wfagpu_initialize_aligner(&a))return 3;
    bool clean=std::getenv("WFA_CLEAN_INPUT")!=nullptr;
    // The upstream add_sequences API does not initialize newly grown metadata
    // or sequence padding. Preallocation with calloc is a software control.
    if(clean){
        size_t bytes=32;for(auto&p:pairs)bytes+=p.first.size()+p.second.size()+16;
        free(a.sequences_buffer);a.sequences_buffer=(char*)calloc(bytes,1);a.sequences_buffer_len=bytes;
        free(a.sequences_metadata);a.sequences_metadata=(sequence_pair_t*)calloc(pairs.size(),sizeof(sequence_pair_t));a.sequences_metadata_len=pairs.size();
        if(!a.sequences_buffer||!a.sequences_metadata)return 7;
    }
    for(auto&p:pairs)if(!wfagpu_add_sequences(&a,p.first.c_str(),p.second.c_str()))return 4;
    size_t dirty_flags=0;for(size_t i=0;i<pairs.size();i++){unsigned char raw;std::memcpy(&raw,&a.sequences_metadata[i].has_N,1);dirty_flags+=raw!=0;}
    if(std::getenv("WFA_CLEAR_FLAGS"))for(size_t i=0;i<pairs.size();i++)a.sequences_metadata[i].has_N=false;
    affine_penalties_t penalties{2,3,1};
    if(!wfagpu_initialize_parameters(&a,penalties))return 5;
    if(std::stoi(argv[3])>0)a.alignment_options.max_error=std::stoi(argv[3]);
    if(std::stoi(argv[4])>0)a.alignment_options.threads_per_block=std::stoi(argv[4]);
    if(std::stoi(argv[5])>0)a.alignment_options.num_workers=std::stoi(argv[5]);
    if(std::stoi(argv[6])>0)wfagpu_set_batch_size(&a,std::stoul(argv[6]));
    a.alignment_options.compute_cigar=std::stoi(argv[7]);
    nvtxRangePop();
    std::cout<<"CONFIG pairs="<<pairs.size()<<" clean_input="<<clean<<" dirty_host_flags="<<dirty_flags<<" prep_ms="<<now_ms()-start<<" max_error="<<a.alignment_options.max_error<<" tblock="<<a.alignment_options.threads_per_block<<" workers="<<a.alignment_options.num_workers<<" batch="<<a.alignment_options.batch_size<<" cigar="<<a.alignment_options.compute_cigar<<std::endl;
    using StatusBegin=int(*)(unsigned,const size_t*);using StatusReset=int(*)();using StatusExport=int(*)(const char*);
    StatusReset status_reset=nullptr;StatusExport status_export=nullptr;const char*status_prefix=getenv("WFA_STATUS_PREFIX");
    if(status_prefix){auto begin=(StatusBegin)dlsym(RTLD_DEFAULT,"wfagpu_status_begin");status_reset=(StatusReset)dlsym(RTLD_DEFAULT,"wfagpu_status_reset");status_export=(StatusExport)dlsym(RTLD_DEFAULT,"wfagpu_status_export");if(!begin||!status_reset||!status_export)return 31;std::vector<size_t> offsets;for(size_t i=0;i<pairs.size();i++)offsets.push_back(a.sequences_metadata[i].pattern_offset);if(begin(pairs.size(),offsets.data()))return 32;}
    const char* audit_prefix=std::getenv("WFA_BT_AUDIT_PREFIX");
    using AuditStart=int(*)(int,int,int,int);using AuditExport=int(*)(const char*);
    AuditExport audit_export=nullptr;
    if(audit_prefix){
        auto audit_start=(AuditStart)dlsym(RTLD_DEFAULT,"wfagpu_bt_audit_begin");
        audit_export=(AuditExport)dlsym(RTLD_DEFAULT,"wfagpu_bt_audit_export");
        if(!audit_start||!audit_export)return 8;
        int target=std::getenv("WFA_BT_AUDIT_TARGET")?std::atoi(std::getenv("WFA_BT_AUDIT_TARGET")):-1;
        if(audit_start(pairs.size(),target,a.alignment_options.max_error,128))return 9;
    }
    using GcBegin=int(*)(int,int,int);using GcReset=int(*)();using GcExport=int(*)(const char*);
    GcReset gc_reset=nullptr;GcExport gc_export=nullptr;
    const char* gc_prefix=getenv("WFA_GC_PREFIX");
    if(gc_prefix){auto begin=(GcBegin)dlsym(RTLD_DEFAULT,"wfagpu_gc_begin");gc_reset=(GcReset)dlsym(RTLD_DEFAULT,"wfagpu_gc_reset");gc_export=(GcExport)dlsym(RTLD_DEFAULT,"wfagpu_gc_export");if(!begin||!gc_reset||!gc_export)return 21;
        start=now_ms();if(begin(pairs.size(),a.alignment_options.num_workers,a.alignment_options.max_error))return 22;std::cout<<"GC_PREP_MS "<<now_ms()-start<<std::endl;}
    for(int r=-1;r<std::stoi(argv[8]);r++){
        // recover_cigar_affine appends to the result. Reset between repeated calls.
        if(a.alignment_options.compute_cigar)for(size_t i=0;i<pairs.size();i++){
            a.results[i].cigar.last_free_position=0;
            a.results[i].cigar.buffer[0]='\0';
        }
        if(status_reset && (status_reset() || cudaDeviceSynchronize()!=cudaSuccess))return 33;
        if(gc_reset && (gc_reset() || cudaDeviceSynchronize()!=cudaSuccess))return 23;
        nvtxRangePushA(r<0?"warmup":"measure_wfagpu");start=now_ms();
        bool ok=wfagpu_align(&a);auto err=cudaDeviceSynchronize();double elapsed=now_ms()-start;nvtxRangePop();
        if(!ok||err!=cudaSuccess){std::cerr<<"GPU_FAILURE "<<cudaGetErrorString(err)<<std::endl;return 6;}
        std::cout<<"ROW "<<r<<" "<<elapsed<<std::endl;
    }
    if(status_export && status_export(status_prefix))return 34;
    if(gc_export && gc_export(gc_prefix))return 24;
    if(audit_export && audit_export(audit_prefix))return 10;
    std::vector<int>scores;for(size_t i=0;i<pairs.size();i++)scores.push_back(a.results[i].error);
    write_scores(argv[2],scores);
    if(a.alignment_options.compute_cigar){std::ofstream out(std::string(argv[2])+".cigar");for(size_t i=0;i<pairs.size();i++)out<<a.results[i].cigar.buffer<<'\n';}
    wfagpu_destroy_aligner(&a);
}
