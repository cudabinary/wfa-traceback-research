// Bounded observation only. No scheduling, GC trigger, or alignment changes.
#include <vector>
#include <ctime>
#include <climits>
struct ExpCheck {unsigned long long ns;int score,steps;unsigned head;int lo,hi;unsigned reserved;};
struct ExpGc {unsigned long long begin,end;unsigned cycles[5];unsigned score,before,live,after,prefix;unsigned long long generated;};
struct ExpPair {unsigned long long begin,end;unsigned worker,sm,reason,calls,mask,overflow;unsigned long long generated;unsigned previous_occupied;ExpCheck cp[3];ExpGc gc[128];};
static_assert(sizeof(ExpCheck)==32 && sizeof(ExpGc)==64 && sizeof(ExpPair)==8344,"trace ABI");
struct ExpCfg {ExpPair* rows;unsigned enabled,n;};
__device__ ExpCfg exp_cfg;static ExpCfg exp_host={};
struct ExpCpu {unsigned long long times[4];int thread;};
static std::vector<ExpCpu> exp_cpu;static FILE*exp_file=nullptr;
struct ExpCuda {cudaEvent_t begin,end;};static std::vector<ExpCuda> exp_cuda;
extern "C" void wfagpu_exp_cuda_event(int which,int batch,void*stream){if(exp_host.enabled){auto&e=exp_cuda[batch];run_check(cudaEventRecord(which?e.end:e.begin,(cudaStream_t)stream));}}
static unsigned long long exp_now(){timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (unsigned long long)t.tv_sec*1000000000ull+t.tv_nsec;}
extern "C" void wfagpu_exp_event(const char*kind,int batch,int from,int count,int value){if(exp_file)fprintf(exp_file,"%llu,%s,%d,%d,%d,%d\n",exp_now(),kind,batch,from,count,value);}
extern "C" void wfagpu_exp_cpu_mark(int pair,int stage,unsigned long long ns,int thread){if(exp_host.enabled && pair>=0 && (unsigned)pair<exp_host.n){exp_cpu[pair].times[stage]=ns;exp_cpu[pair].thread=thread;}}
static void exp_begin(unsigned n){
 exp_host.n=n;exp_host.enabled=getenv("WFA_EXPERIMENT_TRACE")?atoi(getenv("WFA_EXPERIMENT_TRACE")):0;
 if((size_t)n*sizeof(ExpPair)>128ull*1024*1024){fprintf(stderr,"TRACE_CAP_FAILURE\n");exit(51);}
 run_check(cudaMalloc(&exp_host.rows,(size_t)n*sizeof(ExpPair)));
 run_check(cudaMemcpyToSymbol(exp_cfg,&exp_host,sizeof(exp_host)));
 if(exp_host.enabled){exp_cpu.resize(n);exp_cuda.resize((n+511)/512);for(auto&e:exp_cuda){run_check(cudaEventCreate(&e.begin));run_check(cudaEventCreate(&e.end));}char path[4096];snprintf(path,sizeof(path),"%s.host_events.csv",getenv("WFA_STATUS_PREFIX"));exp_file=fopen(path,"w");if(!exp_file)exit(52);fprintf(exp_file,"host_ns,event,batch,from,count,value\n");wfagpu_exp_event("trace_begin",-1,0,n,0);}
 fprintf(stderr,"EXP_TRACE enabled=%u row_bytes=%zu reserved_bytes=%zu\n",exp_host.enabled,sizeof(ExpPair),(size_t)n*sizeof(ExpPair));
}
__device__ __forceinline__ unsigned long long exp_ns(){unsigned long long t;asm volatile("mov.u64 %0, %%globaltimer;":"=l"(t));return t;}
__device__ __forceinline__ void exp_start(unsigned p){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];unsigned sm;asm volatile("mov.u32 %0, %%smid;":"=r"(sm));r.worker=blockIdx.x;r.sm=sm;r.begin=exp_ns();}}
__device__ __forceinline__ void exp_end(unsigned p,unsigned reason){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];r.reason=reason;r.end=exp_ns();}}
__device__ __forceinline__ void exp_check(unsigned p,int score,int steps,unsigned head,unsigned cap,int lo,int hi){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];unsigned stored=min(head,cap-1);if(stored<r.previous_occupied)r.overflow|=4;else r.generated+=(unsigned long long)(stored-r.previous_occupied);r.previous_occupied=stored;for(unsigned j=0;j<3;j++)if(!(r.mask&(1u<<j)) && head>=(cap/4)*(j+1)){r.cp[j]={exp_ns(),score,steps,head,lo,hi,0};r.mask|=1u<<j;}}}
__device__ __forceinline__ void exp_gc_begin(unsigned p,unsigned score,unsigned h,unsigned prefix){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];unsigned i=r.calls++;if(i<128){auto&e=r.gc[i];e.begin=exp_ns();e.score=score;e.before=h;e.prefix=prefix;e.generated=r.generated;}else r.overflow|=1;}}
__device__ __forceinline__ void exp_gc_phase(unsigned p,unsigned phase,unsigned long long cycles){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];if(r.calls && r.calls<=128){r.gc[r.calls-1].cycles[phase]=cycles>UINT_MAX?UINT_MAX:(unsigned)cycles;if(cycles>UINT_MAX)r.overflow|=2;}}}
__device__ __forceinline__ void exp_gc_end(unsigned p,unsigned live){if(exp_cfg.enabled && !threadIdx.x){auto&r=exp_cfg.rows[p];r.previous_occupied=live;if(r.calls && r.calls<=128){auto&e=r.gc[r.calls-1];e.live=live;e.after=live;e.end=exp_ns();}}}
extern "C" int wfagpu_exp_export(const char*prefix){
 if(!exp_host.enabled)return 0;
 wfagpu_exp_event("trace_copy_begin",-1,0,exp_host.n,0);
 std::vector<ExpPair> rows(exp_host.n);run_check(cudaMemcpy(rows.data(),exp_host.rows,rows.size()*sizeof(ExpPair),cudaMemcpyDeviceToHost));
 wfagpu_exp_event("trace_rows_host_visible",-1,0,exp_host.n,0);
 char cpath[4096];snprintf(cpath,sizeof(cpath),"%s.batch_cuda_events.csv",prefix);FILE*cf=fopen(cpath,"w");if(!cf)return 53;fprintf(cf,"batch,cuda_event_ms\n");for(unsigned b=0;b<exp_cuda.size();b++){float ms=0;run_check(cudaEventElapsedTime(&ms,exp_cuda[b].begin,exp_cuda[b].end));fprintf(cf,"%u,%.9f\n",b,ms);}fclose(cf);
 char path[4096];snprintf(path,sizeof(path),"%s.pair_events.csv",prefix);FILE*f=fopen(path,"w");if(!f)return 53;
 fprintf(f,"gpu_index,batch,worker,sm,start_device_ns,end_device_ns,reason,gc_calls,overflow,cumulative_generated,final_occupied\n");
 for(unsigned i=0;i<rows.size();i++){auto&r=rows[i];fprintf(f,"%u,%u,%u,%u,%llu,%llu,%u,%u,%u,%llu,%u\n",i,i/512,r.worker,r.sm,r.begin,r.end,r.reason,r.calls,r.overflow,r.generated,r.previous_occupied);}fclose(f);
 snprintf(path,sizeof(path),"%s.signal_events.csv",prefix);f=fopen(path,"w");if(!f)return 53;fprintf(f,"gpu_index,threshold_quarters,device_ns,score,steps,head,wf_lo,wf_hi\n");
 for(unsigned i=0;i<rows.size();i++)for(unsigned j=0;j<3;j++)if(rows[i].mask&(1u<<j)){auto&e=rows[i].cp[j];fprintf(f,"%u,%u,%llu,%d,%d,%u,%d,%d\n",i,j+1,e.ns,e.score,e.steps,e.head,e.lo,e.hi);}fclose(f);
 snprintf(path,sizeof(path),"%s.gc_events.csv",prefix);f=fopen(path,"w");if(!f)return 53;fprintf(f,"gpu_index,event,start_device_ns,end_device_ns,score,head_before,live_after_rank,head_after,prefix,clear_cycles,mark_cycles,rank_cycles,compact_cycles,remap_cycles,cumulative_generated\n");
 for(unsigned i=0;i<rows.size();i++)for(unsigned j=0;j<rows[i].calls && j<128;j++){auto&e=rows[i].gc[j];fprintf(f,"%u,%u,%llu,%llu,%u,%u,%u,%u,%u",i,j,e.begin,e.end,e.score,e.before,e.live,e.after,e.prefix);for(int k=0;k<5;k++)fprintf(f,",%u",e.cycles[k]);fprintf(f,",%llu\n",e.generated);}fclose(f);
 snprintf(path,sizeof(path),"%s.cpu_events.csv",prefix);f=fopen(path,"w");if(!f)return 53;fprintf(f,"gpu_index,batch,thread,rescue_start_host_ns,rescue_end_host_ns,cigar_start_host_ns,cigar_end_host_ns\n");
 for(unsigned i=0;i<exp_cpu.size();i++){auto&r=exp_cpu[i];fprintf(f,"%u,%u,%d,%llu,%llu,%llu,%llu\n",i,i/512,r.thread,r.times[0],r.times[1],r.times[2],r.times[3]);}fclose(f);
 wfagpu_exp_event("trace_export_done",-1,0,exp_host.n,0);fclose(exp_file);exp_file=nullptr;return 0;
}
