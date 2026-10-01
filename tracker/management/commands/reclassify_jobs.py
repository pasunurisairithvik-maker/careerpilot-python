from django.core.management.base import BaseCommand
from django.utils import timezone
from tracker.models import Job,FeedState
from tracker.discovery import classify,seniority,evidence
from tracker.job_traits import level as jd_level,workplace as jd_workplace,salary as jd_salary

class Command(BaseCommand):
    help='Recompute public cached listing labels once for the current normalization version.'
    def handle(self,*args,**options):
        marker,_=FeedState.objects.get_or_create(key='normalization-v9')
        if marker.success:return
        batch=[];count=0;last_pk=marker.count;visited=0
        for job in Job.objects.filter(pk__gt=marker.count).only('id','title','description','role','level','evidence','location','workplace','salary').order_by('pk').iterator(chunk_size=100):
            role=classify(job.title,job.description);level=jd_level(job.title,job.description);statements=evidence(job.description)
            workplace,quote=jd_workplace(job.location,job.description,job.workplace);salary=jd_salary(job.description,job.salary)
            statements['workplace']={'state':workplace,'evidence':[quote]}
            if (job.role,job.level,job.evidence,job.workplace,job.salary)!=(role,level,statements,workplace,salary):
                job.role=role;job.level=level;job.evidence=statements;job.workplace=workplace;job.salary=salary;batch.append(job)
            visited+=1;last_pk=job.pk
            if visited%100==0:
                if batch:Job.objects.bulk_update(batch,['role','level','evidence','workplace','salary'],batch_size=100)
                count+=len(batch);batch=[]
                marker.count=last_pk;marker.save(update_fields=['count'])
        if batch:
            Job.objects.bulk_update(batch,['role','level','evidence','workplace','salary'],batch_size=100);count+=len(batch)
        marker.success=timezone.now();marker.count=last_pk;marker.save(update_fields=['success','count'])
        self.stdout.write(f'Reclassified {count} public listings; private account data untouched.')
