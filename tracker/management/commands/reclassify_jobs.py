from django.core.management.base import BaseCommand
from django.utils import timezone
from tracker.models import Job,FeedState
from tracker.discovery import classify,seniority,evidence

class Command(BaseCommand):
    help='Recompute public cached listing labels once for the current normalization version.'
    def handle(self,*args,**options):
        marker,_=FeedState.objects.get_or_create(key='normalization-v3')
        if marker.success:return
        batch=[];count=0
        for job in Job.objects.only('id','title','description','role','level','evidence').iterator(chunk_size=100):
            job.role=classify(job.title);job.level=seniority(job.title);job.evidence=evidence(job.description)
            batch.append(job)
            if len(batch)==100:
                Job.objects.bulk_update(batch,['role','level','evidence'],batch_size=100)
                count+=len(batch);batch=[]
        if batch:
            Job.objects.bulk_update(batch,['role','level','evidence'],batch_size=100);count+=len(batch)
        marker.success=timezone.now();marker.count=count;marker.save(update_fields=['success','count'])
        self.stdout.write(f'Reclassified {count} public listings; private account data untouched.')
