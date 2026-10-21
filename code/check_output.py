from pathlib import Path
import re,sys,json
def load_pairs(p):
 lines=Path(p).read_text().splitlines();assert len(lines)%2==0
 assert all(x[0]==('>' if i%2==0 else '<') for i,x in enumerate(lines))
 return [(lines[i][1:],lines[i+1][1:]) for i in range(0,len(lines),2)]
def check(input_file,score_file,reference=None):
 pairs=load_pairs(input_file);score_file=Path(score_file);scores=[int(x) for x in score_file.read_text().splitlines()];cigars=Path(str(score_file)+'.cigar').read_text().splitlines();assert len(scores)==len(cigars)==len(pairs)
 if reference is not None:assert scores==reference,'optimal score mismatch'
 for idx,((a,b),score,cigar) in enumerate(zip(pairs,scores,cigars)):
  ops=re.findall(r'(\d+)([MXID])',cigar);assert ''.join(n+o for n,o in ops)==cigar and ops,(idx,'parse')
  i=j=cost=0;prev=None
  for ns,o in ops:
   n=int(ns);assert n>0
   if o=='M':assert a[i:i+n]==b[j:j+n];i+=n;j+=n
   elif o=='X':assert len(a[i:i+n])==n and len(b[j:j+n])==n and all(x!=y for x,y in zip(a[i:i+n],b[j:j+n]));i+=n;j+=n;cost+=2*n
   elif o=='I':j+=n;cost+=n+(0 if prev==o else 3)
   else:i+=n;cost+=n+(0 if prev==o else 3)
   assert i<=len(a) and j<=len(b),(idx,'consumption overflow');prev=o
  assert (i,j,cost)==(len(a),len(b),score),(idx,i,j,cost,score)
 return scores
if __name__=='__main__':print(json.dumps({'status':'PASS','pairs':len(check(sys.argv[1],sys.argv[2])),'optimum_reference_checked':False}))
