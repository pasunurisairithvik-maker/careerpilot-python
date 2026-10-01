"""Bounded public Ashby boards; no credentials or private posting API."""
import json,urllib.request

def download(slug):
 from .discovery import NoRedirect
 req=urllib.request.Request('https://api.ashbyhq.com/posting-api/job-board/'+slug+'?includeCompensation=true',headers={'Accept':'application/json','User-Agent':'CareerPilot public-job-reader'})
 with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:raw=response.read(12000001)
 if len(raw)>12000000:raise ValueError('Oversized public feed')
 data=json.loads(raw);rows=data.get('jobs')
 if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Invalid public job feed')
 if any(not isinstance(row,dict) or row.get('isListed') is not True for row in rows):raise ValueError('Non-listed posting rejected')
 return rows

def normalize(slug,company,row):
 from .discovery import normalize as common
 if row.get('isListed') is not True:raise ValueError('Non-listed posting rejected')
 description=row.get('descriptionHtml') or row.get('descriptionPlain') or ''
 kind={'FullTime':'Full-time','PartTime':'Part-time','Contract':'Contract','Temporary':'Temporary','Intern':'Internship'}.get(row.get('employmentType'),'')
 if kind:description+='\nEmployer employment type: '+kind
 surrogate={'id':row.get('id'),'title':row.get('title'),'location':{'name':row.get('location','')},'content':description,'absolute_url':row.get('jobUrl') or row.get('applyUrl'),'updated_at':row.get('publishedAt'),'workplaceType':str(row.get('workplaceType','')).lower()}
 compensation=row.get('compensation') or {}
 if isinstance(compensation,dict):surrogate['salaryDescription']=compensation.get('compensationTierSummary','')
 result=common('greenhouse',slug,company,surrogate)
 result.update(provider='ashby',source_key='ashby:'+slug+':'+str(row.get('id')))
 return result
