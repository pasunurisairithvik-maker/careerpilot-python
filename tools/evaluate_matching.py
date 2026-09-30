"""Small authored diagnostic set, not a held-out real-world benchmark."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from tracker.matching import analyse
CASES=[
 ('Python developer','Built a Python API',True),
 ('Java developer','Built a JavaScript app',False),
 ('PostgreSQL developer','Postgres database project',True),
 ('Git developer','A legitimate project',False),
 ('C++ developer','C++ queue implementation',True),
 ('Java developer','No Java experience',False),
 ('Unit testing','Tested with pytest',True),
 ('Operating systems','Studied OS concepts',True),
 ('AWS developer','Amazon Web Services deployment',True),
 ('Python developer','Built a website',False),
]
def evaluate():
    rows=[];tp=fp=fn=tn=0
    for job,resume,expected in CASES:
        result=analyse(job,resume)
        predicted=result['matched']>0
        tp+=predicted and expected;fp+=predicted and not expected;fn+=not predicted and expected;tn+=not predicted and not expected
        rows.append({'job':job,'resume':resume,'expected_mention':expected,'predicted_mention':predicted})
    return {'dataset':'10 authored synthetic diagnostic cases; not representative or held out','true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'cases':rows}
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))
