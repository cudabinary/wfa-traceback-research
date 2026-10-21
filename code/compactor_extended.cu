#include <cuda_runtime.h>
#include <cstdio>
#include <vector>
#include <set>
#include <cassert>
#include "lib/kernels/sequence_alignment_kernel.cuh"
__device__ static wfa_offset_t get_offset(const wfa_wavefront_t*w,int k,size_t half){int g=k>(int)half||k<-(int)half;k+=half*(k<-(int)half);k-=half*(k>(int)half);return w->offsets[g][k];}
#include "lib/bt_gc.cuh"
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){fprintf(stderr,"CUDA %s\n",cudaGetErrorString(e));return 2;}}while(0)
__global__ void test(wfa_backtrace_t*a,unsigned*head,unsigned*roots,unsigned*result,unsigned stride){
 a+=blockIdx.x*stride;head+=blockIdx.x;roots+=blockIdx.x*60;result+=blockIdx.x*4;
 __shared__ wfa_wavefront_t w[15];__shared__ short offsets[15][4];__shared__ unsigned ptr[15][4],vec[15][4];__shared__ GcShared s;
 unsigned t=threadIdx.x;if(!t){s={};}
 if(t<15){w[t].exist=true;w[t].lo=0;w[t].hi=3;w[t].offsets[0]=offsets[t];w[t].offsets[1]=offsets[t];w[t].backtraces_pointers=ptr[t];w[t].backtraces_vectors=vec[t];for(int k=0;k<4;k++){offsets[t][k]=k==3?-1:0;ptr[t][k]=roots[t*4+k];vec[t][k]=123+t*4+k;}}
 __syncthreads();
 gc_collect(w,w+5,w+10,5,8,head,a,0,7,s,1);
 unsigned once=*head;__syncthreads();
 gc_collect(w,w+5,w+10,5,8,head,a,0,8,s,1);
 if(t<15)for(int k=0;k<4;k++){roots[t*4+k]=ptr[t][k];if(vec[t][k]!=123+t*4+k)atomicAdd(result+2,1);}
 if(!t){result[1]=once!=*head;unsigned id=(*head)++;a[id]={0x77777777u,ptr[0][0]};ptr[0][0]=id;}
 __syncthreads();
 gc_collect(w,w+5,w+10,5,8,head,a,0,9,s,1);
 if(t<15)for(int k=0;k<4;k++)roots[t*4+k]=ptr[t][k];
 if(!t){result[0]=s.failed;result[3]=3;}
}
int main(){
 unsigned cases=0;
 for(unsigned n: {0u,1u,2u,31u,32u,33u,255u,256u,257u,8191u,8192u,8193u})for(int style=0;style<4;style++){
  unsigned H=n+1,stride=H+32;std::vector<wfa_backtrace_t> orig(2*stride);
  std::vector<unsigned> roots(120,0),heads(2,H),r(8),after(120);std::vector<std::set<unsigned>> live(2);std::vector<std::vector<unsigned>> map(2,std::vector<unsigned>(stride));
  for(unsigned b=0;b<2;b++){
   for(unsigned i=1;i<H;i++)orig[b*stride+i]={0x10000000u+i+b*100000,(style==1&&i>1)?i-1:((i>2&&i%2)?i-2:0)};
   for(int t=0;t<15;t++)for(int k=0;k<4;k++)if(n){roots[b*60+t*4+k]=k==3?0xfefefefeu:(style==0?0:(k==0?n:k==1?(n>1?n-1:0):1));}
   if(style==3)for(int t=0;t<15;t++)roots[b*60+t*4+1]=0;
   for(int t=0;t<15;t++)for(int k=0;k<3;k++){unsigned p=roots[b*60+t*4+k];while(p){if(!live[b].insert(p).second)break;p=orig[b*stride+p].prev;}}
   unsigned rank=0;for(auto i:live[b])map[b][i]=++rank;
  }
  wfa_backtrace_t*da;unsigned *dh,*dr,*res;GcCfg cfg={};cfg.words=(stride+31)/32;cfg.cap=stride;
  CK(cudaMalloc(&da,orig.size()*sizeof(*da)));CK(cudaMalloc(&dh,8));CK(cudaMalloc(&dr,480));CK(cudaMalloc(&res,32));CK(cudaMemset(res,0,32));
  CK(cudaMalloc(&cfg.bits,2*cfg.words*4));CK(cudaMalloc(&cfg.rank,2*cfg.words*4));CK(cudaMemcpyToSymbol(gc_cfg,&cfg,sizeof(cfg)));
  CK(cudaMemcpy(da,orig.data(),orig.size()*sizeof(*da),cudaMemcpyHostToDevice));CK(cudaMemcpy(dh,heads.data(),8,cudaMemcpyHostToDevice));CK(cudaMemcpy(dr,roots.data(),480,cudaMemcpyHostToDevice));
  test<<<2,256>>>(da,dh,dr,res,stride);CK(cudaDeviceSynchronize());std::vector<wfa_backtrace_t> nodes(orig.size());
  CK(cudaMemcpy(r.data(),res,32,cudaMemcpyDeviceToHost));CK(cudaMemcpy(heads.data(),dh,8,cudaMemcpyDeviceToHost));CK(cudaMemcpy(after.data(),dr,480,cudaMemcpyDeviceToHost));CK(cudaMemcpy(nodes.data(),da,nodes.size()*sizeof(*da),cudaMemcpyDeviceToHost));
  for(unsigned b=0;b<2;b++){
   assert(!r[b*4]&&!r[b*4+1]&&!r[b*4+2]&&r[b*4+3]==3&&heads[b]==live[b].size()+2);
   for(int t=0;t<15;t++)for(int k=0;k<4;k++)assert(after[b*60+t*4+k]==(t==0&&k==0?live[b].size()+1:k==3?0:map[b][roots[b*60+t*4+k]]));
   for(auto id:live[b]){auto z=nodes[b*stride+map[b][id]];assert(z.backtrace==orig[b*stride+id].backtrace&&z.prev==map[b][orig[b*stride+id].prev]);}
   auto appended=nodes[b*stride+live[b].size()+1];assert(appended.backtrace==0x77777777u&&appended.prev==map[b][roots[b*60]]);
   for(unsigned id=heads[b];id<stride;id++){if(id>=H)assert(nodes[b*stride+id].backtrace==orig[b*stride+id].backtrace);}
  }
  cudaFree(da);cudaFree(dh);cudaFree(dr);cudaFree(res);cudaFree(cfg.bits);cudaFree(cfg.rank);cases+=2;
 }
 printf("EXTENDED_COMPACTOR PASS worker_cases=%u actual_collections=%u workers_per_launch=2 append_after_remap=1 empty_H1=1 invalid_offset_poison=1\n",cases,cases*3);
}
