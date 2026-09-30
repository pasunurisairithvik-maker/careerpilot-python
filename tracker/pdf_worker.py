"""Disposable bounded PDF parser subprocess. Receives bytes only; no database access."""
import io,sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(200*1024*1024,200*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(6,6))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(sys.stdin.buffer.read(2000001)),strict=True)
    if reader.is_encrypted or len(reader.pages)>10:raise ValueError()
    chunks=[];length=0
    for p in reader.pages:
        t=p.extract_text() or '';length+=len(t)+1
        if length>20000:raise ValueError()
        chunks.append(t)
    sys.stdout.write('\n'.join(chunks))
except Exception:sys.exit(1)
