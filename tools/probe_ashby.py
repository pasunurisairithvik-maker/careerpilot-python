"""Read-only probe of fixed public Ashby boards. Never reads account data."""
import json,urllib.request
for slug in ('notion','ramp','deel','zapier'):
 try:
  with urllib.request.urlopen('https://api.ashbyhq.com/posting-api/job-board/'+slug+'?includeCompensation=true',timeout=15) as r:
   data=json.loads(r.read(12000001))
  jobs=[j for j in data.get('jobs',[]) if j.get('isListed') is not False]
  print(slug,len(jobs),'public listings')
 except Exception as e:print(slug,type(e).__name__,str(e))
