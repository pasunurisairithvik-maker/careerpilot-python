"""Public-feed normalization and conservative listing evidence. No eligibility decisions."""
import re,html,hashlib,json,urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
SOURCES=[('greenhouse','stripe','Stripe'),('greenhouse','cloudflare','Cloudflare'),('greenhouse','datadog','Datadog'),('lever','palantir','Palantir'),('lever','spotify','Spotify'),('greenhouse','mongodb','MongoDB')]
ROLES=[('developer','Developer / software engineer'),('analyst','Analyst'),('qa','QA / testing'),('data','Data science / ML'),('support','IT / technical support'),('product','Product / project'),('other','Other')]
AUTH=[('opt','OPT'),('stem_opt','STEM OPT'),('h1b','H-1B'),('green_card','Green card / permanent resident'),('citizen','US citizen')]
class Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,t,a):
        if t in ['script','style']:self.skip+=1
        if t in ['p','br','div','li','h1','h2','h3']:self.parts.append('\n')
    def handle_endtag(self,t):
        if t in ['script','style'] and self.skip:self.skip-=1
        if t in ['p','div','li']:self.parts.append('\n')
    def handle_data(self,d):
        if not self.skip:self.parts.append(d)
def plain(value):
    p=Plain();p.feed(html.unescape(str(value or '')));return re.sub(r'\n\s*\n+','\n',''.join(p.parts)).strip()[:20000]
def safe_url(value):
    p=urlsplit(str(value or ''))
    if p.scheme!='https' or not p.hostname or p.username or p.password or len(value)>500:return ''
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_')]),''))
def classify(title):
    t=title.lower()
    for role,pattern in [('qa',r'\bqa\b|quality assurance|test engineer|sdet'),('data',r'data scientist|machine learning|research scientist|data engineer'),('analyst',r'analyst|analytics'),('support',r'help desk|technical support|it support|support engineer'),('developer',r'engineer|developer|programmer'),('product',r'product manager|project manager|program manager')]:
        if re.search(pattern,t):return role
    return 'other'
def seniority(title):
    t=title.lower()
    if re.search(r'intern|internship|co-op',t):return 'intern'
    if re.search(r'senior|staff|principal|lead|director|manager',t):return 'senior'
    if re.search(r'junior|graduate|entry|new grad|associate',t):return 'entry'
    return 'unspecified'
def evidence(text):
    result={}
    patterns={'opt':r'\bOPT\b|optional practical training','stem_opt':r'STEM[ -]+OPT','h1b':r'H[ -]?1[ -]?B','green_card':r'green card|permanent residen(?:t|ce|cy)','citizen':r'(?:U\.?S\.?|United States) citizen(?:ship)?'}
    # Extract sentence-sized context, never infer acceptance from a generic mention.
    sentences=re.split(r'(?<=[.!?])\s+|\n',text)
    for key,pattern in patterns.items():
        states=[];quotes=[]
        for sentence in sentences:
            if not re.search(pattern,sentence,re.I):continue
            if key=='opt' and re.search(r'opt (?:in|out)',sentence,re.I) and not re.search(r'optional practical training|STEM[ -]OPT',sentence,re.I):continue
            quote=sentence.strip()[:700];quotes.append(quote)
            negative=bool(re.search(r'not (?:accept|support|eligible|consider)|cannot|unable|ineligible|no (?:OPT|STEM|H[ -]?1)|excluding|do not|will not',sentence,re.I))
            positive=bool(re.search(r'(?:accept|eligible|welcome|consider|support|sponsor)(?:ed|ing|s|ship)?|must be|require(?:d|ment)?|only',sentence,re.I))
            states.append('excluded' if negative else 'stated' if positive else 'mentioned')
        state='unknown' if not states else states[0] if len(set(states))==1 else 'mixed'
        result[key]={'state':state,'evidence':quotes[:3]}
    sponsor=[]
    for sentence in sentences:
        if not re.search(r'visa sponsorship|immigration sponsorship|sponsor.{0,25}(?:visa|H[ -]?1[ -]?B)|sponsorship',sentence,re.I):continue
        negative=bool(re.search(r'no sponsorship|without.{0,25}sponsorship|not.{0,40}sponsor|unable.{0,40}sponsor|cannot.{0,40}sponsor|do not|will not',sentence,re.I))
        positive=bool(re.search(r'(?:offer|provide|available|support|eligible for).{0,40}sponsor|sponsor.{0,20}(?:available|provided)',sentence,re.I))
        sponsor.append(('no' if negative else 'yes' if positive else 'unknown',sentence.strip()[:700]))
    states={x[0] for x in sponsor};result['sponsorship']={'state':next(iter(states)) if len(states)==1 else 'mixed' if states else 'unknown','evidence':[x[1] for x in sponsor[:3]]}
    return result
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):raise ValueError('Feed redirects are not followed')
def download(provider,slug):
    url=f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true' if provider=='greenhouse' else f'https://api.lever.co/v0/postings/{slug}?mode=json'
    req=urllib.request.Request(url,headers={'User-Agent':'CareerPilot/2.0 public-job-board-reader','Accept':'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=8) as r:raw=r.read(12000001)
    if len(raw)>12000000:raise ValueError('Feed exceeds configured bound')
    data=json.loads(raw);rows=data.get('jobs') if provider=='greenhouse' and isinstance(data,dict) else data
    if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Invalid or oversized feed')
    return rows
def normalize(provider,slug,company,row):
    if not isinstance(row,dict) or not row.get('id'):raise ValueError('Invalid posting')
    title=str(row.get('title') if provider=='greenhouse' else row.get('text') or '').strip()[:150]
    if not title:raise ValueError('Missing title')
    categories=row.get('categories') or {}
    location=str((row.get('location') or {}).get('name','') if provider=='greenhouse' else categories.get('location',''))[:200]
    description=plain(row.get('content','') if provider=='greenhouse' else row.get('descriptionPlain') or row.get('description',''))
    if provider=='lever':description+='\n'+plain('\n'.join(str(x.get('text',''))+'\n'+str(x.get('content','')) for x in row.get('lists',[]) if isinstance(x,dict)))+'\n'+plain(row.get('additionalPlain') or row.get('additional',''))
    url=safe_url(row.get('absolute_url','') if provider=='greenhouse' else row.get('hostedUrl',''))
    if not url:raise ValueError('Unsafe source link')
    workplace=row.get('workplaceType','')
    remote='remote' if workplace=='remote' or re.search(r'\bremote\b',location,re.I) else 'hybrid' if workplace=='hybrid' or re.search(r'\bhybrid\b',location,re.I) else 'unspecified'
    salary=plain(row.get('salaryDescription',''))[:1000]
    salary_range=row.get('salaryRange')
    if isinstance(salary_range,dict):salary=(salary+'\n'+json.dumps(salary_range,ensure_ascii=False))[:1000]
    description=description[:20000]
    return dict(source_key=f'{provider}:{slug}:{row["id"]}',provider=provider,board=slug,company=company,title=title,location=location,description=description,url=url,role=classify(title),level=seniority(title),workplace=remote,salary=salary,evidence=evidence(description),source_updated=str(row.get('updated_at') or '')[:50])
def refresh(force=False):
    from .models import Job,FeedState
    now=timezone.now()
    with transaction.atomic():
        FeedState.objects.get_or_create(key='refresh')
        lock=FeedState.objects.select_for_update().get(key='refresh')
        if lock.attempted and now-lock.attempted<timedelta(minutes=30) and not force:return {'busy':True}
        lock.attempted=now;lock.save(update_fields=['attempted'])
    def fetch(source):
        provider,slug,company=source
        try:return source,[normalize(provider,slug,company,row) for row in download(provider,slug)],None
        except Exception as e:return source,None,type(e).__name__
    counts={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for source,rows,error in pool.map(fetch,SOURCES):
            provider,slug,company=source;key=f'{provider}:{slug}'
            state,_=FeedState.objects.get_or_create(key=key)
            state.attempted=now
            if error:state.error=error;state.save();counts[company]='unavailable';continue
            with transaction.atomic():
                keys=[]
                objects=[]
                for row in rows:
                    sk=row['source_key'];keys.append(sk)
                    objects.append(Job(**row,checked=now,active=True))
                if objects:
                    fields=[k for k in rows[0] if k!='source_key']+['checked','active']
                    Job.objects.bulk_create(objects,update_conflicts=True,update_fields=fields,unique_fields=['source_key'],batch_size=100)
                Job.objects.filter(provider=provider,board=slug,active=True).exclude(source_key__in=keys).update(active=False,checked=now)
                state.success=now;state.error='';state.count=len(rows);state.save()
            counts[company]=len(rows)
    Job.objects.filter(active=False,checked__lt=now-timedelta(days=30)).delete()
    return counts
