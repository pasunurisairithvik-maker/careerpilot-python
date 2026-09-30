import uuid
from django.conf import settings
from django.db import models

STAGES=[('saved','Saved'),('applied','Applied'),('screening','Screening'),('interview','Interview'),('offer','Offer'),('rejected','Rejected'),('withdrawn','Withdrawn')]
class Profile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='profile')
    timezone=models.CharField(max_length=50,default='Asia/Kolkata')
    recovery_hash=models.CharField(max_length=256)
    resume=models.TextField(max_length=20000,blank=True)
class Throttle(models.Model):
    key=models.CharField(primary_key=True,max_length=64)
    count=models.PositiveIntegerField(default=0)
    bucket=models.BigIntegerField()
class Application(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    company=models.CharField(max_length=100)
    role=models.CharField(max_length=150)
    source_url=models.URLField(max_length=500,blank=True)
    description=models.TextField(max_length=20000)
    requirements=models.TextField(max_length=3000,blank=True,help_text='Optional: one skill phrase per line. Overrides automatic skill detection. Maximum 30 phrases.')
    stage=models.CharField(max_length=12,choices=STAGES,default='saved')
    next_step=models.CharField(max_length=300,blank=True)
    due=models.DateField(null=True,blank=True)
    notes=models.TextField(max_length=3000,blank=True)
    submission_id=models.UUIDField(null=True,blank=True,editable=False)
    submission_hash=models.CharField(max_length=64,blank=True)
    created=models.DateTimeField(auto_now_add=True)
    updated=models.DateTimeField(auto_now=True)
    archived=models.BooleanField(default=False)
    class Meta:
        ordering=['-updated']
        indexes=[models.Index(fields=['owner','stage']),models.Index(fields=['owner','due'])]
        constraints=[models.UniqueConstraint(fields=['owner','submission_id'],name='application_submission_unique'),models.CheckConstraint(condition=models.Q(stage__in=[s[0] for s in STAGES]),name='application_stage_valid')]

class Job(models.Model):
    source_key=models.CharField(max_length=180,unique=True)
    provider=models.CharField(max_length=20)
    board=models.CharField(max_length=80)
    company=models.CharField(max_length=100)
    title=models.CharField(max_length=150)
    location=models.CharField(max_length=200,blank=True)
    description=models.TextField(max_length=20000)
    url=models.URLField(max_length=500)
    role=models.CharField(max_length=20)
    level=models.CharField(max_length=20)
    workplace=models.CharField(max_length=20)
    salary=models.TextField(max_length=1000,blank=True)
    evidence=models.JSONField(default=dict)
    source_updated=models.CharField(max_length=50,blank=True)
    first_seen=models.DateTimeField(auto_now_add=True)
    checked=models.DateTimeField()
    active=models.BooleanField(default=True)
    class Meta:
        ordering=['-first_seen','pk']
        indexes=[models.Index(fields=['active','role']),models.Index(fields=['company','board'])]
class FeedState(models.Model):
    key=models.CharField(max_length=120,primary_key=True)
    attempted=models.DateTimeField(null=True)
    success=models.DateTimeField(null=True)
    error=models.CharField(max_length=80,blank=True)
    count=models.PositiveIntegerField(default=0)
class SavedSearch(models.Model):
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    name=models.CharField(max_length=80)
    filters=models.JSONField(default=dict)
    created=models.DateTimeField(auto_now_add=True)
    seen=models.DateTimeField(null=True)
class ResumeDraft(models.Model):
    owner=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    fields=models.JSONField(default=dict)
    updated=models.DateTimeField(auto_now=True)
