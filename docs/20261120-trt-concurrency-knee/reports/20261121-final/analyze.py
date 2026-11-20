"""Offline raw-request/resource reanalysis of the fixed 27-case campaign."""
from pathlib import Path
import argparse,collections,csv,hashlib,json,math,statistics,sys

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for x in iter(lambda:stream.read(1<<20),b''):h.update(x)
 return h.hexdigest()
def percentile(v,q):
 if not v:return None
 v=sorted(v);at=(len(v)-1)*q;lo=int(at);hi=min(lo+1,len(v)-1);return v[lo]+(v[hi]-v[lo])*(at-lo)
def describe(v):
 v=[x for x in v if x is not None]
 return dict(samples=len(v),mean=statistics.mean(v),median=statistics.median(v),min=min(v),max=max(v)) if v else dict(samples=0,mean=None,median=None,min=None,max=None)
def numeric(s):
 try:return float(s.strip())
 except ValueError:return None

def analyze(root,output,partial=False,continuations=None):
 assert not output.exists();plan=json.loads((root/'plan.json').read_text());assert len(plan['jobs'])==27
 contract=None;openapi_files=0;result=[];expected={j['label'] for j in plan['jobs']};locations={}
 for source in [root]+list(continuations or []):
  child_plan=json.loads((source/'plan.json').read_text());assert child_plan['code']==plan['code']
  for key in ['source_sha256','engine_manifest_sha256','engines','config_source_sha256','pools','seed','gpu_uuid']:assert child_plan[key]==plan[key],key
  assert all(j in plan['jobs'] for j in child_plan['jobs'])
  for p in source.glob('*/case-result.json'):
   assert p.parent.name not in locations;locations[p.parent.name]=p.parent
 actual=set(locations)
 if not partial:assert actual==expected
 assert actual<=expected
 for job in plan['jobs']:
  if job['label'] not in actual:continue
  folder=locations[job['label']]
  case=json.loads((folder/'case-result.json').read_text());assert case['job']==job and case['returncode']==0 and case['openapi_captured']
  summary=json.loads((folder/'load/summary.json').read_text());raw=[json.loads(line) for line in (folder/'load/requests.jsonl').read_text().splitlines()];good=[r for r in raw if r['valid']];failed=[r for r in raw if not r['valid']]
  assert case['validation']['summary']==summary
  assert len(raw)==summary['requests'] and len(good)==summary['successful'] and len(failed)==summary['failed']
  assert len({r['sequence'] for r in raw})==len(raw) and {r['sequence'] for r in raw}==set(range(len(raw)))
  assert all(0<=r['sent_offset_s']<180 and r['completed_offset_s']>=r['sent_offset_s'] and r['latency_ms']>=0 for r in raw)
  completed=sum(r['completed_offset_s']<=180 for r in good);tps=completed/180
  assert tps==summary['success_images_per_s_in_window']
  lat=[r['latency_ms'] for r in good];metrics={k:percentile(lat,q) for k,q in [('p50',.5),('p95',.95),('p99',.99)]};metrics['mean']=statistics.mean(lat) if lat else None
  assert metrics==summary['successful_image_latency_ms']
  instances=json.loads((folder/'instances.json').read_text());assert len(instances['pids'])==job['instances'];assert instances['max_batches']==512 and instances['queue_size']==0
  specs=sorted(folder.glob('runtime-openapi-*.json'));assert len(specs)==job['instances']
  for path in specs:
   spec=json.loads(path.read_text());current=dict(paths=spec['paths'],components=spec.get('components',{}));assert len(current['paths'])==7
   if contract is None:contract=current
   assert contract==current;openapi_files+=1
  assert not case['validation']['critical_logs']
  failure_groups=collections.defaultdict(list)
  for row in failed:
   available=[str(e['errno']) for e in row.get('error_chain',[]) if 'errno' in e];key=row.get('error_type','http_'+str(row.get('status')))+'|errno='+(','.join(available) if available else 'unavailable');failure_groups[key].append(row)
  failure_evidence={key:dict(count=len(rows),completed_offset_s=describe([r['completed_offset_s'] for r in rows]),latency_ms=describe([r['latency_ms'] for r in rows]),per_instance=dict(collections.Counter(r['instance'] for r in rows)),reachable_chain_types=dict(collections.Counter(' -> '.join(e['type'] for e in r.get('error_chain',[])) for r in rows))) for key,rows in failure_groups.items()}
  per_url={u:dict(requests=sum(r['instance']==u for r in raw),successful=sum(r['instance']==u for r in good),failed=sum(r['instance']==u for r in failed)) for u in instances['urls']}
  start=summary['started_unix_time'];samples=[];pidvalues=collections.defaultdict(lambda:dict(role=None,cpu=[],rss=[]));gmem=[];gutil=[];gtemp=[];gpower=[];servercpu=[];serverrss=[];clientcpu=[];clientrss=[]
  with (folder/'resources.csv').open() as stream:
   for row in csv.DictReader(stream):
    ts=float(row['unix_time'])
    if not start<=ts<=start+180:continue
    stats=json.loads(row['process_stats_json']);samples.append(ts)
    gpu=[numeric(s) for s in row['gpu_query'].split(',')]
    assert len(gpu)>=5
    for arr,v in zip([gmem,gutil,gtemp,gpower],gpu[:4]):
     if v is not None:arr.append(v)
    sums=collections.defaultdict(lambda:dict(cpu=0.,rss=0.,has_cpu=False))
    for s in stats:
     p=pidvalues[str(s['pid'])];p['role']=s['role'];p['rss'].append(s['rss_kib']/1024)
     if s['cpu_percent_one_core_100'] is not None:p['cpu'].append(s['cpu_percent_one_core_100']);sums[s['role']]['cpu']+=s['cpu_percent_one_core_100'];sums[s['role']]['has_cpu']=True
     sums[s['role']]['rss']+=s['rss_kib']/1024
    for role,cp,mem in [('server',servercpu,serverrss),('load_generator',clientcpu,clientrss)]:
     if sums[role]['has_cpu']:cp.append(sums[role]['cpu'])
     mem.append(sums[role]['rss'])
  assert len(samples)>=150 and {int(k) for k,v in pidvalues.items() if v['role']=='server'}==set(instances['pids'])
  assert all(len(v['cpu'])>=150 for v in pidvalues.values())
  images=collections.Counter(r['image_id'] for r in raw);window_inflight=sum(r['completed_offset_s']>180 for r in raw)
  statuses=collections.Counter(str(r.get('status')) for r in raw);errors=collections.Counter(r.get('error','http_'+str(r.get('status'))) for r in failed)
  log_counts={}
  for i,url in enumerate(instances['urls']):
   log=folder/('instance-'+url.rsplit(':',1)[1]+'.log');text=log.read_text();endpoint=summary['endpoint'];assert not any(term in text for term in ['Traceback','CUDA out of memory','CUDA error','NMS time limit','out of memory'])
   access=sum('"POST '+endpoint+' HTTP/1.1" 200 OK' in line for line in text.splitlines());assert access>=per_url[url]['successful']
   log_counts[url]=dict(http_200_including_prefill_and_warmup=access,formal_success=per_url[url]['successful'])
  events=list(map(json.loads,(folder/'events.jsonl').read_text().splitlines()));assert events[-1]['event']=='cleanup_complete'
  result.append(dict(label=job['label'],interface=job['name'],endpoint=summary['endpoint'],instances=job['instances'],workers_per_instance=1,total_workers=job['instances'],C=job['concurrency'],b=512,queue=0,window_seconds=180,started_unix=start,requests=len(raw),successful=len(good),failed=len(failed),completed_in_window=completed,inflight_at_window_end=window_inflight,successful_tps=tps,success_fraction=len(good)/len(raw),latency_ms=metrics,failed_latency_ms_p95=percentile([r['latency_ms'] for r in failed],.95),status_counts=dict(statuses),errors=dict(errors),failure_evidence=failure_evidence,drain_seconds=max(0,summary['elapsed_including_drain_s']-180),unique_images=len(images),pool_images=plan['pools'][job['name']]['files'],image_frequency=dict(min=min(images.values()),max=max(images.values())),resource_samples=len(samples),gpu_memory_mib=describe(gmem),gpu_utilization=describe(gutil),gpu_temperature_c=describe(gtemp),gpu_power_w=describe(gpower),server_cpu_sum_one_core_100=describe(servercpu),server_rss_sum_mib=describe(serverrss),generator_cpu_one_core_100=describe(clientcpu),generator_rss_mib=describe(clientrss),per_pid={k:dict(role=v['role'],cpu=describe(v['cpu']),rss_mib=describe(v['rss'])) for k,v in pidvalues.items()},per_instance=per_url,access_log_check=log_counts,requests_sha256=sha(folder/'load/requests.jsonl'),summary_sha256=sha(folder/'load/summary.json'),case_result_sha256=sha(folder/'case-result.json'),resources_sha256=sha(folder/'resources.csv')))
 slopes=[]
 for name in ['sync','student','teacher']:
  for i in [1,2,4]:
   cases=sorted([r for r in result if r['interface']==name and r['instances']==i],key=lambda r:r['C'])
   if len(cases)!=3:continue
   deltas=[]
   for a,b in zip(cases,cases[1:]):
    gain=b['successful_tps']/a['successful_tps']-1;p95=b['latency_ms']['p95']/a['latency_ms']['p95']-1
    deltas.append(dict(from_C=a['C'],to_C=b['C'],tps_gain_fraction=gain,p95_change_fraction=p95,platform_candidate=gain<.05 and (p95>0 or b['success_fraction']<a['success_fraction'] or b['gpu_utilization']['mean']>a['gpu_utilization']['mean'])))
   slopes.append(dict(interface=name,instances=i,steps=deltas,scope='single_run_grid_candidate_not_exact_knee_or_causal_peak'))
 out=dict(schema_version=1,run_id=root.name,continuation_runs=[p.name for p in continuations or []],planned_cases=27,completed_cases=len(result),complete=actual==expected,code=plan['code'],plan_sha256=sha(root/'plan.json'),analyzer_sha256=sha(Path(__file__)),runtime_openapi_files=openapi_files,runtime_openapi_contract_equal=True,method='closed_loop_single_image_total_C_success_completed_in_180s_no_retries',b512_user_authorized=True,statistics_scope='success_latency_all_sent_in_formal_window_including_drain; resources_formal_window_only',cases=result,marginal_gains=slopes,limitations=['one_run_per_point_no_repeat_confidence_intervals','only_C50_100_200_no_exact_sub50_knee','no_production_latency_SLO','b512_not_comparable_to_old_b1_as_isolated_factor','single_generator_can_limit_offered_load','resource_CPU_one_core_100_not_whole_host'])
 output.mkdir(parents=True,exist_ok=False);(output/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 fields=['interface','instances','workers_per_instance','total_workers','C','b','queue','requests','successful','failed','completed_in_window','successful_tps','p50_ms','p95_ms','p99_ms','mean_ms','gpu_memory_peak_mib','gpu_util_mean','server_cpu_mean','server_rss_peak_mib','generator_cpu_mean','unique_images','inflight_at_window_end','drain_seconds']
 with (output/'metrics.csv').open('w') as stream:
  w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
  for r in result:
   row={k:r[k] for k in fields if k in r};row.update(p50_ms=r['latency_ms']['p50'],p95_ms=r['latency_ms']['p95'],p99_ms=r['latency_ms']['p99'],mean_ms=r['latency_ms']['mean'],gpu_memory_peak_mib=r['gpu_memory_mib']['max'],gpu_util_mean=r['gpu_utilization']['mean'],server_cpu_mean=r['server_cpu_sum_one_core_100']['mean'],server_rss_peak_mib=r['server_rss_sum_mib']['max'],generator_cpu_mean=r['generator_cpu_one_core_100']['mean']);w.writerow(row)
 print(json.dumps(dict(completed_cases=len(result),complete=out['complete'],successful=sum(r['successful'] for r in result),failed=sum(r['failed'] for r in result),summary_sha256=sha(output/'summary.json')),ensure_ascii=False))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--partial',action='store_true');p.add_argument('--continuation',type=Path,nargs='*');a=p.parse_args();analyze(a.input,a.output,a.partial,a.continuation)
