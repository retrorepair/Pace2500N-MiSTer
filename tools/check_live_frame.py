from PIL import Image
from pathlib import Path
r=Path("re/deployment/v047_live_ram.bin").read_bytes();im=Image.open("re/deployment/v047_guide_fixed.png").convert("RGB");w,h=im.size
pal=[]
for i in range(256):
 v=int.from_bytes(r[0x5e9468+i*2:0x5e946a+i*2],"big");yy=(((v>>8)&63)*4-16)*298;cb=((v>>4)&15)*16-128;cr=(v&15)*16-128
 pal.append(tuple(max(0,min(255,v>>8)) for v in [yy+409*cr,yy-100*cb-208*cr,yy+516*cb]))
bins=[0]*20;sample=[]
for y in range(h):
 base=[0x584048,0x5b6a58][y&1]+(y>>1)*720
 for x in range(w):
  expected=pal[r[base+x+x//8]];actual=im.getpixel((x,y))
  if max(abs(a-b) for a,b in zip(expected,actual))>2:
   bins[x*20//w]+=1
   if len(sample)<10 and y==165:sample.append((x,expected,actual))
print("mismatches by32-column bin",bins,"samples",sample)
