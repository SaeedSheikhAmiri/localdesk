"""Image decoding in the same no-network, no-write document sandbox."""
import sys,io,json,base64,warnings,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CPU,(4,4))
try:
 from PIL import Image,ImageOps
 Image.MAX_IMAGE_PIXELS=10000000
 warnings.simplefilter('error',Image.DecompressionBombWarning)
 raw=sys.stdin.buffer.read(2097153)
 if len(raw)>2097152:raise ValueError()
 with Image.open(io.BytesIO(raw)) as original:
  if original.format not in ('JPEG','PNG','WEBP'):raise ValueError()
  original.load();image=ImageOps.exif_transpose(original);image.thumbnail((1024,1024));image=image.convert('RGB');image.info.clear();out=io.BytesIO();image.save(out,format='JPEG',quality=65,exif=b'',icc_profile=None)
  if len(out.getvalue())>200000:raise ValueError()
  result={'image':base64.b64encode(out.getvalue()).decode(),'width':image.width,'height':image.height,'characters':0}
except Exception:result={'error':'تصویر معتبر، قابل خواندن یا در محدودهٔ اندازه نیست.'}
sys.stdout.write(json.dumps(result))
