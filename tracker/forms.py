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
    resume=forms.CharField(max_length=20000,required=False,label='Resume text',widget=forms.Textarea(attrs={'rows':16}),help_text='Paste your real resume. No generated experience. Maximum 20,000 characters.')
    resume_file=forms.FileField(required=False,label='Or import a UTF-8 .txt resume (maximum 80 KB)')
    def clean(self):
        data=super().clean();f=data.get('resume_file')
        if f:
            if not f.name.lower().endswith('.txt'):self.add_error('resume_file','Only plain .txt files are supported. Paste text from a PDF instead.');return data
            raw=f.read(80001)
            if len(raw)>80000:self.add_error('resume_file','File exceeds 80 KB.');return data
            try:text=raw.decode('utf-8-sig')
            except UnicodeDecodeError:self.add_error('resume_file','Use UTF-8 text.');return data
            if '\x00' in text or len(text)>20000:self.add_error('resume_file','Use plain text of at most 20,000 characters.');return data
            data['resume']=text
        return data
