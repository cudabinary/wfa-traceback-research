"""Source-budget feasibility only. Does not read scores or run an aligner."""
from model import footprint

FAMILIES = {
    'full10': ['gc',16384,1,512,10*2**20,1],
    'full20': ['gc',16384,1,512,20*2**20,1],
    'nogc32': ['guarded',16384,1,512,32*2**20,0],
    'nogc40': ['guarded',16384,1,512,40*2**20,0],
    'nogc4': ['guarded',16384,1,512,4*2**20,0],
}

def fit(pairs, family, budget, ceiling=64):
    cfg=FAMILIES[family].copy()
    one=footprint(pairs,cfg);cfg[2]=2
    per_worker=footprint(pairs,cfg)-one
    workers=min(ceiling,(budget-(one-per_worker))//per_worker)
    if workers<1:raise ValueError('budget cannot accommodate one worker')
    cfg[2]=workers
    predicted=one+(workers-1)*per_worker
    assert predicted<=budget
    return cfg,dict(family=family,workers=workers,predicted_reserved_bytes=predicted,
                    headroom_bytes=budget-predicted,worker_ceiling=ceiling)

def select(pairs, choice, budget):
    import time
    from input_sketch import sketch
    start=time.perf_counter();features={}
    if choice.startswith('family_'):
        family=choice.removeprefix('family_');kind='fixed family, budget-scaled workers'
    elif choice=='length_branch':
        features={'max_length':max(max(map(len,p)) for p in pairs)}
        family='nogc4' if features['max_length']<=10000 else 'full20'
        kind='simple length branch plus budget feasibility'
    elif choice=='policy_joint':
        features=sketch(pairs)
        if features['max_length']<=10000 or features['hit_fraction']>=0.75:family='nogc4'
        else:family='full10' if budget<=3*2**30 else 'full20'
        kind='one-shot length/anchor/budget rule'
    else:raise ValueError(choice)
    # More workers is not assumed faster. Selection favoured W32 over W40
    # for the Full20 family, so its queue pool is capped at 32.
    ceiling=32 if family=='full20' else 64
    cfg,info=fit(pairs,family,budget,ceiling)
    return cfg,dict(kind=kind,choice=choice,features=features,**info,selection_s=time.perf_counter()-start)
