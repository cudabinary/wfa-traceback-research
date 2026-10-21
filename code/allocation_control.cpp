// Controlled device CUDA API allocation reuse. Algorithm, reset bytes,
// transfers and output contract stay unchanged. cudaFree's completion
// boundary is conservatively retained by cudaDeviceSynchronize on cache mode.
#include <cuda_runtime_api.h>
#include <nvtx3/nvToolsExt.h>
#include <dlfcn.h>
#include <cstdlib>
#include <cstdio>
#include <vector>
#include <cstddef>
struct Entry{void*ptr;size_t bytes;bool host;bool free;};
static std::vector<Entry>& entries(){static auto*p=new std::vector<Entry>;return*p;}
static bool reuse(){static bool r=std::getenv("AUDIT_REUSE")&&std::atoi(std::getenv("AUDIT_REUSE"));return r;}
static size_t dev_live=0,dev_peak=0,dev_reserved=0,dev_reserved_peak=0,host_live=0,host_peak=0;
static unsigned long fresh=0,hits=0,free_calls=0;
template<class F>static F next(const char*name){auto f=(F)dlsym(RTLD_NEXT,name);if(!f){fprintf(stderr,"missing %s\n",name);abort();}return f;}
static cudaError_t allocate(void**ptr,size_t bytes,bool host){
    nvtxRangePushA(host?"cuda_host_allocate_control":"cuda_device_allocate_control");
    if(reuse()&&!host)for(auto&e:entries())if(e.free&&e.host==host&&e.bytes==bytes){
        e.free=false;*ptr=e.ptr;hits++;if(host){host_live+=bytes;host_peak=host_live>host_peak?host_live:host_peak;}else{dev_live+=bytes;dev_peak=dev_live>dev_peak?dev_live:dev_peak;}
        nvtxRangePop();return cudaSuccess;
    }
    if(!host){
        size_t budget=std::getenv("AUDIT_BUDGET_BYTES")?strtoull(std::getenv("AUDIT_BUDGET_BYTES"),nullptr,10):0;
        if(budget)while(dev_reserved+bytes>budget){
            Entry*chosen=nullptr;for(auto&e:entries())if(!e.host&&e.free&&e.ptr&&(!chosen||e.bytes>chosen->bytes))chosen=&e;
            if(!chosen)break;
            static auto free_real=next<cudaError_t(*)(void*)>("cudaFree");auto status=free_real(chosen->ptr);if(status!=cudaSuccess)abort();
            dev_reserved-=chosen->bytes;chosen->ptr=nullptr;chosen->bytes=0;chosen->free=false;
        }
        if(budget&&dev_reserved+bytes>budget){fprintf(stderr,"ALLOC_FAIL kind=policy_budget requested=%zu live=%zu reserved=%zu budget=%zu\n",bytes,dev_live,dev_reserved,budget);exit(90);}
    }
    cudaError_t rc;
    if(host){static auto f=next<cudaError_t(*)(void**,size_t)>("cudaMallocHost");rc=f(ptr,bytes);}
    else{static auto f=next<cudaError_t(*)(void**,size_t)>("cudaMalloc");rc=f(ptr,bytes);}
    if(!host&&rc!=cudaSuccess)fprintf(stderr,"ALLOC_FAIL kind=device_cuda requested=%zu cuda_code=%d cuda_name=%s live=%zu reserved=%zu\n",bytes,(int)rc,cudaGetErrorName(rc),dev_live,dev_reserved);
    if(rc==cudaSuccess){
        entries().push_back({*ptr,bytes,host,false});fresh++;
        if(host){host_live+=bytes;host_peak=host_live>host_peak?host_live:host_peak;}
        else{dev_live+=bytes;dev_peak=dev_live>dev_peak?dev_live:dev_peak;dev_reserved+=bytes;dev_reserved_peak=dev_reserved>dev_reserved_peak?dev_reserved:dev_reserved_peak;}
    }
    nvtxRangePop();return rc;
}
extern "C" cudaError_t cudaMalloc(void**ptr,size_t bytes){return allocate(ptr,bytes,false);}
extern "C" cudaError_t cudaMallocHost(void**ptr,size_t bytes){return allocate(ptr,bytes,true);}
static cudaError_t release(void*ptr,bool host){
    nvtxRangePushA(host?"cuda_host_free_control":"cuda_device_free_control");free_calls++;
    for(auto&e:entries())if(e.ptr==ptr&&e.host==host&&!e.free){
        if(reuse()&&!host){
            static auto sync=next<cudaError_t(*)()>("cudaDeviceSynchronize");auto rc=sync();
            if(rc!=cudaSuccess){nvtxRangePop();return rc;}
            e.free=true;if(host)host_live-=e.bytes;else dev_live-=e.bytes;
            nvtxRangePop();return cudaSuccess;
        }
        e.free=true;if(host)host_live-=e.bytes;else{dev_live-=e.bytes;dev_reserved-=e.bytes;}
        break;
    }
    cudaError_t rc;
    if(host){static auto f=next<cudaError_t(*)(void*)>("cudaFreeHost");rc=f(ptr);}
    else{static auto f=next<cudaError_t(*)(void*)>("cudaFree");rc=f(ptr);}
    nvtxRangePop();return rc;
}
extern "C" cudaError_t cudaFree(void*ptr){return release(ptr,false);}
extern "C" cudaError_t cudaFreeHost(void*ptr){return release(ptr,true);}
__attribute__((destructor))static void summary(){
    fprintf(stderr,"ALLOC_SUMMARY device_reuse=%d fresh=%lu cache_hits=%lu free_calls=%lu device_live_peak_bytes=%zu device_reserved_peak_bytes=%zu pinned_host_tracking=INCOMPLETE\n",reuse(),fresh,hits,free_calls,dev_peak,dev_reserved_peak);
}
