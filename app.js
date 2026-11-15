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
function setDims(w,h){adjusting=true;$('width').value=w;$('height').value=h;adjusting=false}
$('width').onchange=()=>{if(adjusting||!origW)return;const w=Number($('width').value);if($('ratio').checked)setDims(w,Math.max(1,Math.round(w*origH/origW)))};
$('height').onchange=()=>{if(adjusting||!origH)return;const h=Number($('height').value);if($('ratio').checked)setDims(Math.max(1,Math.round(h*origW/origH)),h)};
$('preset').onchange=()=>{if(!origW)return;const v=$('preset').value;if(v==='original')setDims(origW,origH);else {const [w,h]=v.split('x').map(Number);setDims(w,h)}};
const enable=()=>{$('quant').disabled=!py||!source||busy;for(const id of ['export','png','rom'])$(id).disabled=!result||busy;$('resized').disabled=!source||!py||busy};
async function loadFile(file,isExample=false){if(!file)return;const ext=(file.name.split('.').pop()||'').toLowerCase();if(!['png','bmp','gif','webp','jpg','jpeg','avif'].includes(ext)){status('Formato não suportado.','error');return}source=new Uint8Array(await file.arrayBuffer());sourceName=basename(file.name);result=false;$('memorial').hidden=!isExample;try{const bmp=await createImageBitmap(file);origW=bmp.width;origH=bmp.height;bmp.close();setDims(origW,origH);$('preset').value='original';$('fileinfo').textContent=`${file.name} · ${origW} × ${origH} · ${(file.size/1024).toFixed(1)} KiB`;const url=URL.createObjectURL(file);setImg('before',url);$('before').dataset.w=origW;$('before').dataset.h=origH;$('after').removeAttribute('src');$('after').dataset.w='';$('after').dataset.h='';applyZoom();status('Imagem carregada. Ajuste as opções e clique em Quantizar.');}catch(e){source=null;status('Não foi possível decodificar a imagem: '+e.message,'error')}enable()}
$('file').onchange=e=>loadFile(e.target.files[0]);const drop=$('drop');drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};drop.ondragleave=()=>drop.classList.remove('over');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');loadFile(e.dataTransfer.files[0])};
async function loadExample(){try{const response=await fetch('cholirede.png?v=example-1',{cache:'no-store'});if(!response.ok)throw Error('imagem de exemplo não publicada');const blob=await response.blob();if(source)return;await loadFile(new File([blob],'cholirede.png',{type:'image/png'}),true);$('preset').value='320x224';setDims(320,224);$('fileinfo').textContent+=' · exemplo';}catch(e){console.info('Exemplo indisponível:',e.message)}}
function validate(){const w=Number($('width').value),h=Number($('height').value);if(!Number.isInteger(w)||!Number.isInteger(h)||w<1||h<1||w>8192||h>8192||w*h>16000000)throw Error('Dimensões inválidas (máximo 8192 por eixo e 16 MP).');const tiles=Math.ceil(w/8)*Math.ceil(h/8),base=Number($('base').value),budget=Number($('budget').value);if(base>=2048||budget<1)throw Error('Orçamento ou tile inicial inválido.');return {width:w,height:h,palettes:Number($('palettes').value),colors:Number($('colors').value),iterations:Number($('iterations').value),dither:$('dither').value,dither_strength:Number($('strength').value),transparent:$('transparent').checked,background:$('background').value,base_tile:base,vram_budget_tiles:budget,allow_lossy_tiles:$('lossytiles').checked,resize:$('resize').value}}
function putInput(){py.FS.writeFile('/tmp/source.img',source)}
function download(bytes,name,mime){const url=dataUrl(bytes,mime);const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}
async function work(fn){if(busy)return;busy=true;enable();await new Promise(r=>setTimeout(r,60));try{await fn()}catch(e){status(e.message||String(e),'error')}finally{busy=false;enable()}}
$('quant').onclick=()=>work(async()=>{if(!py||!source)return;const opts=validate();status('Processando com o algoritmo Python original…');putInput();py.globals.set('opts_json',JSON.stringify(opts));await py.runPythonAsync(`import io,json,base64\nfrom PIL import Image\nfrom quantizer import Settings,quantize,vram_usage\nfrom tile_optimizer import optimize\nimport numpy as np\nopts=json.loads(opts_json)\noriginal=Image.open('/tmp/source.img');original.seek(0)\nresample=getattr(Image.Resampling,opts.pop('resize'))\nw=opts.pop('width');h=opts.pop('height')\nresized=original.convert('RGBA').resize((w,h),resample)\nconfig=Settings(**opts)\nresult=quantize(resized,config)
budget=min(config.vram_budget_tiles,2048-config.base_tile)
opt=optimize(result.indices,result.tile_palettes,budget=budget,allow_lossy=config.allow_lossy_tiles,palettes_rgb=result.palettes_rgb)
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
    result.preview=Image.fromarray(rgb[:h,:w],'RGB')
preview_io=io.BytesIO();result.preview.save(preview_io,format='PNG')\npreview_b64=base64.b64encode(preview_io.getvalue()).decode()\nresized_io=io.BytesIO();resized.save(resized_io,format='PNG')\nresized_b64=base64.b64encode(resized_io.getvalue()).decode()\nmetrics=json.dumps({'tiles':int(result.tile_palettes.size),'mse':round(float(result.mean_squared_error),2),'size':list(result.source_size),'unique':int(opt['unique_count']),'lossless':int(opt['lossless_unique']),'merges':int(opt['lossy_merges']),'fits':bool(opt['fits_budget'])})`);const b64=py.globals.get('preview_b64');const raw=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));setImg('after',dataUrl(raw));$('after').dataset.w=opts.width;$('after').dataset.h=opts.height;const resized=Uint8Array.from(atob(py.globals.get('resized_b64')),c=>c.charCodeAt(0));setImg('before',dataUrl(resized));$('before').dataset.w=opts.width;$('before').dataset.h=opts.height;applyZoom();const metrics=JSON.parse(py.globals.get('metrics'));$('stats').textContent=`${metrics.tiles} posições · ${metrics.unique} tiles únicos (${metrics.lossless} sem perda) · ${metrics.merges} substituições · erro RGB² ${metrics.mse}`;result=true;status(metrics.fits?'Quantização concluída. Tilemap otimizado pronto para exportação.':'Limite não atingido: não há tiles compatíveis suficientes para substituir. A exportação omitirá o tilemap. ',metrics.fits?'ok':'error')});
$('rom').onclick=()=>work(async()=>{if(!result)return;status('Gerando ROM de teste Mega Drive…');await py.runPythonAsync(`import base64,json\nfrom rom_test import build_test_rom\nrom_data,rom_info=build_test_rom(result)\nrom_b64=base64.b64encode(rom_data).decode()`);const b64=py.globals.get('rom_b64');const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));download(bytes,sourceName+'_megadrive_test.bin','application/octet-stream');status('ROM de teste gerada ('+bytes.length+' bytes). Valide primeiro no emulador antes do hardware real.','ok')});
$('png').onclick=()=>{if(!result)return;const b64=py.globals.get('preview_b64');download(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),sourceName+'_pal.png','image/png')};
$('resized').onclick=()=>work(async()=>{if(!source||!py)return;const w=Number($('width').value),h=Number($('height').value);if(w<1||h<1||w*h>16000000)throw Error('Dimensões inválidas');putInput();py.globals.set('rw',w);py.globals.set('rh',h);py.globals.set('resize_method',$('resize').value);await py.runPythonAsync(`import io,base64\nfrom PIL import Image\nim=Image.open('/tmp/source.img');im.seek(0)\nim=im.convert('RGBA').resize((rw,rh),getattr(Image.Resampling,resize_method))\nout=io.BytesIO();im.save(out,'PNG');resized_b64=base64.b64encode(out.getvalue()).decode()`);download(Uint8Array.from(atob(py.globals.get('resized_b64')),c=>c.charCodeAt(0)),sourceName+'_resized.png','image/png');status('PNG redimensionado exportado.','ok')});
$('export').onclick=()=>work(async()=>{if(!result)return;status('Gerando arquivos SGDK…');py.globals.set('prefix',sourceName+'_pal');await py.runPythonAsync(`import os,io,zipfile,base64\nfrom quantizer import export\nimport pathlib\nfolder=pathlib.Path('/tmp/sgdk_export');folder.mkdir(exist_ok=True)\nfor p in folder.iterdir():\n    if p.is_file():p.unlink()\nfiles=export(result,folder,prefix)\nbuf=io.BytesIO()\nwith zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:\n    for p in files:z.write(p,p.name)\nzip_b64=base64.b64encode(buf.getvalue()).decode()`);const b64=py.globals.get('zip_b64');download(Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),sourceName+'_sgdk.zip','application/zip');status('Pacote SGDK exportado com sucesso.','ok')});
loadExample();
(async()=>{try{if(typeof loadPyodide!=='function')throw Error('Biblioteca Pyodide indisponível. Verifique sua conexão.');py=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});$('engine').textContent='Carregando NumPy e Pillow…';await py.loadPackage(['numpy','pillow']);const r=await fetch('quantizer.py?v=colorzero-20261115a',{cache:'no-store'});if(!r.ok)throw Error('Não foi possível carregar quantizer.py');py.FS.writeFile('/home/pyodide/quantizer.py',await r.text());const opt=await fetch('tile_optimizer.py?v=rilden-orion-20261115f',{cache:'no-store'});if(!opt.ok)throw Error('Não foi possível carregar tile_optimizer.py');py.FS.writeFile('/home/pyodide/tile_optimizer.py',await opt.text());const romModule=await fetch('rom_test.py?v=colorzero-20261115a',{cache:'no-store'});if(!romModule.ok)throw Error('Não foi possível carregar rom_test.py');py.FS.writeFile('/home/pyodide/rom_test.py',await romModule.text());await py.runPythonAsync('import importlib, quantizer, tile_optimizer, rom_test; importlib.reload(tile_optimizer); importlib.reload(quantizer); assert "allow_lossy_tiles" in quantizer.Settings.__dataclass_fields__, "Motor Python desatualizado"');$('engine').textContent='Python pronto · processamento local';status('Motor pronto. Carregue uma imagem para começar.','ok');enable()}catch(e){$('engine').textContent='Falha ao iniciar';status('Erro na inicialização: '+e.message,'error')}})();
