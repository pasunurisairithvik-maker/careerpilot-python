"""Bounded, explainable phrase matching. This is not an ATS or hiring predictor."""
import re,unicodedata
SKILLS={
 'Python':['python'],'Java':['java'],'C++':['c++'],'C#':['c#'],
 'SQL':['sql'],'PostgreSQL':['postgresql','postgres'],'Django':['django'],'FastAPI':['fastapi'],
 'REST APIs':['rest','restful','rest api'],'Git':['git'],'Docker':['docker'],'Linux':['linux'],
 'AWS':['aws','amazon web services'],'S3':['s3'],'DynamoDB':['dynamodb'],'EC2':['ec2'],
 'Data structures':['data structures'],'Algorithms':['algorithms','algorithm'],'OOP':['oop','object-oriented','object oriented'],
 'Operating systems':['operating systems','operating system'],'Networking':['networking','network protocols'],
 'Unit testing':['unit tests','unit testing','pytest'],'CI/CD':['ci/cd','continuous integration'],
 'Machine learning':['machine learning'],'NLP':['nlp','natural language processing'],
 'Deep learning':['deep learning'],'Computer vision':['computer vision'],'PyTorch':['pytorch'],'TensorFlow':['tensorflow'],
 'Distributed systems':['distributed systems'],'Multithreading':['multithreading','multi-threading'],
 'Communication':['communication'],'Problem solving':['problem solving','problem-solving']}
def normalise(text):return unicodedata.normalize('NFKC',text).casefold()
def contains(text,phrase):return re.search(r'(?<!\w)'+re.escape(normalise(phrase))+r'(?!\w)',normalise(text)) is not None
def analyse(description,resume,requirements=''):
    custom=list(dict.fromkeys(x.strip() for x in requirements.splitlines() if x.strip()))[:30]
    selected=[(p,[p]) for p in custom] if custom else [(name,aliases) for name,aliases in SKILLS.items() if any(contains(description,p) for p in aliases)]
    rows=[]
    lines=[x.strip() for x in resume.splitlines() if x.strip()]
    for name,aliases in selected:
        evidence=next((line[:350] for line in lines if any(contains(line,p) for p in aliases)),None)
        rows.append({'skill':name,'found':evidence is not None,'evidence':evidence})
    matched=sum(r['found'] for r in rows)
    return {'rows':rows,'matched':matched,'total':len(rows),'coverage':round(100*matched/len(rows)) if rows else None,'method':'custom phrases' if custom else 'skill dictionary v1'}
