#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA vision on IQ8 NPU: image -> YOLOv8 w8a8 DLC (HTP V75) -> Events.

Mirrors aura.vision.detector semantics but sources detections from qnn-net-run
on the Hexagon NPU. The w8a8 DLC has a built-in decode head emitting
boxes[8400,4] (xyxy, 640-space) + scores[8400] + class_idx[8400].
"""
import json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
import numpy as np, cv2

QNN='/opt/qnn'
DLC='/opt/aura-vision/models/yolov8_det_w8a8.dlc'
COCO80=['person','bicycle','car','motorcycle','airplane','bus','train','truck','boat','traffic light','fire hydrant','stop sign','parking meter','bench','bird','cat','dog','horse','sheep','cow','elephant','bear','zebra','giraffe','backpack','umbrella','handbag','tie','suitcase','frisbee','skis','snowboard','sports ball','kite','baseball bat','baseball glove','skateboard','surfboard','tennis racket','bottle','wine glass','cup','fork','knife','spoon','bowl','banana','apple','sandwich','orange','broccoli','carrot','hot dog','pizza','donut','cake','chair','couch','potted plant','bed','dining table','toilet','tv','laptop','mouse','remote','keyboard','cell phone','microwave','oven','toaster','sink','refrigerator','book','clock','vase','scissors','teddy bear','hair drier','toothbrush']

def iou(a,b):
    ix1,iy1=max(a[0],b[0]),max(a[1],b[1]); ix2,iy2=min(a[2],b[2]),min(a[3],b[3])
    iw,ih=max(0.,ix2-ix1),max(0.,iy2-iy1); inter=iw*ih
    if inter<=0: return 0.
    ua=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/ua if ua>0 else 0.

def nms(dets,thr=0.45,maxd=100):
    kept=[]
    for d in sorted(dets,key=lambda x:x[1],reverse=True):
        if len(kept)>=maxd: break
        if all(iou(d[2],k[2])<thr for k in kept): kept.append(d)
    return kept

def detect(img_path, conf=0.6, s=640, location=None):
    img=cv2.cvtColor(cv2.imread(img_path),cv2.COLOR_BGR2RGB)
    h,w=img.shape[:2]; sx,sy=w/s,h/s
    x=(cv2.resize(img,(s,s)).astype('float32')/255.).transpose(2,0,1)[None,...]
    with tempfile.TemporaryDirectory() as td:
        raw=os.path.join(td,'input.raw'); lst=os.path.join(td,'l.txt'); out=os.path.join(td,'out')
        x.astype('float32').tofile(raw)
        open(lst,'w').write('images:=%s\n'%raw); os.makedirs(out,exist_ok=True)
        env=dict(os.environ,LD_LIBRARY_PATH=QNN+'/lib:'+QNN+'/dsp',ADSP_LIBRARY_PATH=QNN+'/dsp')
        r=subprocess.run([QNN+'/bin/qnn-net-run','--backend',QNN+'/lib/libQnnHtp.so','--dlc_path',DLC,'--input_list',lst,'--output_dir',out],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        if r.returncode!=0: raise RuntimeError('qnn-net-run failed:\n'+r.stderr[-500:])
        rd=os.path.join(out,'Result_0')
        boxes=np.fromfile(rd+'/boxes.raw',dtype=np.float32).reshape(-1,4)
        scores=np.fromfile(rd+'/scores.raw',dtype=np.float32)
        cls=np.fromfile(rd+'/class_idx.raw',dtype=np.float32).astype(int)
    dets=[]
    for i in np.where(scores>=conf)[0]:
        b=boxes[i]; box=(float(b[0]*sx),float(b[1]*sy),float(b[2]*sx),float(b[3]*sy))
        dets.append((int(cls[i]),float(scores[i]),box))
    dets=nms(dets)
    ts=datetime.now(timezone.utc).isoformat(timespec='seconds')
    events=[]
    for cid,sc,box in dets:
        lbl=COCO80[cid] if 0<=cid<len(COCO80) else 'class_%d'%cid
        events.append({'event':'%s detected'%lbl,'timestamp':ts,'type':'detection','entities':[lbl],'location':location,'source':'vision','confidence':round(sc,3),'attributes':{'box':[int(v) for v in box]}})
    return events

if __name__=='__main__':
    p=sys.argv[1] if len(sys.argv)>1 else '/opt/aura-vision/data/bus.jpg'
    evs=detect(p,location='iq8-npu')
    counts={}
    for e in evs: counts[e['entities'][0]]=counts.get(e['entities'][0],0)+1
    print('== Scene (NPU) ==')
    print(', '.join('%d %s'%(n,l) for l,n in counts.items()) or 'nothing','in view')
    print('== Events ==')
    for e in evs: print(json.dumps(e))
