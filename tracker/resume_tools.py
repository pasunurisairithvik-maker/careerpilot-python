"""Local-only document extraction and a truthful, editable resume generator."""
import io,re,zipfile,threading
PDF_SLOT=threading.BoundedSemaphore(1)
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from .matching import analyse
MAX_BYTES=2000000
MAX_TEXT=20000
def extract_file(f):
    raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('Maximum file size is 2 MB.')
    name=f.name.lower()
    if name.endswith('.txt'):
        if len(raw)>80000:raise ValueError('TXT files must be at most 80 KB.')
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:raise ValueError('TXT files must use UTF-8.')
    elif name.endswith('.docx'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(x.file_size for x in z.infolist())>10000000:raise ValueError('Document expands beyond the 10 MB limit.')
                content=z.read('word/document.xml')
            if b'<!DOCTYPE' in content or b'<!ENTITY' in content:raise ValueError('Unsafe XML is unsupported.')
            root=ET.fromstring(content);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text='\n'.join(''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in root.findall('.//w:p',ns))
        except (zipfile.BadZipFile,KeyError,ET.ParseError):raise ValueError('Could not read this DOCX file.')
    elif name.endswith('.pdf'):
        import subprocess,sys,os
        worker=os.path.join(os.path.dirname(__file__),'pdf_worker.py')
        if not PDF_SLOT.acquire(blocking=False):raise ValueError('PDF parser is busy. Try again or use TXT.')
        try:
            proc=subprocess.run([sys.executable,worker],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,env={'PATH':os.getenv('PATH','')})
        except subprocess.TimeoutExpired:raise ValueError('PDF parsing timed out. Use DOCX or TXT.')
        finally:PDF_SLOT.release()
        if proc.returncode:raise ValueError('PDF could not be parsed within safe limits. Use an unencrypted text PDF with at most 10 pages, DOCX or TXT.')
        text=proc.stdout.decode('utf-8')
        if not text.strip():raise ValueError('This PDF has no extractable text. Scans need OCR outside CareerPilot.')
    else:raise ValueError('Use a .txt, .docx or text-based .pdf file.')
    if '\x00' in text or len(text)>MAX_TEXT:raise ValueError('Use plain text of at most 20,000 characters.')
    if not text.strip():raise ValueError('No resume text was extracted.')
    return text

def checks(text,description=''):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    issues=[]
    if len(text)<300:issues.append('Very little text: check that the full resume was extracted.')
    if len(text.split())>1000:issues.append('More than 1,000 words: consider trimming repeated content.')
    if not re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',text):issues.append('No email address found in the extracted text.')
    sections={label:bool(re.search(r'(?im)^\s*'+pattern+r'\s*:?.*$',text)) for label,pattern in [('Experience','(?:work |professional )?experience|employment'),('Education','education|academic background'),('Skills','(?:technical )?skills'),('Projects','(?:selected |academic )?projects')]}
    for label,present in sections.items():
        if not present:issues.append(f'No recognizable {label} heading. Use a clear section heading when applicable.')
    if re.search(r'\ufffd|[\x00-\x08\x0b\x0c\x0e-\x1f]',text):issues.append('Extraction contains replacement or control characters; inspect the preview.')
    if any(len(x)>300 for x in lines):issues.append('Long extracted lines may indicate merged columns; check reading order in the preview.')
    quantified=sum(bool(re.search(r'\d+(?:%|\s*(?:users|seconds|hours|records|tests|requests))',x,re.I)) for x in lines)
    return {'issues':issues,'sections':sections,'words':len(text.split()),'lines':len(lines),'quantified':quantified,'match':analyse(description,text),'preview':text}

def build_text(fields,job=None):
    parts=[fields.get('name',''),fields.get('contact','')]
    summary=fields.get('summary','').strip()
    if summary:parts.extend(['','SUMMARY',summary])
    skills=[x.strip() for x in fields.get('skills','').split(',') if x.strip()]
    # Reorder only user-entered skills. Never insert missing job keywords.
    if job:
        from .matching import contains
        skills.sort(key=lambda s:not contains(job.description,s))
    if skills:parts.extend(['','SKILLS',', '.join(skills)])
    for key,label in [('experience','EXPERIENCE'),('projects','PROJECTS'),('education','EDUCATION')]:
        if fields.get(key,'').strip():parts.extend(['',label,fields[key].strip()])
    return '\n'.join(parts).strip()
def docx(text):
    ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    paragraphs=[]
    for i,line in enumerate(text.splitlines()):
        heading=line in ['SUMMARY','SKILLS','EXPERIENCE','PROJECTS','EDUCATION']
        prop='<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>' if heading or i==0 else '<w:rPr><w:sz w:val="22"/></w:rPr>'
        paragraphs.append('<w:p><w:pPr><w:spacing w:after="100"/></w:pPr><w:r>'+prop+'<w:t xml:space="preserve">'+escape(line)+'</w:t></w:r></w:p>')
    document=f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{ns}"><w:body>'+''.join(paragraphs)+'<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/></w:sectPr></w:body></w:document>'
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml',document)
    return out.getvalue()
