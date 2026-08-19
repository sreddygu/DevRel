# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
import sys, numpy as np, cv2
src, dst, s = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 640
img = cv2.imread(src)                    # BGR HxWx3
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]
img = cv2.resize(img, (s, s))
x = img.astype('float32') / 255.0
x = x.transpose(2, 0, 1)[None, ...]      # NCHW
x.astype('float32').tofile(dst)
print('preprocessed', src, '->', dst, 'orig', w, h, 'scale_x', w/s, 'scale_y', h/s)
