import json, glob, re, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for s in ['raw-record','person','task-queue','dna','source']:
    p='schemas/%s.schema.json'%s
    t=open(p,encoding='utf-8').read()
    t2=t.replace('"const": "1.7"','"const": "1.8"')
    open(p,'w',encoding='utf-8').write(t2)
    print('const bumped' if t!=t2 else 'NO CHANGE', s)
n=0
pat=re.compile(r'("schema_version"\s*:\s*")1\.7(")')
for f in glob.glob('test/fixtures/**/*.json', recursive=True):
    t=open(f,encoding='utf-8').read()
    t2=pat.sub(r'\g<1>1.8\g<2>', t)
    if t!=t2:
        open(f,'w',encoding='utf-8').write(t2); n+=1
print('fixtures re-stamped:', n)
