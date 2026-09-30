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
from .models import Job,FeedState,SavedSearch,Application,ResumeDraft
from .discovery import ROLES,AUTH,SOURCES,refresh
from .matching import analyse
from .resume_tools import checks,build_text,docx
from .forms import ResumeBuilderForm
class JobFilter(forms.Form):
    q=forms.CharField(required=False,max_length=100,label='Keywords')
    location=forms.CharField(required=False,max_length=100)
    company=forms.CharField(required=False,max_length=100)
    role=forms.ChoiceField(required=False,choices=[('','All roles')]+ROLES)
    level=forms.ChoiceField(required=False,choices=[('','Any experience'),('intern','Internship'),('entry','Entry / graduate'),('senior','Senior / lead'),('unspecified','Not stated in title')])
    workplace=forms.ChoiceField(required=False,choices=[('','Any workplace'),('remote','Remote stated in location'),('hybrid','Hybrid stated in location'),('unspecified','Not stated')])
    provider=forms.ChoiceField(required=False,choices=[('','All sources'),('greenhouse','Greenhouse'),('lever','Lever')])
    authorization=forms.ChoiceField(required=False,choices=[('','Any authorization')]+AUTH,label='Listing mentions status')
    include_unknown=forms.BooleanField(required=False,label='Include listings that do not mention this status')
    sponsorship=forms.ChoiceField(required=False,choices=[('','Any sponsorship'),('yes','Positive statement'),('no','Negative statement'),('unknown','Unknown'),('mixed','Conflicting statements')])
    salary=forms.BooleanField(required=False,label='Salary supplied by source')
    days=forms.ChoiceField(required=False,choices=[('','Any first-seen date'),('1','First seen in 24 hours'),('7','First seen in 7 days'),('30','First seen in 30 days')])
    fresh=forms.BooleanField(required=False,label='Only feeds checked in the last 24 hours')
    closed=forms.BooleanField(required=False,label='Include removed / closed listings')
def filtered(data):
    qs=Job.objects.all()
    if not data.get('closed'):qs=qs.filter(active=True)
    if data.get('q'):qs=qs.filter(Q(title__icontains=data['q'])|Q(description__icontains=data['q'])|Q(company__icontains=data['q']))
    for field in ['company','location']:
        if data.get(field):qs=qs.filter(**{field+'__icontains':data[field]})
    for field in ['role','level','workplace','provider']:
        if data.get(field):qs=qs.filter(**{field:data[field]})
    if data.get('authorization'):
        field='evidence__'+data['authorization']+'__state'
        states=['stated','mentioned','mixed']+(['unknown'] if data.get('include_unknown') else [])
        qs=qs.filter(**{field+'__in':states})
    if data.get('sponsorship'):qs=qs.filter(evidence__sponsorship__state=data['sponsorship'])
    if data.get('salary'):qs=qs.exclude(salary='')
    if data.get('days'):qs=qs.filter(first_seen__gte=timezone.now()-timedelta(days=int(data['days'])))
    if data.get('fresh'):qs=qs.filter(checked__gte=timezone.now()-timedelta(hours=24))
    # Same canonical application URL represents the same listing; don't merge distinct requisitions merely by title.
    seen=set();ids=[]
    for pk,url in qs.order_by('-active','-first_seen','pk').values_list('pk','url'):
        if url not in seen:seen.add(url);ids.append(pk)
    return qs.filter(pk__in=ids)
def jobs(request):
    form=JobFilter(request.GET or None)
    valid=not request.GET or form.is_valid()
    data=form.cleaned_data if request.GET and valid else {}
    qs=filtered(data) if valid else Job.objects.none()
    pager=Paginator(qs.defer('description','evidence'),20);page=pager.get_page(request.GET.get('page'))
    query=request.GET.copy();query.pop('page',None)
    saved=[]
    if request.user.is_authenticated:
        for search in SavedSearch.objects.filter(owner=request.user):
            f=JobFilter(search.filters)
            count=filtered(f.cleaned_data).filter(first_seen__gt=search.seen or search.created).count() if f.is_valid() else 0
            saved.append({'item':search,'new':count,'query':urlencode(search.filters)})
    return render(request,'jobs.html',{'form':form,'page':page,'query':query.urlencode(),'saved':saved,'feeds':FeedState.objects.exclude(key='refresh'),'total':pager.count,'sources':SOURCES})
def job(request,pk):
    item=get_object_or_404(Job,pk=pk)
    match=analyse(item.description,request.user.profile.resume) if request.user.is_authenticated else None
    return render(request,'job.html',{'job':item,'match':match,'stale':timezone.now()-item.checked>timedelta(hours=24),'auth_labels':AUTH})
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
