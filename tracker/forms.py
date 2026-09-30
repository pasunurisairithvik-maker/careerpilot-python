from django import forms
from django.contrib.auth.forms import UserCreationForm
from urllib.parse import urlsplit
from .models import Application
class RegisterForm(UserCreationForm):
    def clean_username(self):return super().clean_username().lower()
class RecoveryForm(forms.Form):
    username=forms.CharField(max_length=150)
    recovery_code=forms.CharField(widget=forms.PasswordInput,max_length=100)
    password1=forms.CharField(label='New password',widget=forms.PasswordInput)
    password2=forms.CharField(label='Confirm new password',widget=forms.PasswordInput)
class SettingsForm(forms.Form):
    timezone=forms.ChoiceField(choices=[('Asia/Kolkata','India'),('America/Chicago','US Central'),('America/New_York','US Eastern'),('America/Los_Angeles','US Pacific'),('Europe/London','UK'),('UTC','UTC')])
class ApplicationForm(forms.ModelForm):
    submission_id=forms.UUIDField(required=False,widget=forms.HiddenInput)
    class Meta:
        model=Application
        fields=['company','role','source_url','description','requirements','stage','next_step','due','notes']
        widgets={'description':forms.Textarea(attrs={'rows':8}),'requirements':forms.Textarea(attrs={'rows':3}),'notes':forms.Textarea(attrs={'rows':3}),'due':forms.DateInput(attrs={'type':'date'})}
    def clean_source_url(self):
        url=self.cleaned_data['source_url']
        if url:
            parsed=urlsplit(url)
            if parsed.scheme not in ['http','https'] or parsed.username or parsed.password:raise forms.ValidationError('Use an HTTP or HTTPS job URL without credentials.')
        return url
    def clean_requirements(self):
        value=self.cleaned_data['requirements']
        phrases=[x.strip() for x in value.splitlines() if x.strip()]
        if len(phrases)>30 or any(len(p)>80 for p in phrases):raise forms.ValidationError('Use up to 30 phrases, each at most 80 characters.')
        return '\n'.join(dict.fromkeys(phrases))
class ResumeForm(forms.Form):
    resume=forms.CharField(max_length=20000,required=False,label='Resume text',widget=forms.Textarea(attrs={'rows':16}),help_text='Paste your real resume. Maximum 20,000 characters.')
    resume_file=forms.FileField(required=False,label='Or import TXT (80 KB), DOCX or text-based PDF (2 MB, 10 PDF pages)')
    def clean(self):
        data=super().clean();f=data.get('resume_file')
        if f:
            from .resume_tools import extract_file
            try:data['resume']=extract_file(f)
            except ValueError as e:self.add_error('resume_file',str(e))
        return data
class ResumeBuilderForm(forms.Form):
    name=forms.CharField(max_length=150)
    contact=forms.CharField(max_length=300,help_text='Email, phone, city and optional portfolio links. Avoid sensitive identifiers.')
    summary=forms.CharField(max_length=1000,required=False,widget=forms.Textarea(attrs={'rows':3}))
    skills=forms.CharField(max_length=1500,required=False,help_text='Comma-separated skills you can demonstrate.')
    experience=forms.CharField(max_length=5000,required=False,widget=forms.Textarea(attrs={'rows':7}),help_text='Your actual employers, dates and achievements. No invented metrics.')
    projects=forms.CharField(max_length=5000,required=False,widget=forms.Textarea(attrs={'rows':7}))
    education=forms.CharField(max_length=1500,required=False,widget=forms.Textarea(attrs={'rows':3}))
    confirmed=forms.BooleanField(label='I reviewed these details and confirm they are truthful.')
