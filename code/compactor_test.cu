#include <cuda_runtime.h>
#include <cstdio>
#include <vector>
#include <set>
#include <cassert>
#include "lib/kernels/sequence_alignment_kernel.cuh"
__device__ static wfa_offset_t get_offset(const wfa_wavefront_t*w,int k,size_t half){int g=k>(int)half||k<-(int)half;k+=half*(k<-(int)half);k-=half*(k>(int)half);return w->offsets[g][k];}
#include "lib/bt_gc.cuh"
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){fprintf(stderr,"CUDA %s\n",cudaGetErrorString(e));return 2;}}while(0)
__global__ void test(wfa_backtrace_t*a,unsigned*head,unsigned*roots,unsigned*result){
 __shared__ wfa_wavefront_t w[15];__shared__ short offsets[15][4];__shared__ unsigned ptr[15][4],vec[15][4];__shared__ GcShared s;
 unsigned t=threadIdx.x;if(!t){s={};}
 if(t<15){w[t].exist=true;w[t].lo=0;w[t].hi=3;w[t].offsets[0]=offsets[t];w[t].offsets[1]=offsets[t];w[t].backtraces_pointers=ptr[t];w[t].backtraces_vectors=vec[t];for(int k=0;k<4;k++){offsets[t][k]=k==3?-1:0;ptr[t][k]=roots[t*4+k];vec[t][k]=123+t*4+k;}}
 __syncthreads();
 gc_collect(w,w+5,w+10,5,8,head,a,0,7,s,1);
 unsigned once=*head;__syncthreads();
 gc_collect(w,w+5,w+10,5,8,head,a,0,8,s,1);
 if(t<15)for(int k=0;k<4;k++){roots[t*4+k]=ptr[t][k];if(vec[t][k]!=123+t*4+k)atomicAdd(result+2,1);}
 if(!t){result[0]=s.failed;result[1]=once!=*head;result[3]=2;}
}
int main(){
 unsigned cases=0;
 for(unsigned n: {1u,2u,31u,32u,33u,255u,256u,257u,8191u,8192u,8193u})for(int style=0;style<3;style++){
  unsigned H=n+1;std::vector<wfa_backtrace_t> orig(H);for(unsigned i=1;i<H;i++)orig[i]={0x10000000u+i,(i>2&&i%2)?i-2:0};
  std::vector<unsigned> roots(60,0);for(int t=0;t<15;t++)for(int k=0;k<3;k++)if(style)roots[t*4+k]=(style==1?0u:(k==0?n:k==1?(n>1?n-1:0):1));
  std::set<unsigned> live;for(int t=0;t<15;t++)for(int k=0;k<3;k++){unsigned p=roots[t*4+k];while(p){if(!live.insert(p).second)break;p=orig[p].prev;}}
  std::vector<unsigned> map(H);unsigned rank=0;for(auto i:live)map[i]=++rank;
  wfa_backtrace_t* da;unsigned *dh,*dr,*res;GcCfg cfg={};cfg.words=(H+31)/32;cfg.cap=H+32;
  CK(cudaMalloc(&da,H*sizeof(*da)));CK(cudaMalloc(&dh,4));CK(cudaMalloc(&dr,240));CK(cudaMalloc(&res,16));CK(cudaMemset(res,0,16));
  CK(cudaMalloc(&cfg.bits,cfg.words*4));CK(cudaMalloc(&cfg.rank,cfg.words*4));CK(cudaMemcpyToSymbol(gc_cfg,&cfg,sizeof(cfg)));
  CK(cudaMemcpy(da,orig.data(),H*sizeof(*da),cudaMemcpyHostToDevice));CK(cudaMemcpy(dh,&H,4,cudaMemcpyHostToDevice));CK(cudaMemcpy(dr,roots.data(),240,cudaMemcpyHostToDevice));
  test<<<1,256>>>(da,dh,dr,res);CK(cudaDeviceSynchronize());unsigned r[4],head;std::vector<unsigned> after(60);std::vector<wfa_backtrace_t> nodes(H);
  CK(cudaMemcpy(r,res,16,cudaMemcpyDeviceToHost));CK(cudaMemcpy(&head,dh,4,cudaMemcpyDeviceToHost));CK(cudaMemcpy(after.data(),dr,240,cudaMemcpyDeviceToHost));CK(cudaMemcpy(nodes.data(),da,H*sizeof(*da),cudaMemcpyDeviceToHost));
  assert(!r[0]&&!r[1]&&!r[2]&&r[3]==2&&head==live.size()+1);
  for(int t=0;t<15;t++)for(int k=0;k<4;k++)assert(after[t*4+k]==(k==3?0:map[roots[t*4+k]]));
  for(auto id:live){auto z=nodes[map[id]];assert(z.backtrace==orig[id].backtrace&&z.prev==map[orig[id].prev]);}
  cudaFree(da);cudaFree(dh);cudaFree(dr);cudaFree(res);cudaFree(cfg.bits);cudaFree(cfg.rank);cases++;
 }
 printf("COMPACTOR PASS cases=%u actual_collections=%u null_shared_roots_boundaries=1\n",cases,cases*2);
}
