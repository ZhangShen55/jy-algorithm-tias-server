from pathlib import Path
import argparse,hashlib,json,platform,subprocess,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();data=json.loads(a.summary.read_text());assert data['complete'] and data['completed_cases']==27
a.output.mkdir(parents=True,exist_ok=False)
colors={1:'#1765ad',2:'#de7b1c',4:'#188869'};names={'sync':'Person / face','student':'Student behavior','teacher':'Teacher behavior'}
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'vbas-trt-concurrency-knee-20261121','font.family':'DejaVu Sans'})
plots=[('throughput','successful_tps','Successful images / second',1),('latency','latency_ms.p95','Successful request P95 (seconds)',.001),('latency_p99','latency_ms.p99','Successful request P99 (seconds)',.001),('gpu','gpu_utilization.mean','GPU utilization (%)',1),('cpu','server_cpu_sum_one_core_100.mean','Server CPU sum (one core = 100%)',1),('failures','failure_percent','Failed requests (%)',1)]
manifest=[]
def value(row,key):
 if key=='failure_percent':return 100*(1-row['success_fraction'])
 v=row
 for k in key.split('.'):v=v[k]
 return v
for file,key,ylabel,scale in plots:
 fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
 for ax,name in zip(axes,['sync','student','teacher']):
  all_values=[]
  for i in [1,2,4]:
   rows=sorted([r for r in data['cases'] if r['interface']==name and r['instances']==i],key=lambda r:r['C']);assert [r['C'] for r in rows]==[50,100,200]
   vals=[value(r,key)*scale for r in rows];assert all(v>=0 for v in vals);all_values+=vals
   ax.plot([50,100,200],vals,marker='o',linewidth=2,color=colors[i],label=f'{i} instance(s), {i} worker(s)')
   failed=[(r['C'],v) for r,v in zip(rows,vals) if r['failed']>0]
   if failed:ax.scatter([x for x,y in failed],[y for x,y in failed],s=90,marker='x',color='#c52c3c',linewidths=2,zorder=6,label='Failures observed' if not any(t.get_label()=='Failures observed' for t in ax.collections) else None)
  ax.set_title(names[name]);ax.set_xticks([50,100,200]);ax.set_xlabel('Total client concurrency');ax.set_ylabel(ylabel);ax.set_ylim(0,max(all_values)*1.16 if max(all_values)>0 else 1);ax.grid(alpha=.22)
  assert ax.get_ylim()[1]>=max(all_values)
 handles,labels=axes[0].get_legend_handles_labels();lookup=dict(zip(labels,handles));order=[f'{i} instance(s), {i} worker(s)' for i in [1,2,4]]+['Failures observed'];fig.legend([lookup[k] for k in order],[k for k in order],loc='outside lower center',ncol=4,fontsize=9,frameon=False)
 fig.suptitle('TensorRT FP16 / RTX 3090 / b=512 per worker / queue=0 / 180s / one run per point',fontsize=12)
 for ext in ['png','svg']:
  path=a.output/(file+'.'+ext);fig.savefig(path,dpi=160,metadata={'Creator':'VBAS evidence plotting','Date':None} if ext=='svg' else {'Software':'VBAS evidence plotting'});manifest.append({'file':path.name,'bytes':path.stat().st_size,'sha256':sha(path)})
 plt.close(fig)
(a.output/'requirements.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze','--all'],text=True))
(a.output/'manifest.json').write_text(json.dumps({'summary_sha256':sha(a.summary),'script_sha256':sha(Path(__file__)),'requirements_sha256':sha(a.output/'requirements.txt'),'python':platform.python_version(),'matplotlib':matplotlib.__version__,'files':manifest,'qa':{'cases':27,'series':9,'all_axis_ranges_checked':True,'single_run_no_confidence_intervals':True}},indent=2)+'\n')
print(json.dumps({'figures':len(manifest),'manifest_sha256':sha(a.output/'manifest.json')}))
