"""Isolated, bounded document-to-text worker. No file extraction or network."""
import sys,json,base64,io,zipfile,resource,tempfile,subprocess,struct,os
from pathlib import Path
MAX=60000

def jpeg_dimensions(raw):
 pos=2
 if not raw.startswith(b'\xff\xd8'):raise ValueError('تصویر JPEG معتبر نیست.')
 while pos+4<=len(raw):
  if raw[pos]!=255:raise ValueError('ساختار تصویر معتبر نیست.')
  marker=raw[pos+1];pos+=2
  if marker in (0xd8,0xd9):continue
  if marker==0xda:break
  length=int.from_bytes(raw[pos:pos+2],'big')
  if length<2 or pos+length>len(raw):raise ValueError('ساختار تصویر معتبر نیست.')
  if marker in (0xc0,0xc1,0xc2):return int.from_bytes(raw[pos+5:pos+7],'big'),int.from_bytes(raw[pos+3:pos+5],'big')
  pos+=length
 raise ValueError('ابعاد تصویر پیدا نشد.')
def strip_jpeg_metadata(raw):
 out=raw[:2];pos=2
 while pos+4<=len(raw):
  marker=raw[pos+1]
  if marker==0xda:return out+raw[pos:]
  length=int.from_bytes(raw[pos+2:pos+4],'big');end=pos+2+length
  if length<2 or end>len(raw):raise ValueError('تصویر معتبر نیست.')
  if not (0xe1<=marker<=0xef and marker!=0xee) and marker!=0xfe:out+=raw[pos:end]
  pos=end
 raise ValueError('تصویر معتبر نیست.')
def image_parse(raw):
 command=[sys.executable,'-I','-B',str(Path(__file__).resolve().parent/'image_worker.py')]
 result=subprocess.run(command,input=raw,capture_output=True,timeout=8)
 if result.returncode:raise ValueError('تصویر خوانده نشد؛ JPG یا PNG معتبر و کوچک‌تر انتخاب کن.')
 data=json.loads(result.stdout)
 if data.get('error'):raise ValueError(data['error'])
 jpeg=base64.b64decode(data['image'],validate=True);width,height=jpeg_dimensions(jpeg)
 if width>1024 or height>1024 or len(jpeg)>200000:raise ValueError('تصویر بیش از حد بزرگ است.')
 return data
def parse(name,raw):
 if not 0<len(raw)<=2*1024*1024:raise ValueError('حداکثر اندازهٔ فایل ۲ مگابایت است.')
 suffix=Path(name).suffix.lower()
 if suffix in ('.png','.jpg','.jpeg','.webp'):
  return image_parse(raw)
 if suffix in ('.txt','.md','.csv','.json','.tsv'):
  try:text=raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
  except UnicodeError:raise ValueError('فایل متنی باید UTF-8 یا UTF-16 باشد.')
 elif suffix=='.docx':
  import xml.etree.ElementTree as ET
  with zipfile.ZipFile(io.BytesIO(raw)) as archive:
   entries=archive.infolist()
   if len(entries)>2000 or sum(e.file_size for e in entries)>10*1024*1024:raise ValueError('ساختار فایل Word بیش از حد بزرگ است.')
   info=archive.getinfo('word/document.xml')
   if info.file_size>2*1024*1024:raise ValueError('متن Word بیش از حد بزرگ است.')
   xml=archive.read(info)
   if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise ValueError('ساختار XML فایل پشتیبانی نمی‌شود.')
   root=ET.fromstring(xml);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
   text='\n\n'.join(''.join(t.text or '' for t in p.iter(ns+'t')) for p in root.iter(ns+'p'))
 elif suffix=='.pdf':
  try:from pypdf import PdfReader
  except ImportError:raise ValueError('خواندن PDF در این نصب آماده نیست؛ متن را کپی کن.')
  reader=PdfReader(io.BytesIO(raw),strict=False)
  if reader.is_encrypted:raise ValueError('PDF رمزدار پشتیبانی نمی‌شود.')
  if len(reader.pages)>40:raise ValueError('حداکثر ۴۰ صفحهٔ PDF قابل خواندن است.')
  pages=[];size=0
  for number,page in enumerate(reader.pages,1):
   value=page.extract_text() or '';size+=len(value)
   if size>MAX:raise ValueError('متن فایل بیش از ۶۰ هزار حرف است؛ بخش کوتاه‌تری انتخاب کن.')
   if value.strip():pages.append('[صفحه '+str(number)+']\n'+value.strip())
  text='\n\n'.join(pages)
 else:raise ValueError('فرمت پشتیبانی نمی‌شود. TXT، MD، CSV، JSON، DOCX یا PDF متنی انتخاب کن.')
 text=text.replace('\r\n','\n').replace('\r','\n').strip()
 if not text or '\x00' in text:raise ValueError('متن قابل استفاده پیدا نشد. PDF اسکن‌شده به تبدیل تصویر به متن نیاز دارد.')
 if len(text)>MAX:raise ValueError('متن فایل بیش از ۶۰ هزار حرف است؛ بخش کوتاه‌تری انتخاب کن.')
 return {'title':name[:120],'text':text,'characters':len(text)}
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_CPU,(8,8))
 try:resource.setrlimit(resource.RLIMIT_DATA,(384*1024*1024,384*1024*1024))
 except (OSError,ValueError):pass
 try:
  d=json.loads(sys.stdin.buffer.read(2900000));raw=base64.b64decode(d['data'],validate=True);result=parse(d['name'],raw)
 except ValueError as e:result={'error':str(e)}
 except Exception:result={'error':'ساختار فایل معتبر یا قابل خواندن نیست.'}
 sys.stdout.write(json.dumps(result,ensure_ascii=False))
