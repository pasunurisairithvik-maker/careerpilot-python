"""Real Chromium workflows against disposable localhost data only."""
from concurrent.futures import ThreadPoolExecutor
import os,sys,tempfile,subprocess,time,urllib.request,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# Override inherited credentials before Django is imported. Never use an existing DB.
with tempfile.TemporaryDirectory(prefix='careerpilot-browser-') as tmp:
 os.environ.update(DEBUG='1',DATABASE_URL='sqlite:///'+tmp+'/qa.sqlite3',AUTO_JOB_REFRESH='0',DJANGO_SETTINGS_MODULE='config.settings',ALLOWED_HOSTS='127.0.0.1,localhost')
 os.environ.pop('RENDER_EXTERNAL_HOSTNAME',None)
 import django
 django.setup()
 from django.core.management import call_command
 from django.utils import timezone
 from django.contrib.auth.models import User
 from tracker.models import Job,Application,Profile,SavedSearch
 from tracker.discovery import evidence
 def db(fn):
  with ThreadPoolExecutor(max_workers=1) as pool:return pool.submit(fn).result()
 call_command('migrate',verbosity=0)
 call_command('collectstatic',interactive=False,verbosity=0)
 other=User.objects.create_user(username='qa-isolation',password='Synthetic-Isolation-Password-42!')
 from django.contrib.auth.hashers import make_password
 Profile.objects.create(user=other,recovery_hash=make_password('synthetic-recovery-fixture'))
 desc='Responsibilities\nAnalyze data using SQL and Python.\nRequirements\nZero to two years of experience.'
 job=Job.objects.create(source_key='synthetic:1',provider='greenhouse',board='synthetic',company='Synthetic Employer',title='Junior Data Analyst',location='Chicago, IL',description=desc,url='https://example.com/jobs/1',role='analyst',level='entry',workplace='unspecified',evidence=evidence(desc),checked=timezone.now())
 log=open(tmp+'/server.log','w')
 server=subprocess.Popen([sys.executable,'manage.py','runserver','127.0.0.1:8765','--noreload'],stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:
    urllib.request.urlopen('http://127.0.0.1:8765/livez',timeout=1);break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Isolated server did not start')
  from playwright.sync_api import sync_playwright,expect,Error
  with sync_playwright() as p:
   browser=p.chromium.launch()
   for width in (1280,390):
    context=browser.new_context(viewport={'width':width,'height':900},accept_downloads=True)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:errors.append('HTTP '+str(r.status)+' '+r.url) if r.status>=500 and r.url.startswith('http://127.0.0.1:8765') else None)
    def go(path):
     page.goto('http://127.0.0.1:8765'+path)
     assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Horizontal overflow: '+path+' width '+str(width)
    username='qa'+str(width);password='Synthetic-Workflow-Password-42!'
    go('/signup/')
    page.locator('[name=username]').fill(username)
    for field in ('password1','password2'):page.locator('[name='+field+']').fill(password)
    page.get_by_role('button',name='Create account').click()
    expect(page.locator('.recovery-code')).to_be_visible();code=page.locator('.recovery-code').inner_text()
    go('/dashboard/');go('/applications/new/')
    for name,value in {'company':'Synthetic Private Company','role':'QA Analyst','description':'SQL Python testing','requirements':'SQL\nPython','notes':'Private fixture','next_step':'Practice interview','due':'2026-12-01'}.items():page.locator('[name='+name+']').fill(value)
    page.get_by_role('button',name='Save application').click()
    item=db(lambda: Application.objects.get(owner__username=username,company='Synthetic Private Company'));detail='/applications/'+str(item.pk)+'/'
    isolated=browser.new_context();second=isolated.new_page();second.goto('http://127.0.0.1:8765/login/');second.locator('[name=username]').fill('qa-isolation');second.locator('[name=password]').fill('Synthetic-Isolation-Password-42!');second.get_by_role('button',name='Sign in').click()
    assert isolated.request.get('http://127.0.0.1:8765'+detail).status==404
    assert isolated.request.get('http://127.0.0.1:8765'+detail+'edit/').status==404
    assert 'Private fixture' not in isolated.request.get('http://127.0.0.1:8765/dashboard/').text();isolated.close()
    go(detail+'edit/');page.locator('[name=stage]').select_option('interview');page.get_by_role('button',name='Save application').click()
    db(item.refresh_from_db);assert item.stage=='interview'
    go('/resume/');page.locator('[name=resume_file]').set_input_files({'name':'resume.txt','mimeType':'text/plain','buffer':b'Synthetic Candidate\nSQL Python testing project'})
    page.get_by_role('button',name='Save resume').click();assert 'SQL' in db(lambda: Profile.objects.get(user__username=username).resume)
    go('/resume/check/');page.locator('[name=resume]').fill('Synthetic SQL Python resume');page.locator('[name=description]').fill('SQL Python skills');page.get_by_role('button',name='Run resume checks').click();expect(page.get_by_text('Parsing review',exact=True)).to_be_visible()
    assert 'testing project' in db(lambda: Profile.objects.get(user__username=username).resume)
    go('/jobs/?role=analyst&level=entry&authorization=opt');expect(page.get_by_text('No matching openings.',exact=True)).to_be_visible()
    go('/jobs/?role=analyst&level=entry&authorization=opt&include_unknown=on');expect(page.get_by_role('link',name='Junior Data Analyst',exact=True)).to_be_visible()
    page.locator('[name=name]').fill('QA search');page.get_by_role('button',name='Save search').click()
    search=db(lambda: SavedSearch.objects.get(owner__username=username));go('/dashboard/');go('/jobs/')
    # Submit the actual CSRF-protected saved-search forms through the browser.
    page.locator('form[action="/searches/'+str(search.pk)+'/seen/"] button').click()
    assert db(lambda: SavedSearch.objects.get(pk=search.pk).seen) is not None
    go('/jobs/');page.locator('form[action="/searches/'+str(search.pk)+'/remove/"] button').click();assert not db(lambda: SavedSearch.objects.filter(pk=search.pk).exists())
    go('/jobs/'+str(job.pk)+'/');page.get_by_role('button',name='Save to workspace').click()
    assert db(lambda: Application.objects.filter(owner__username=username,source_url=job.url).count())==1
    go('/resume/build/')
    for name,value in {'name':'Synthetic Candidate','contact':'qa@example.com','skills':'SQL, Python','experience':'Local synthetic testing','education':'Synthetic degree'}.items():page.locator('[name='+name+']').fill(value)
    page.locator('[name=confirmed]').check();page.get_by_role('button',name='Preview').click();expect(page.get_by_text('Your resume preview',exact=True)).to_be_visible()
    for label,suffix in [('Download TXT','.txt'),('Download DOCX','.docx')]:
     with page.expect_download() as d:page.get_by_role('button',name=label).click()
     assert d.value.suggested_filename.endswith(suffix);assert d.value.failure() is None
    for route in ('/export/','/backup/','/calendar/'):
     with page.expect_download() as d:
      try:page.goto('http://127.0.0.1:8765'+route,wait_until='commit')
      except Error as e:
       if 'Download is starting' not in str(e):raise
     assert d.value.failure() is None
    go(detail);page.get_by_role('button',name='Archive application').click();db(item.refresh_from_db);assert item.archived
    go(detail);page.get_by_role('button',name='Restore from archive').click();db(item.refresh_from_db);assert not item.archived
    go('/account/password/');page.locator('[name=old_password]').fill(password);page.locator('[name=new_password1]').fill(password+'Updated');page.locator('[name=new_password2]').fill(password+'Updated');page.get_by_role('button',name='Update password').click();password+='Updated'
    go('/account/');page.locator('[name=timezone]').select_option('America/Chicago');page.get_by_role('button',name='Save timezone').click()
    assert db(lambda: Profile.objects.get(user__username=username).timezone)=='America/Chicago'
    page.locator('#recovery-password').fill(password);page.get_by_role('button',name='Replace recovery code').click();newcode=page.locator('.recovery-code').inner_text();assert newcode!=code
    context.clear_cookies();go('/recover/')
    for name,value in {'username':username,'recovery_code':newcode,'password1':password,'password2':password}.items():page.locator('[name='+name+']').fill(value)
    page.get_by_role('button',name='Reset password').click();expect(page.locator('.recovery-code')).to_be_visible()
    go('/account/');page.get_by_text('Delete account permanently',exact=True).click();page.locator('#delete-password').fill(password);page.locator('#confirmation').fill('DELETE');page.get_by_role('button',name='Permanently delete account').click()
    assert not db(lambda: User.objects.filter(username=username).exists());assert db(lambda: Job.objects.filter(pk=job.pk).exists())
    assert not errors,errors
    context.close();print('PASS Chromium '+str(width)+'px: signup, recovery, account, search, tracking, applications, resume import/build/download, exports, archive and deletion',flush=True)
   browser.close()
 finally:
  server.terminate();server.wait(timeout=10);log.close()
