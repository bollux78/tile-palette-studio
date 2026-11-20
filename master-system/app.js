'use strict';
const $=id=>document.getElementById(id);let py=null,source=null,sourceName='',result=false,busy=false,origW=0,origH=0,adjusting=false;
const status=(s,kind='')=>{$('status').textContent=s;$('status').className='status '+kind};
const basename=s=>s.replace(/\.[^.]+$/,'').replace(/[^\w-]/g,'_')||'art';
function dataUrl(bytes,type='image/png'){const b=new Blob([bytes],{type});return URL.createObjectURL(b)}
function setImg(id,url){const img=$(id);if(img.dataset.url?.startsWith('blob:'))URL.revokeObjectURL(img.dataset.url);img.src=url;img.dataset.url=url;applyZoom()}
function applyZoom(){const z=Number($('zoom').value);$('zoomlabel').textContent=z+'×';for(const id of ['before','after']){const im=$(id);im.style.width=im.dataset.w?Number(im.dataset.w)*z+'px':'auto';im.style.height=im.dataset.h?Number(im.dataset.h)*z+'px':'auto';const view=im.closest('.viewport');if(view){const imageHeight=Number(im.dataset.h)||224;view.style.height=Math.min(imageHeight*z,Math.max(240,Math.floor(window.innerHeight*.70)))+'px'}}}
// Both previews show the same image coordinates when zooming or panning.
const viewports=[...document.querySelectorAll('.viewport')];
let syncingScroll=false,previousZoom=Number($('zoom').value);
function syncViewport(origin){
  if(syncingScroll)return;
  syncingScroll=true;
  const maxX=Math.max(0,origin.scrollWidth-origin.clientWidth);
  const maxY=Math.max(0,origin.scrollHeight-origin.clientHeight);
  const rx=maxX?origin.scrollLeft/maxX:0,ry=maxY?origin.scrollTop/maxY:0;
  for(const other of viewports){
    if(other===origin)continue;
    other.scrollLeft=rx*Math.max(0,other.scrollWidth-other.clientWidth);
    other.scrollTop=ry*Math.max(0,other.scrollHeight-other.clientHeight);
  }
  requestAnimationFrame(()=>{syncingScroll=false});
}
function changeZoom(next,origin=viewports[0],anchorX=origin.clientWidth/2,anchorY=origin.clientHeight/2){
  const previous=previousZoom;
  next=Math.max(Number($('zoom').min),Math.min(Number($('zoom').max),next));
  if(next===previous)return;
  const x=origin.scrollLeft+anchorX,y=origin.scrollTop+anchorY;
  $('zoom').value=String(next);
  applyZoom();
  previousZoom=next;
  origin.scrollLeft=x*next/previous-anchorX;
  origin.scrollTop=y*next/previous-anchorY;
  syncViewport(origin);
}
$('zoom').oninput=()=>{
  const next=Number($('zoom').value);
  $('zoom').value=String(previousZoom);
  changeZoom(next);
};
window.addEventListener('resize',()=>{applyZoom();syncViewport(viewports[0])});
viewports.forEach(view=>{
  view.addEventListener('scroll',()=>syncViewport(view),{passive:true});
  view.addEventListener('wheel',e=>{
    e.preventDefault();
    const rect=view.getBoundingClientRect();
    changeZoom(previousZoom+(e.deltaY<0?1:-1),view,e.clientX-rect.left,e.clientY-rect.top);
  },{passive:false});
});
$('strength').oninput=()=>$('strengthlabel').textContent=$('strength').value;
$('iterations').oninput=()=>$('iterationslabel').textContent=$('iterations').value;
let cropBitmap=null,cropSelection=null,cropStart=null,cropPointer=null;
const cropCanvas=$('cropCanvas'),cropContext=cropCanvas.getContext('2d');
function cropPoint(e){const r=cropCanvas.getBoundingClientRect();return {x:Math.max(0,Math.min(origW,Math.round((e.clientX-r.left)*origW/r.width))),y:Math.max(0,Math.min(origH,Math.round((e.clientY-r.top)*origH/r.height)))}}
function drawCrop(){
  cropContext.clearRect(0,0,cropCanvas.width,cropCanvas.height);
  if(!cropBitmap)return;
  cropContext.drawImage(cropBitmap,0,0,cropCanvas.width,cropCanvas.height);
  const b=cropSelection,valid=b&&b[2]>b[0]&&b[3]>b[1];$('applyCrop').disabled=!valid;
  $('cropInfo').textContent=valid?`Área selecionada: ${b[2]-b[0]} × ${b[3]-b[1]} pixels`:'Arraste para selecionar uma área.';
  if(!valid)return;
  const sx=cropCanvas.width/origW,sy=cropCanvas.height/origH,x=b[0]*sx,y=b[1]*sy,w=(b[2]-b[0])*sx,h=(b[3]-b[1])*sy;
  cropContext.fillStyle='rgba(0,0,0,.55)';cropContext.beginPath();cropContext.rect(0,0,cropCanvas.width,cropCanvas.height);cropContext.rect(x,y,w,h);cropContext.fill('evenodd');
  cropContext.strokeStyle='#fff';cropContext.lineWidth=2;cropContext.strokeRect(x,y,w,h);
}
$('openCrop').onclick=async()=>{if(!source||busy)return;try{cropBitmap?.close();cropBitmap=await createImageBitmap(new Blob([source]));const scale=Math.min(1,1200/origW,800/origH);cropCanvas.width=Math.max(1,Math.round(origW*scale));cropCanvas.height=Math.max(1,Math.round(origH*scale));cropStart=null;cropPointer=null;try{cropSelection=editOptions().crop}catch{cropSelection=null}drawCrop();$('cropDialog').showModal()}catch(e){status('Não foi possível abrir o recorte: '+e.message,'error')}};
cropCanvas.onpointerdown=e=>{if(e.button!==0||cropPointer!==null)return;e.preventDefault();cropPointer=e.pointerId;cropStart=cropPoint(e);cropCanvas.setPointerCapture(e.pointerId);cropSelection=null;drawCrop()};
cropCanvas.onpointermove=e=>{if(cropPointer!==e.pointerId||!cropStart)return;const p=cropPoint(e);cropSelection=[Math.min(cropStart.x,p.x),Math.min(cropStart.y,p.y),Math.max(cropStart.x,p.x),Math.max(cropStart.y,p.y)];drawCrop()};
cropCanvas.onpointerup=e=>{if(cropPointer!==e.pointerId)return;cropCanvas.onpointermove(e);cropStart=null;cropPointer=null;if(cropCanvas.hasPointerCapture(e.pointerId))cropCanvas.releasePointerCapture(e.pointerId)};
cropCanvas.onpointercancel=()=>{cropStart=null;cropPointer=null;cropSelection=null;drawCrop()};
$('cancelCrop').onclick=()=>$('cropDialog').close();
$('cropDialog').addEventListener('close',()=>{cropBitmap?.close();cropBitmap=null;cropStart=null;cropPointer=null});
$('applyCrop').onclick=()=>{const b=cropSelection;if(!b||b[2]<=b[0]||b[3]<=b[1])return;$('cropx').value=b[0];$('cropy').value=b[1];$('cropw').value=b[2]-b[0];$('croph').value=b[3]-b[1];$('crop').checked=true;$('crop').onchange();$('cropDialog').close();if(py)$('previewEdits').onclick()};
function editOptions(){
  const crop=$('crop').checked;
  const x=Number($('cropx').value),y=Number($('cropy').value),w=Number($('cropw').value),h=Number($('croph').value);
  if(crop&&(![x,y,w,h].every(Number.isInteger)||x<0||y<0||w<1||h<1||x+w>origW||y+h>origH))throw Error('Recorte fora dos limites da imagem original.');
  return {crop:crop?[x,y,x+w,y+h]:null,brightness:Number($('brightness').value)/100,contrast:Number($('contrast').value)/100,sharpness:Number($('sharpness').value)/100};
}
function invalidateEdits(){result=false;$('after').removeAttribute('src');$('stats').textContent='';enable();status('Ajustes alterados. Atualize a prévia ou quantize novamente.');}
function resetEdits(){for(const id of ['brightness','contrast','sharpness']){$(id).value=100;$(id+'label').textContent='100'}$('crop').checked=false;$('cropx').value=0;$('cropy').value=0;$('cropw').value=origW||1;$('croph').value=origH||1;}
for(const id of ['brightness','contrast','sharpness'])$(id).oninput=()=>{$(id+'label').textContent=$(id).value;invalidateEdits()};
for(const id of ['crop','cropx','cropy','cropw','croph'])$(id).onchange=()=>{if($('preset').value==='original'&&source){try{const e=editOptions();setDims(e.crop?e.crop[2]-e.crop[0]:origW,e.crop?e.crop[3]-e.crop[1]:origH)}catch{}}invalidateEdits()};
$('resetEdits').onclick=()=>{if(busy)return;resetEdits();if(source){if($('preset').value==='original')setDims(origW,origH);setImg('before',dataUrl(source));$('before').dataset.w=origW;$('before').dataset.h=origH;applyZoom();invalidateEdits()}};
$('previewEdits').onclick=()=>work(async()=>{const edits=editOptions();putInput();py.globals.set('edits_json',JSON.stringify(edits));await py.runPythonAsync("import io,json,base64\nfrom PIL import Image\nfrom image_prepare import prepare_image\nim=prepare_image(Image.open('/tmp/source.img'),json.loads(edits_json))\nout=io.BytesIO();im.save(out,'PNG')\nedited_b64=base64.b64encode(out.getvalue()).decode()\nedited_size=json.dumps(im.size)");const size=JSON.parse(py.globals.get('edited_size'));$('before').dataset.w=size[0];$('before').dataset.h=size[1];setImg('before',dataUrl(Uint8Array.from(atob(py.globals.get('edited_b64')),c=>c.charCodeAt(0))));status('Prévia preparada. Quantize para atualizar o resultado.');});
function setDims(w,h){adjusting=true;$('width').value=w;$('height').value=h;adjusting=false}
$('width').onchange=()=>{$('preset').value='original'};
$('height').onchange=()=>{$('preset').value='original'};
$('preset').onchange=()=>{if(!origW)return;const v=$('preset').value;if(v==='original'){const e=editOptions();setDims(e.crop?e.crop[2]-e.crop[0]:origW,e.crop?e.crop[3]-e.crop[1]:origH)}else {const [w,h]=v.split('x').map(Number);setDims(w,h)}};
const enable=()=>{$('quant').disabled=!py||!source||busy;for(const id of ['export','png','rom'])$(id).disabled=!result||busy;$('resized').disabled=!source||!py||busy;$('previewEdits').disabled=!source||!py||busy;$('openCrop').disabled=!source||busy;for(const id of ['brightness','contrast','sharpness','crop','cropx','cropy','cropw','croph','resetEdits'])$(id).disabled=busy};
async function loadFile(file,isExample=false){if(!file)return;const ext=(file.name.split('.').pop()||'').toLowerCase();if(!['png','bmp','gif','webp','jpg','jpeg','avif'].includes(ext)){status('Formato não suportado.','error');return}source=new Uint8Array(await file.arrayBuffer());sourceName=basename(file.name);result=false;$('memorial').hidden=!isExample;try{const bmp=await createImageBitmap(file);origW=bmp.width;origH=bmp.height;bmp.close();resetEdits();setDims(origW,origH);$('preset').value='original';$('fileinfo').textContent=`${file.name} · ${origW} × ${origH} · ${(file.size/1024).toFixed(1)} KiB`;const url=URL.createObjectURL(file);setImg('before',url);$('before').dataset.w=origW;$('before').dataset.h=origH;$('after').removeAttribute('src');$('after').dataset.w='';$('after').dataset.h='';applyZoom();status('Imagem carregada. Ajuste as opções e clique em Quantizar.');}catch(e){source=null;status('Não foi possível decodificar a imagem: '+e.message,'error')}enable()}
$('file').onchange=e=>loadFile(e.target.files[0]);const drop=$('drop');drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};drop.ondragleave=()=>drop.classList.remove('over');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');loadFile(e.dataTransfer.files[0])};
async function loadExample(){try{const response=await fetch('../cholirede.png?v=example-1',{cache:'no-store'});if(!response.ok)throw Error('imagem de exemplo não publicada');const blob=await response.blob();if(source)return;await loadFile(new File([blob],'cholirede.png',{type:'image/png'}),true);$('preset').value='256x192';setDims(256,192);$('fileinfo').textContent+=' · exemplo';}catch(e){console.info('Exemplo indisponível:',e.message)}}
function validate(){const w=Number($('width').value),h=Number($('height').value);if(!Number.isInteger(w)||!Number.isInteger(h)||w<1||h<1||w>8192||h>8192||w*h>16000000)throw Error('Dimensões inválidas (máximo 8192 por eixo e 16 MP).');const tiles=Math.ceil(w/8)*Math.ceil(h/8),base=Number($('base').value),budget=Number($('budget').value);if(base>=448||budget<1)throw Error('Orçamento ou tile inicial inválido.');return {edits:editOptions(),width:w,height:h,palettes:Number($('palettes').value),colors:Number($('colors').value),iterations:Number($('iterations').value),dither:$('dither').value,dither_strength:Number($('strength').value),transparent:$('transparent').checked,background:$('background').value,base_tile:base,vram_budget_tiles:budget,allow_lossy_tiles:$('lossytiles').checked,resize:$('resize').value,keep_aspect:$('ratio').checked}}
function putInput(){py.FS.writeFile('/tmp/source.img',source)}
function download(bytes,name,mime){const url=dataUrl(bytes,mime);const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}
async function work(fn){if(busy)return;busy=true;enable();await new Promise(r=>setTimeout(r,60));try{await fn()}catch(e){status(e.message||String(e),'error')}finally{busy=false;enable()}}
$('quant').onclick=()=>work(async()=>{if(!py||!source)return;const opts=validate();status('Processando com o algoritmo Python original…');putInput();py.globals.set('opts_json',JSON.stringify(opts));await py.runPythonAsync(`import io,json,base64\nfrom PIL import Image\nfrom sms_quantizer import Settings,quantize,vram_usage\nfrom tile_optimizer import optimize\nimport numpy as np\nopts=json.loads(opts_json)\noriginal=Image.open('/tmp/source.img');original.seek(0)\nresample=getattr(Image.Resampling,opts.pop('resize'))\nw=opts.pop('width');h=opts.pop('height')\nkeep_aspect=opts.pop('keep_aspect',False)\nfrom image_prepare import prepare_image\nsource_rgba=prepare_image(original,opts.pop('edits'))\nif keep_aspect:\n    from PIL import ImageOps\n    fitted=ImageOps.contain(source_rgba,(w,h),method=resample)\n    resized=Image.new('RGBA',(w,h),(0,0,0,255))\n    if opts.get('transparent',False):\n        resized.paste(fitted,((w-fitted.width)//2,(h-fitted.height)//2))\n    else:\n        resized.alpha_composite(fitted,((w-fitted.width)//2,(h-fitted.height)//2))\nelse:\n    resized=source_rgba.resize((w,h),resample)\nconfig=Settings(**opts)\nresult=quantize(resized,config)
budget=min(config.vram_budget_tiles,448-config.base_tile)
opt=optimize(result.indices,result.tile_palettes,budget=budget,allow_lossy=config.allow_lossy_tiles,palettes_rgb=result.palettes_rgb,reserve_zero=config.transparent)
if config.allow_lossy_tiles and opt['lossy_merges']:
    ty,tx=result.tile_palettes.shape
    remade=np.empty((ty*8,tx*8),dtype=np.uint8)
    for k,(idx,flip) in enumerate(zip(opt['mapping'],opt['flips'])):
        tile=opt['tiles'][int(idx)]
        if int(flip)&0x0800: tile=tile[:,::-1]
        if int(flip)&0x1000: tile=tile[::-1,:]
        remade[(k//tx)*8:(k//tx+1)*8,(k%tx)*8:(k%tx+1)*8]=tile
    result.indices=remade
    rgb=np.empty((ty*8,tx*8,3),dtype=np.uint8)
    for iy in range(ty):
        for ix in range(tx):
            p=int(result.tile_palettes[iy,ix])
            rgb[iy*8:(iy+1)*8,ix*8:(ix+1)*8]=result.palettes_rgb[p][remade[iy*8:(iy+1)*8,ix*8:(ix+1)*8]]
    alpha=result.preview.getchannel('A')
    result.preview=Image.fromarray(rgb[:h,:w],'RGB').convert('RGBA')
    result.preview.putalpha(alpha)
    visible=np.asarray(resized.getchannel('A'))>=config.alpha_threshold if config.transparent else np.ones((h,w),dtype=bool)
    delta=rgb[:h,:w].astype(np.float32)-np.asarray(resized.convert('RGB')).astype(np.float32)
    result.mean_squared_error=float(np.mean(delta[visible]**2)) if visible.any() else 0.0
preview_io=io.BytesIO();result.preview.save(preview_io,format='PNG')\npreview_b64=base64.b64encode(preview_io.getvalue()).decode()\nresized_io=io.BytesIO();resized.save(resized_io,format='PNG')\nresized_b64=base64.b64encode(resized_io.getvalue()).decode()\nmetrics=json.dumps({'tiles':int(result.tile_palettes.size),'mse':round(float(result.mean_squared_error),2),'size':list(result.source_size),'unique':int(opt['unique_count']),'lossless':int(opt['lossless_unique']),'merges':int(opt['lossy_merges']),'fits':bool(opt['fits_budget'])})`);const b64=py.globals.get('preview_b64');const raw=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));setImg('after',dataUrl(raw));$('after').dataset.w=opts.width;$('after').dataset.h=opts.height;const resized=Uint8Array.from(atob(py.globals.get('resized_b64')),c=>c.charCodeAt(0));setImg('before',dataUrl(resized));$('before').dataset.w=opts.width;$('before').dataset.h=opts.height;applyZoom();const metrics=JSON.parse(py.globals.get('metrics'));$('stats').textContent=`${metrics.tiles} posições · ${metrics.unique} tiles únicos (${metrics.lossless} sem perda) · ${metrics.merges} substituições · erro RGB² ${metrics.mse}`;result=true;status(metrics.fits?'Quantização concluída. Tilemap otimizado pronto para exportação.':'Quantização concluída. Excede o orçamento de tiles: reduza a imagem ou ative a substituição por similares antes de exportar pacote ou ROM.', 'ok')});
$('rom').onclick=()=>work(async()=>{if(!result)return;status('Gerando ROM de teste Master System…');await py.runPythonAsync("import base64\nfrom sms_rom import build_test_rom\nrom_data,rom_info=build_test_rom(result)\nrom_b64=base64.b64encode(rom_data).decode()");download(Uint8Array.from(atob(py.globals.get('rom_b64')),c=>c.charCodeAt(0)),sourceName+'_master_system.sms','application/octet-stream');status('ROM de teste Master System gerada · 256 × 192.','ok')});
$('png').onclick=()=>{if(!result)return;const b64=py.globals.get('preview_b64');download(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),sourceName+'_pal.png','image/png')};
$('resized').onclick=()=>work(async()=>{if(!source||!py)return;const w=Number($('width').value),h=Number($('height').value);if(w<1||h<1||w*h>16000000)throw Error('Dimensões inválidas');const edits=editOptions();putInput();py.globals.set('edits_json',JSON.stringify(edits));py.globals.set('rw',w);py.globals.set('rh',h);py.globals.set('resize_method',$('resize').value);py.globals.set('keep_aspect_export',$('ratio').checked);py.globals.set('preserve_alpha_export',$('transparent').checked);await py.runPythonAsync("import io,base64\nfrom PIL import Image,ImageOps\nim=Image.open('/tmp/source.img');im.seek(0)\nfrom image_prepare import prepare_image\nimport json\nim=prepare_image(im,json.loads(edits_json))\nmethod=getattr(Image.Resampling,resize_method)\nif keep_aspect_export:\n    fitted=ImageOps.contain(im,(rw,rh),method)\n    canvas=Image.new('RGBA',(rw,rh),(0,0,0,255))\n    if preserve_alpha_export:\n        canvas.paste(fitted,((rw-fitted.width)//2,(rh-fitted.height)//2))\n    else:\n        canvas.alpha_composite(fitted,((rw-fitted.width)//2,(rh-fitted.height)//2))\n    im=canvas\nelse:\n    im=im.resize((rw,rh),method)\nout=io.BytesIO();im.save(out,'PNG');resized_b64=base64.b64encode(out.getvalue()).decode()");download(Uint8Array.from(atob(py.globals.get('resized_b64')),c=>c.charCodeAt(0)),sourceName+'_resized.png','image/png');status('PNG redimensionado exportado.','ok')});
$('export').onclick=()=>work(async()=>{if(!result)return;status('Gerando arquivos Master System…');py.globals.set('prefix',sourceName+'_pal');await py.runPythonAsync(`import os,io,zipfile,base64\nfrom sms_quantizer import export\nimport pathlib\nfolder=pathlib.Path('/tmp/sms_export');folder.mkdir(exist_ok=True)\nfor p in folder.iterdir():\n    if p.is_file():p.unlink()\nfiles=export(result,folder,prefix)\nbuf=io.BytesIO()\nwith zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:\n    for p in files:z.write(p,p.name)\nzip_b64=base64.b64encode(buf.getvalue()).decode()`);const b64=py.globals.get('zip_b64');download(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),sourceName+'_sms.zip','application/zip');status('Pacote Master System exportado com sucesso.','ok')});
loadExample();
(async()=>{try{
if(typeof loadPyodide!=='function')throw Error('Biblioteca Pyodide indisponível. Verifique sua conexão.');
py=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
$('engine').textContent='Carregando NumPy e Pillow…';await py.loadPackage(['numpy','pillow']);
for(const name of ['image_prepare.py','sms_quantizer.py','tile_optimizer.py','sms_rom.py']){const r=await fetch('../'+name+'?v=tile-clustering-20261120',{cache:'no-store'});if(!r.ok)throw Error('Falha ao carregar '+name);py.FS.writeFile('/home/pyodide/'+name,await r.text())}
await py.runPythonAsync('import sms_quantizer, tile_optimizer, sms_rom');
$('engine').textContent='Python pronto · Master System · processamento local';status('Motor Master System pronto.','ok');enable()
}catch(e){$('engine').textContent='Falha ao iniciar';status('Erro na inicialização: '+e.message,'error')}})();
