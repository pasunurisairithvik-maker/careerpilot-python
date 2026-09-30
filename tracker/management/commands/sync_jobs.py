from django.core.management.base import BaseCommand
from tracker.discovery import refresh
class Command(BaseCommand):
    help='Refresh the allowlisted public employer boards; preserve cached jobs on feed failure.'
    def add_arguments(self,parser):parser.add_argument('--force',action='store_true')
    def handle(self,*args,**options):self.stdout.write(str(refresh(force=options['force'])))
