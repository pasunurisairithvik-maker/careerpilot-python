"""Listing traits from explicit JD statements; never infer missing eligibility."""
import re
from .job_presentation import experience_requirement

def level(title,description):
 from .discovery import seniority
 titled=seniority(title)
 if titled=='intern':return titled
 if re.search(r'\b(?:director|head of|vice president|vp|chief|manager)\b',title,re.I):return 'management'
 requirement=experience_requirement(description)
 if requirement:
  years=requirement['years']
  return 'entry' if years<=2 else 'mid' if years<=5 else 'senior'
 return titled

def workplace(location,description,metadata=''):
 text='\n'.join([location or '',description or ''])
 patterns={
  'hybrid':r'\bhybrid\b|\b\d+ days? (?:per week |a week )?(?:in (?:the )?office|on[- ]?site)',
  'remote':r'\b(?:fully remote|remote (?:role|position|job|work|within|from|in|across)|work (?:fully )?remotely|work from home)\b',
  'onsite':r'\b(?:on[- ]?site (?:role|position|work|job)|office[- ]based|in[- ]person (?:role|position|work)|work (?:from|in) (?:our|the) office)\b',
 }
 for kind,pattern in patterns.items():
  for line in text.splitlines():
   if re.search(pattern,line,re.I) and not re.search(r'(?:not|no|cannot|unable).{0,25}(?:remote|hybrid)',line,re.I):return kind,line.strip()[:500]
 if metadata in ('remote','hybrid','onsite','on-site'):return metadata.replace('on-site','onsite'),'Employer workplace metadata: '+metadata
 for kind in ('hybrid','remote','onsite'):
  if re.search(r'\b'+kind+r'\b',location or '',re.I):return kind,location[:500]
 return 'unspecified','Work arrangement not stated in listing.'

def salary(description,structured=''):
 if structured:return structured
 # Require an explicit monetary amount and a pay-related context in the same sentence.
 money=r'(?:\$|USD\s*|CAD\s*|GBP\s*|EUR\s*|£|€|INR\s*|₹)\s*\d[\d,]*(?:\.\d{1,2})?(?:\s*[kK])?'
 for line in re.split(r'\n|(?<=[.!?])\s+',description or ''):
  if re.search(money,line) and re.search(r'\b(?:salary|base pay|pay range|compensation|per hour|hourly|per year|annually|annual)\b',line,re.I):return line.strip()[:1000]
 return ''
