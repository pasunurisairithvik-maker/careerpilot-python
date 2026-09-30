import csv,hashlib,hmac,io,json,secrets,time,unicodedata,uuid
from datetime import date,timedelta
from collections import Counter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login,logout,get_user_model,update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm,AuthenticationForm,PasswordChangeForm
from django.contrib.auth.hashers import make_password,check_password
from django.db import transaction,connection
from django.db.models import Q
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from config.observability import audit
from .models import Profile,Throttle,Application
from .forms import RegisterForm,RecoveryForm,SettingsForm,ApplicationForm,ResumeForm
from .matching import analyse
User=get_user_model()
def digest(value):return hmac.new(settings.SECRET_KEY.encode(),value.encode(),hashlib.sha256).hexdigest()
def valid_recovery_code(code,stored):
    # Legacy HMACs remain valid while their original signing key is retained.
    if len(stored)==64 and all(c in '0123456789abcdef' for c in stored):
        return secrets.compare_digest(stored,digest(code))
    return check_password(code,stored)

def limited(key,limit=10):
    key=digest(key);bucket=int(time.time()//900)
    with transaction.atomic():
        Throttle.objects.filter(bucket__lt=bucket-1).exclude(key__in=['account-capacity']).delete()
        Throttle.objects.get_or_create(key=key,defaults={'bucket':bucket})
        item=Throttle.objects.select_for_update().get(key=key)
        if item.bucket!=bucket:item.bucket=bucket;item.count=0
        item.count+=1;item.save()
        return item.count>limit
def sign_up(request):
    form=RegisterForm(request.POST or None)
    if request.method=='POST':
        if limited('registration',20):form.add_error(None,'Signup is temporarily busy. Try again in 15 minutes.')
        elif form.is_valid():
            with transaction.atomic():
                # Lock a stable row to serialize the free-tier account quota.
                lock,_=Throttle.objects.get_or_create(key='account-capacity',defaults={'bucket':int(time.time()//900)})
                Throttle.objects.select_for_update().get(pk=lock.pk)
                if User.objects.count()>=settings.MAX_USERS:form.add_error(None,'The free plan is currently full.')
                else:
                    user=form.save();code=secrets.token_urlsafe(32)
                    Profile.objects.create(user=user,recovery_hash=make_password(code));login(request,user)
                    return render(request,'recovery_code.html',{'code':code})
    return render(request,'form.html',{'form':form,'heading':'Your career. Your private workspace.','intro':'Create a username and a unique password. No email address required.','button':'Create account'})
def canonical_username(value):return unicodedata.normalize('NFKC',value).strip().lower()
def sign_in(request):
    data=request.POST.copy() if request.method=='POST' else None
    if data is not None:data['username']=canonical_username(data.get('username',''))
    form=AuthenticationForm(request,data=data)
    if request.method=='POST':
        if limited('authentication-global',500) or limited('login:'+data.get('username',''),10):form.add_error(None,'Too many attempts. Try again in 15 minutes.')
        elif form.is_valid():login(request,form.get_user());return redirect('dashboard')
    return render(request,'form.html',{'form':form,'heading':'Welcome back.','intro':'Sign in to your private application workspace.','button':'Sign in','recover':True})
def recover(request):
    form=RecoveryForm(request.POST or None)
    if request.method=='POST':
        if limited('authentication-global',500) or limited('recover:'+canonical_username(request.POST.get('username','')),5):form.add_error(None,'Too many attempts. Try again in 15 minutes.')
        elif form.is_valid():
            with transaction.atomic():
                user=User.objects.filter(username=canonical_username(form.cleaned_data['username'])).first()
                profile=Profile.objects.select_for_update().filter(user=user).first() if user else None
                if not profile or not valid_recovery_code(form.cleaned_data['recovery_code'],profile.recovery_hash):form.add_error(None,'Username or recovery code is incorrect.')
                else:
                    password=SetPasswordForm(user,{'new_password1':form.cleaned_data['password1'],'new_password2':form.cleaned_data['password2']})
                    if password.is_valid():
                        password.save();code=secrets.token_urlsafe(32);profile.recovery_hash=make_password(code);profile.save();login(request,user)
                        return render(request,'recovery_code.html',{'code':code})
                    else:
                        for errors in password.errors.values():
                            for error in errors:form.add_error(None,error)
    return render(request,'form.html',{'form':form,'heading':'Recover your account.','intro':'Use the recovery code you saved at signup. Without your password or code, we cannot recover your account.','button':'Reset password'})
@login_required
def account(request):
    form=SettingsForm(request.POST or None,initial={'timezone':request.user.profile.timezone})
    if request.method=='POST' and form.is_valid():request.user.profile.timezone=form.cleaned_data['timezone'];request.user.profile.save();messages.success(request,'Timezone updated.');return redirect('account')
    return render(request,'account.html',{'form':form})
@login_required
def change_password(request):
    form=PasswordChangeForm(request.user,request.POST or None)
    if request.method=='POST':
        if limited('sensitive:'+str(request.user.pk),10):form.add_error(None,'Too many attempts. Try again in 15 minutes.')
        elif form.is_valid():
            user=form.save();update_session_auth_hash(request,user);audit(request,'password_changed');messages.success(request,'Password updated. Other sessions are invalidated.');return redirect('account')
    return render(request,'form.html',{'form':form,'heading':'Change your password','button':'Update password'})
@login_required
@require_POST
def delete_account(request):
    if limited('sensitive:'+str(request.user.pk),10):
        messages.error(request,'Too many attempts. Try again in 15 minutes.');return redirect('account')
    if request.POST.get('confirmation')=='DELETE' and request.user.check_password(request.POST.get('password','')):
        user=request.user;logout(request);user.delete();audit(request,'account_deleted');messages.success(request,'Account, resume text and application records deleted. Provider backups may retain older copies temporarily.');return redirect('home')
    messages.error(request,'Enter your password and DELETE to confirm.');return redirect('account')
@login_required
@require_POST
def replace_recovery_code(request):
    if limited('sensitive:'+str(request.user.pk),10):
        messages.error(request,'Too many attempts. Try again in 15 minutes.');return redirect('account')
    if not request.user.check_password(request.POST.get('password','')):
        messages.error(request,'Your current password is incorrect.');return redirect('account')
    with transaction.atomic():
        profile=Profile.objects.select_for_update().get(user=request.user)
        code=secrets.token_urlsafe(32)
        profile.recovery_hash=make_password(code);profile.save(update_fields=['recovery_hash'])
    audit(request,'recovery_code_replaced')
    return render(request,'recovery_code.html',{'code':code})

def owned(request):return Application.objects.filter(owner=request.user)
def home(request):return render(request,'home.html')
@login_required
def dashboard(request):
    items=owned(request).filter(archived=False)
    counts=Counter(items.values_list('stage',flat=True))
    q=request.GET.get('q','')[:100];stage=request.GET.get('stage','')
    if q:items=items.filter(Q(company__icontains=q)|Q(role__icontains=q)|Q(notes__icontains=q))
    if stage:items=items.filter(stage=stage)
    today=timezone.localdate()
    due=owned(request).filter(archived=False,due__lte=today+timedelta(days=7)).exclude(stage__in=['rejected','withdrawn','offer']).order_by('due')
    from .models import STAGES
    return render(request,'dashboard.html',{'items':items,'q':q,'stage':stage,'counts':counts,'stages':STAGES,'due':due[:6],'active_count':sum(counts.values()),'interview_count':counts.get('interview',0),'offer_count':counts.get('offer',0)})
@login_required
def edit(request,pk=None):
    item=get_object_or_404(owned(request),pk=pk) if pk else Application(owner=request.user)
    form=ApplicationForm(request.POST or None,instance=item,initial={'submission_id':None if pk else uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            nonce=form.cleaned_data.get('submission_id') if not pk else None
            payload={k:str(v) for k,v in form.cleaned_data.items() if k!='submission_id'}
            fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            prior=owned(request).filter(submission_id=nonce).first() if nonce else None
            if prior:
                if prior.submission_hash==fingerprint:return redirect('detail',pk=prior.pk)
                form.add_error(None,'This form was already saved with different data. Open a fresh form.')
            elif not pk and owned(request).count()>=settings.MAX_APPLICATIONS:form.add_error(None,'Account limit: 100 applications including archived records.')
            else:
                item=form.save(commit=False)
                if nonce:item.submission_id=nonce;item.submission_hash=fingerprint
                item.save();messages.success(request,'Application saved.');return redirect('detail',pk=item.pk)
    return render(request,'form.html',{'form':form,'heading':'Edit application' if pk else 'Make your next move.','intro':'Keep the original job description and your next action in one place.','button':'Save application'})
@login_required
def detail(request,pk):
    item=get_object_or_404(owned(request),pk=pk)
    match=analyse(item.description,request.user.profile.resume,item.requirements)
    return render(request,'detail.html',{'item':item,'match':match,'has_resume':bool(request.user.profile.resume)})
@login_required
def resume(request):
    form=ResumeForm(request.POST if request.method=='POST' else None,request.FILES or None,initial={'resume':request.user.profile.resume})
    if request.method=='POST' and form.is_valid():
        request.user.profile.resume=form.cleaned_data.get('resume','');request.user.profile.save(update_fields=['resume'])
        messages.success(request,'Resume text saved. Matching uses this version.');return redirect('resume')
    return render(request,'form.html',{'form':form,'heading':'Let your work speak.','intro':'Keep truthful evidence here. Text stays in your account; it is not sent to an AI provider. Saving an empty form clears your resume.','button':'Save resume','multipart':True})
@login_required
@require_POST
def archive(request,pk):
    item=get_object_or_404(owned(request),pk=pk)
    item.archived=not item.archived;item.save(update_fields=['archived','updated'])
    return redirect('dashboard')
@login_required
def archived(request):return render(request,'archived.html',{'items':owned(request).filter(archived=True)})
def csv_safe(value):
    s='' if value is None else str(value)
    return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
@login_required
def export(request):
    response=HttpResponse(content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="careerpilot-applications.csv"'
    writer=csv.writer(response);writer.writerow(['company','role','source_url','stage','next_step','due','notes','description','requirements','archived'])
    for a in owned(request):writer.writerow([csv_safe(getattr(a,k)) for k in ['company','role','source_url','stage','next_step','due','notes','description','requirements','archived']])
    return response
@login_required
def backup(request):
    fields=['company','role','source_url','stage','next_step','due','notes','description','requirements','archived']
    records=[{k:str(getattr(a,k)) if k=='due' and a.due else getattr(a,k) for k in fields} for a in owned(request)]
    from .models import ResumeDraft,SavedSearch
    draft=ResumeDraft.objects.filter(owner=request.user).first()
    searches=list(SavedSearch.objects.filter(owner=request.user).values('name','filters','created','seen'))
    response=JsonResponse({'format_version':2,'resume':request.user.profile.resume,'timezone':request.user.profile.timezone,'applications':records,'resume_draft':draft.fields if draft else None,'saved_searches':searches},json_dumps_params={'ensure_ascii':False,'indent':2})
    response['Content-Disposition']='attachment; filename="careerpilot-backup.json"';return response

def ics_escape(value):return str(value).replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
def fold(line):
    parts=[];chunk='';size=0
    for char in line:
        n=len(char.encode())
        if size+n>73:parts.append(chunk);chunk=' ';size=1
        chunk+=char;size+=n
    return '\r\n'.join(parts+[chunk])
@login_required
def calendar(request):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//CareerPilot//Application deadlines//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    for a in owned(request).filter(archived=False,due__gte=timezone.localdate()).exclude(stage__in=['offer','rejected','withdrawn']):
        lines+=['BEGIN:VEVENT',f'UID:{a.pk}@careerpilot',f'DTSTAMP:{timezone.now():%Y%m%dT%H%M%SZ}',f'DTSTART;VALUE=DATE:{a.due:%Y%m%d}',f'SUMMARY:{ics_escape(a.company+": "+a.role)}',f'DESCRIPTION:{ics_escape(a.next_step)}','BEGIN:VALARM','TRIGGER:-P1D','ACTION:DISPLAY',f'DESCRIPTION:{ics_escape(a.next_step or "Application deadline")}', 'END:VALARM','END:VEVENT']
    lines+=['END:VCALENDAR'];r=HttpResponse('\r\n'.join(fold(x) for x in lines)+'\r\n',content_type='text/calendar; charset=utf-8');r['Content-Disposition']='attachment; filename="careerpilot-deadlines.ics"';return r

def privacy(request):return render(request,'privacy.html')
def health(request):
    try:
        with connection.cursor() as c:c.execute('SELECT 1 FROM tracker_application LIMIT 1')
        # Health remains available even if optional cache scheduling fails.
        try:
            from .auto_refresh import maybe_refresh
            maybe_refresh()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Could not schedule public-cache refresh")
        return JsonResponse({'status':'ok','service':'careerpilot'})
    except Exception:return JsonResponse({'status':'unavailable'},status=503)
def live(request):return JsonResponse({'status':'ok','service':'careerpilot'})

@login_required
@require_POST
def sign_out(request):logout(request);return redirect('home')

@login_required
@require_POST
def remove_application(request,pk):
    if limited('sensitive:'+str(request.user.pk),10):
        messages.error(request,'Too many attempts. Try again in 15 minutes.');return redirect('detail',pk=pk)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        item=get_object_or_404(owned(request),pk=pk,archived=True)
        if request.POST.get('confirmation')=='DELETE' and request.user.check_password(request.POST.get('password','')):
            item.delete();messages.success(request,'Archived application permanently deleted.');return redirect('archived')
    messages.error(request,'Enter your current password and DELETE to confirm.');return redirect('detail',pk=pk)
