"""Score kNN vs linear head on the frozen challenge sets A and B using stored vectors. python3 -I head_frozen.py"""
import json, csv, numpy as np, collections
from sklearn.linear_model import LogisticRegression
def load(p):
    m=json.load(open(p+'.json'));v=np.fromfile(p+'.f32',dtype=np.float32).reshape(len(m['items']),m['dim']);v/=np.linalg.norm(v,axis=1,keepdims=True);return v,m['items']
def truth(p): return {r['case_id']:r['ground_truth_id'] for r in csv.DictReader(open(p))}
def knn(rv,rt,rs,Q,k=50,cap=3,T=0.05):
    out=[];S=Q@rv.T
    for sims in S:
        order=np.argsort(-sims)[:k];seen=set();per=collections.defaultdict(list)
        for i in order:
            if rs[i] in seen: continue
            seen.add(rs[i])
            if len(per[rt[i]])<cap: per[rt[i]].append(sims[i])
        top=max(max(v) for v in per.values());sc={t:sum(np.exp((x-top)/T) for x in v) for t,v in per.items()}
        out.append([t for t,_ in sorted(sc.items(),key=lambda x:-x[1])[:3]])
    return out
def head(rv,rt,rs,Q,C,sw=None):
    clf=LogisticRegression(C=C,max_iter=400);clf.fit(rv,rt,sample_weight=sw)
    return [[clf.classes_[j] for j in np.argsort(-r)[:3]] for r in clf.predict_proba(Q)]
def specw(rt,rs):
    # each specimen carries equal weight within its class, each class equal weight overall
    cnt=collections.Counter(rs);cls=collections.Counter(rt)
    spc=collections.defaultdict(set)
    for t,s in zip(rt,rs): spc[t].add(s)
    return np.array([1.0/cnt[s]/len(spc[t]) for t,s in zip(rt,rs)])*len(rt)/len(cls)
tA,tB=truth('/tmp/ch_a.csv'),truth('/tmp/ch_b.csv')
def acc(pred,ids,t):
    y=[t[i] for i in ids];n=len(y);return f"{sum(p[0]==a for p,a in zip(pred,y))/n:.3f}/{sum(a in p for p,a in zip(pred,y))/n:.3f}"
for name,d in [('21 live + Kaggle (23 classes)','/tmp/embK'),('21 + Kaggle + 76 museum (99)','/tmp/embA')]:
    rv,items=load(d+'/reference_private');rt=np.array([i['t'] for i in items]);rs=np.array([i['s'] for i in items])
    print('\n',name,len(rt),'photos')
    qa,ia=load(d+'/challenge');qb,ib=load(d+'/challenge_b');ida=[i['id'] for i in ia];idb=[i['id'] for i in ib]
    sw=specw(rt,rs)
    runs={'kNN now':lambda Q:knn(rv,rt,rs,Q),**{f'head C={c}':(lambda Q,c=c:head(rv,rt,rs,Q,c)) for c in (1,10,100)},'head C=10 specimen-weighted':lambda Q:head(rv,rt,rs,Q,10,sw)}
    for k,f in runs.items(): print(f'  {k:30} A {acc(f(qa),ida,tA)}  B {acc(f(qb),idb,tB)}   (top1/top3)')
