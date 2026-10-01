"""Fixed US internship-query feeds from the public SmartRecruiters Posting API."""
import json,re,urllib.request
from concurrent.futures import ThreadPoolExecutor

def read(url):
 from .discovery import NoRedirect
 req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'CareerPilot public-job-reader'})
 with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:raw=response.read(2000001)
 if len(raw)>2000000:raise ValueError('Oversized posting response')
 return json.loads(raw)

def download(slug):
 base='https://api.smartrecruiters.com/v1/companies/'+slug+'/postings'
 rows=[];total=None
 for offset in (0,100):
  page=read(base+'?country=us&q=intern&limit=100&offset='+str(offset))
  if not isinstance(page,dict) or not isinstance(page.get('content'),list):raise ValueError('Invalid public posting list')
  count=page.get('totalFound')
  if not isinstance(count,int) or count>200:raise ValueError('Public feed exceeds 200-posting bound')
  if total is not None and count!=total:raise ValueError('Posting list changed while paging; retry next refresh')
  total=count;rows.extend(page['content'])
  if len(rows)>=total:break
 if len(rows)!=total:raise ValueError('Incomplete public posting list')
 def details(row):
  identifier=str(row.get('id',''))
  if not re.fullmatch(r'[a-zA-Z0-9-]+',identifier):raise ValueError('Invalid posting ID')
  detail=read(base+'/'+identifier)
  if detail.get('visibility') not in (None,'PUBLIC'):raise ValueError('Non-public posting rejected')
  return detail
 with ThreadPoolExecutor(max_workers=4) as pool:return list(pool.map(details,rows))

def normalize(slug,company,row):
 from .discovery import plain,normalize as common
 location=row.get('location') or {}
 sections=(row.get('jobAd') or {}).get('sections') or {}
 description='\n'.join(str(s.get('title',''))+'\n'+str(s.get('text','')) for s in sections.values() if isinstance(s,dict))
 employment=row.get('typeOfEmployment') or {}
 if isinstance(employment,dict) and employment.get('label'):description+='\nEmployer employment type: '+str(employment['label'])
 arrangement='hybrid' if location.get('hybrid') else 'remote' if location.get('remote') else ''
 surrogate={'id':row.get('id'),'title':row.get('name'),'location':{'name':location.get('fullLocation') or ', '.join(str(location.get(k,'')) for k in ('city','region','country'))},'content':description,'absolute_url':row.get('postingUrl') or row.get('applyUrl'),'updated_at':row.get('releasedDate'),'workplaceType':arrangement}
 result=common('greenhouse',slug,company,surrogate)
 result['provider']='smartrecruiters';result['source_key']='smartrecruiters:'+slug+':'+str(row.get('id'))
 return result
