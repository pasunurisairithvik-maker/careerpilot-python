from datetime import timedelta
from urllib.parse import urlencode
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .job_traits import level as jd_level,workplace as jd_workplace,salary as jd_salary
from .models import Job,FeedState,SavedSearch,Application,ResumeDraft
from .discovery import ROLES,AUTH,SOURCES,refresh,evidence as jd_evidence
from .matching import analyse
from .resume_tools import checks,build_text,docx
from .forms import ResumeBuilderForm
from .job_presentation import experience_requirement,description_sections,authorization_rows
from .employment import terms as employment_terms, EMPLOYMENT, ENGAGEMENT
class JobFilter(forms.Form):
    q=forms.CharField(required=False,max_length=100,label='Keywords')
    exclude=forms.CharField(required=False,max_length=100,label='Exclude words (comma separated)')
    title_only=forms.BooleanField(required=False,label='Search keywords in title only')
    sort=forms.ChoiceField(required=False,choices=[('','Recently discovered'),('company','Company A–Z'),('title','Job title A–Z')])
    location=forms.CharField(required=False,max_length=100)
    company=forms.CharField(required=False,max_length=100)
    role=forms.ChoiceField(required=False,choices=[('','All roles')]+ROLES)
    level=forms.ChoiceField(required=False,choices=[('','Any experience'),('intern','Internship'),('entry','Entry / graduate'),('mid','Mid-level'),('senior','Senior / lead'),('management','Management / leadership'),('unspecified','Experience not stated')])
    include_unstated=forms.BooleanField(required=False,label='Include listings with unstated seniority')
    workplace=forms.ChoiceField(required=False,choices=[('','Any workplace'),('remote','Remote'),('hybrid','Hybrid'),('onsite','Onsite'),('unspecified','Work arrangement not stated')])
    provider=forms.ChoiceField(required=False,choices=[('','All sources'),('greenhouse','Greenhouse'),('lever','Lever'),('smartrecruiters','SmartRecruiters')])
    authorization=forms.ChoiceField(required=False,choices=[('','Any authorization')]+AUTH,label='Listing mentions status')
    include_unknown=forms.BooleanField(required=False,label='Include listings that do not mention this status')
    sponsorship=forms.ChoiceField(required=False,choices=[('','Any sponsorship'),('yes','Employer states sponsorship support'),('no','Employer states no sponsorship'),('unknown','Not confirmed in listing'),('mixed','Conflicting statements')])
    employment=forms.ChoiceField(required=False,choices=[('', 'Any employment type')]+EMPLOYMENT,label='Employment type')
    engagement=forms.ChoiceField(required=False,choices=[('', 'Any engagement basis')]+ENGAGEMENT,label='Engagement basis')
    salary=forms.BooleanField(required=False,label='Only jobs with published pay')
    days=forms.ChoiceField(required=False,choices=[('','Any first-seen date'),('1','First seen in 24 hours'),('7','First seen in 7 days'),('30','First seen in 30 days')])
    fresh=forms.BooleanField(required=False,label='Only feeds checked in the last 24 hours')
    closed=forms.BooleanField(required=False,label='Include removed / closed listings')
def filtered(data):
    qs=Job.objects.all()
    if not data.get('closed'):qs=qs.filter(active=True)
    if data.get('q'):
        qs=qs.filter(title__icontains=data['q']) if data.get('title_only') else qs.filter(Q(title__icontains=data['q'])|Q(description__icontains=data['q'])|Q(company__icontains=data['q']))
    for term in (data.get('exclude') or '').split(','):
        if term.strip():qs=qs.exclude(Q(title__icontains=term.strip())|Q(description__icontains=term.strip()))
    for field in ['company','location']:
        if data.get(field):qs=qs.filter(**{field+'__icontains':data[field]})
    if data.get('level'):
        qs=qs.filter(Q(level=data['level'])|Q(level='unspecified')) if data.get('include_unstated') else qs.filter(level=data['level'])
    for field in ['role','provider','workplace']:
        if data.get(field):qs=qs.filter(**{field:data[field]})
    if data.get('sponsorship'):qs=qs.filter(evidence__sponsorship__state=data['sponsorship'])
    if data.get('salary'):qs=qs.exclude(salary='')
    if data.get('authorization'):
        field='evidence__'+data['authorization']+'__state'
        states=['stated','mentioned','mixed']+(['unknown'] if data.get('include_unknown') else [])
        qs=qs.filter(**{field+'__in':states})
    if data.get('days'):qs=qs.filter(first_seen__gte=timezone.now()-timedelta(days=int(data['days'])))
    if data.get('fresh'):qs=qs.filter(checked__gte=timezone.now()-timedelta(hours=24))
    # Same canonical application URL represents the same listing; don't merge distinct requisitions merely by title.
    seen=set();ids=[]
    check_experience=data.get('level') in ['entry','intern']
    check_terms=bool(data.get('employment') or data.get('engagement'))
    columns=['pk','url']+(['description'] if check_experience or check_terms else [])+(['title'] if check_terms else [])
    for row in qs.order_by('-active','-first_seen','pk').values_list(*columns).iterator(chunk_size=100):
        pk,url=row[:2]
        experience=experience_requirement(row[2]) if check_experience else None
        if experience and experience['years']>2:continue
        if check_terms:
            labels=employment_terms(row[3],row[2])['keys']
            if any(data.get(field) and (not labels.isdisjoint({k for k,_ in choices if k!='unknown'}) if data[field]=='unknown' else data[field] not in labels) for field,choices in [('employment',EMPLOYMENT),('engagement',ENGAGEMENT)]):continue
        if url not in seen:seen.add(url);ids.append(pk)
    qs=qs.filter(pk__in=ids)
    return qs.order_by('company','title','pk') if data.get('sort')=='company' else qs.order_by('title','pk') if data.get('sort')=='title' else qs
def jobs(request):
    form=JobFilter(request.GET or None)
    valid=not request.GET or form.is_valid()
    data=form.cleaned_data if request.GET and valid else {}
    qs=filtered(data) if valid else Job.objects.none()
    pager=Paginator(qs,20);page=pager.get_page(request.GET.get('page'))
    for listing in page:
        listing.employment_terms=employment_terms(listing.title,listing.description)
        listing.experience=experience_requirement(listing.description)
        listing.evidence=jd_evidence(listing.description)
        listing.level=jd_level(listing.title,listing.description)
        listing.workplace,listing.workplace_quote=jd_workplace(listing.location,listing.description,listing.workplace)
        listing.salary=jd_salary(listing.description,listing.salary)
    query=request.GET.copy();query.pop('page',None)
    saved=[]
    if request.user.is_authenticated:
        for search in SavedSearch.objects.filter(owner=request.user):
            f=JobFilter(search.filters)
            count=filtered(f.cleaned_data).filter(first_seen__gt=search.seen or search.created).count() if f.is_valid() else 0
            saved.append({'item':search,'new':count,'query':urlencode(search.filters)})
    chips=[]
    for key,value in data.items():
        if value:
            reduced=query.copy();reduced.pop(key,None)
            label=dict(form.fields[key].choices).get(value,value) if hasattr(form.fields[key],'choices') else 'Enabled' if value is True else value
            chips.append({'label':f'{form.fields[key].label or key.replace("_"," ").title()}: {label}','query':reduced.urlencode()})
    broader=query.copy();broader['include_unknown']='on'
    suggestions=[]
    if valid and pager.count<5:
        variants=[]
        if data.get('authorization') and not data.get('include_unknown'):
            v=query.copy();v['include_unknown']='on';variants.append(('Include unstated authorization',v))
        if data.get('level') and not data.get('include_unstated'):
            v=query.copy();v['include_unstated']='on'
            if data.get('authorization'):v['include_unknown']='on'
            variants.append(('Explore roles with unstated seniority and authorization',v))
        if data.get('sponsorship'):
            v=query.copy();v.pop('sponsorship',None)
            if data.get('authorization'):v['include_unknown']='on'
            if data.get('level'):v['include_unstated']='on'
            variants.append(('Explore without a sponsorship restriction',v))
        if data.get('role'):
            variants.append(('Browse all '+dict(ROLES).get(data['role'],data['role'])+' roles',{'role':data['role']}))
        for label,params in variants:
            candidate=JobFilter(params)
            if candidate.is_valid():
                count=filtered(candidate.cleaned_data).count()
                if count>pager.count:suggestions.append({'label':label,'count':count,'query':urlencode(params)})
    recommendations=[];recommendation_query=''
    if valid and pager.count==0 and suggestions:
        recommendation_query=suggestions[0]['query']
        from urllib.parse import parse_qs
        params={k:v[-1] for k,v in parse_qs(recommendation_query).items()}
        alternative=JobFilter(params)
        if alternative.is_valid():recommendations=list(filtered(alternative.cleaned_data)[:3])
    role_terms={'developer':'software engineer','analyst':'analyst','qa':'QA tester','mainframe':'COBOL mainframe','cloud':'DevOps','security':'cybersecurity','design':'UX designer','finance':'finance analyst','hr':'recruiter','sales':'customer success','marketing':'marketing','operations':'operations','data':'data science','support':'technical support','product':'product manager'}
    terms=' '.join(x for x in [data.get('q',''),role_terms.get(data.get('role'),''),data.get('company','')] if x).strip()
    external=[{'name':name,'url':base+urlencode({param:terms,location_param:data.get('location','')})} for name,base,param,location_param in [('LinkedIn','https://www.linkedin.com/jobs/search/?','keywords','location'),('Indeed','https://www.indeed.com/jobs?','q','l'),('Dice','https://www.dice.com/jobs?','q','location'),('ZipRecruiter','https://www.ziprecruiter.com/jobs-search?','search','location')]]
    return render(request,'jobs.html',{'recommendations':recommendations,'recommendation_query':recommendation_query,'suggestions':suggestions,'chips':chips,'broader':broader.urlencode(),'external':external,'available':Job.objects.filter(active=True).count(),'form':form,'page':page,'query':query.urlencode(),'saved':saved,'feeds':FeedState.objects.filter(Q(key__startswith='greenhouse:')|Q(key__startswith='lever:')|Q(key__startswith='smartrecruiters:')),'total':pager.count,'sources':SOURCES})
def job(request,pk):
    item=get_object_or_404(Job,pk=pk)
    match=analyse(item.description,request.user.profile.resume) if request.user.is_authenticated else None
    item.employment_terms=employment_terms(item.title,item.description)
    item.evidence=jd_evidence(item.description)
    item.level=jd_level(item.title,item.description)
    item.workplace,item.workplace_quote=jd_workplace(item.location,item.description,item.workplace)
    item.salary=jd_salary(item.description,item.salary)
    return render(request,'job.html',{'job':item,'match':match,'stale':timezone.now()-item.checked>timedelta(hours=24),'auth_labels':AUTH,'experience':experience_requirement(item.description),'sections':description_sections(item.description),'authorization_rows':authorization_rows(item.evidence),'has_resume':bool(request.user.is_authenticated and request.user.profile.resume.strip())})
@login_required
@require_POST
def sync(request):
    from .views import limited
    if limited('job-refresh',2):messages.info(request,'Refresh is rate-limited. Cached jobs are still available.');return redirect('jobs')
    result=refresh()
    messages.info(request,'Another refresh ran recently. Try after 30 minutes.' if result.get('busy') else 'Refresh finished. Source status below shows failures; cached records are retained.')
    return redirect('jobs')
@login_required
@require_POST
def save_search(request):
    form=JobFilter(request.POST)
    name=request.POST.get('name','Saved search').strip()[:80] or 'Saved search'
    if form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if SavedSearch.objects.filter(owner=request.user).count()>=10:messages.error(request,'Limit: 10 saved searches. Remove one before adding another.')
            else:
                data={k:str(v) if not isinstance(v,bool) else 'on' for k,v in form.cleaned_data.items() if v}
                SavedSearch.objects.create(owner=request.user,name=name,filters=data);messages.success(request,'Search saved. New-match alerts appear here when you return; no emails are sent.')
    else:messages.error(request,'Invalid search filters.')
    return redirect('jobs')
@login_required
@require_POST
def search_seen(request,pk):
    s=get_object_or_404(SavedSearch,pk=pk,owner=request.user);s.seen=timezone.now();s.save(update_fields=['seen']);return redirect('/jobs/?'+urlencode(s.filters))
@login_required
@require_POST
def search_remove(request,pk):
    get_object_or_404(SavedSearch,pk=pk,owner=request.user).delete();messages.success(request,'Saved search removed.');return redirect('jobs')
@login_required
@require_POST
def track(request,pk):
    item=get_object_or_404(Job,pk=pk)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        prior=Application.objects.filter(owner=request.user,source_url=item.url).first()
        if prior:return redirect('detail',pk=prior.pk)
        if Application.objects.filter(owner=request.user).count()>=100:messages.error(request,'Your account has reached its 100-application limit.');return redirect('job',pk=pk)
        app=Application.objects.create(owner=request.user,company=item.company,role=item.title,source_url=item.url,description=item.description)
    return redirect('detail',pk=app.pk)
@login_required
def resume_check(request):
    from .forms import ResumeForm
    form=ResumeForm(request.POST if request.method=='POST' else None,request.FILES or None,initial={'resume':request.user.profile.resume})
    description=request.POST.get('description','')[:20000] if request.method=='POST' else ''
    result=None
    if request.method=='POST' and form.is_valid():result=checks(form.cleaned_data.get('resume',''),description)
    return render(request,'resume_check.html',{'form':form,'result':result,'description':description})
@login_required
def builder(request):
    draft=ResumeDraft.objects.filter(owner=request.user).first()
    target=None
    if request.GET.get('job'):
        try:target=Job.objects.filter(pk=int(request.GET['job'])).first()
        except (ValueError,OverflowError):pass
    form=ResumeBuilderForm(request.POST if request.method=='POST' else None,initial=draft.fields if draft else {})
    preview=None
    if request.method=='POST' and form.is_valid():
        fields={k:v for k,v in form.cleaned_data.items() if k!='confirmed'}
        preview=build_text(fields,target)
        action=request.POST.get('action','preview')
        if action in ['save','use']:
            ResumeDraft.objects.update_or_create(owner=request.user,defaults={'fields':fields})
            if action=='use':request.user.profile.resume=preview;request.user.profile.save(update_fields=['resume']);messages.success(request,'Reviewed resume saved for matching.')
            else:messages.success(request,'Draft saved privately.')
        if action in ['txt','docx']:
            response=HttpResponse(docx(preview) if action=='docx' else preview,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document' if action=='docx' else 'text/plain; charset=utf-8');response['Content-Disposition']=f'attachment; filename="careerpilot-resume.{action}"';return response
    return render(request,'builder.html',{'form':form,'preview':preview,'target':target})
