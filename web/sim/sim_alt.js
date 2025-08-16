(function(){
  const WIDTH = 250, HEIGHT = 122;
  const HEADER_NAME = [  6,  2, 160, 14];
  const HEADER_TIME = [172,  2,  72, 14];
  const INSIDE_TEMP = [  6, 36, 118, 28];
  const INSIDE_RH   = [  6, 66, 118, 14];
  const OUT_TEMP    = [131, 36,  90, 28];
  // Alt layout: larger icon and clearer separation
  const OUT_ICON    = [206, 58,  32, 32];
  const OUT_ROW1_L  = [131, 64,  44, 12]; // RH
  const OUT_ROW1_R  = [177, 64,  44, 12]; // mph
  const OUT_ROW2_L  = [131, 88,  90, 12]; // condition spans both small columns
  const STATUS      = [  6, 112, 238, 10];

  const canvas = document.getElementById('epd');
  const ctx = canvas.getContext('2d');
  canvas.style.imageRendering = 'pixelated';
  ctx.imageSmoothingEnabled = false;

  const FONT_STACK = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
  const SIZE_SMALL = 11;
  const SIZE_TIME = 11;
  const SIZE_BIG = 22;

  function text(x,y,str,size=10,weight='normal'){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px ${FONT_STACK}`;
    ctx.textBaseline = 'top';
    ctx.fillText(str, x, y);
  }

  function drawTempWithUnitsCentered(rect, valueStr){
    const [x,y,w,h] = rect;
    ctx.font = `bold ${SIZE_BIG}px ${FONT_STACK}`;
    const tw = ctx.measureText(valueStr).width;
    const rx = x + Math.max(0, Math.floor((w - tw) / 2));
    text(rx, y, valueStr, SIZE_BIG, 'bold');
    const degX = rx + tw + 2;
    const fX = degX + 6;
    text(degX, y + 4, '°', 12);
    text(fX,   y + 4, 'F', 12);
  }

  function clear(){ ctx.fillStyle = '#fff'; ctx.fillRect(0,0,WIDTH,HEIGHT); }

  function draw(data){
    clear();
    // frame
    ctx.fillStyle = '#000';
    ctx.fillRect(0,0,WIDTH,1); ctx.fillRect(0,HEIGHT-1,WIDTH,1); ctx.fillRect(0,0,1,HEIGHT); ctx.fillRect(WIDTH-1,0,1,HEIGHT);
    // rules
    ctx.fillRect(0,18,WIDTH,1);
    ctx.fillRect(125,18,1,77);
    // header
    text(HEADER_NAME[0], HEADER_NAME[1]+1, data.room_name||'Room', 12, 'bold');
    const t = data.time||'10:32';
    const tw = ctx.measureText(t).width;
    text(HEADER_TIME[0]+HEADER_TIME[2]-2-tw, HEADER_TIME[1]+1, t, SIZE_TIME);
    // labels
    text(6,22,'INSIDE',11,'bold');
    text(131,22,'OUTSIDE',11,'bold');
    // inside
    drawTempWithUnitsCentered(INSIDE_TEMP, `${data.inside_temp||'72.5'}`);
    text(INSIDE_RH[0], INSIDE_RH[1], `${data.inside_hum||'47'}% RH`, SIZE_SMALL);
    // outside
    drawTempWithUnitsCentered(OUT_TEMP, `${data.outside_temp||'68.4'}`);
    const rhText = `${data.outside_hum||'53'}% RH`;
    const mph = `${((parseFloat(data.wind||'4.2')||4.2)*2.237).toFixed(1)} mph`;
    text(OUT_ROW1_L[0], OUT_ROW1_L[1], rhText, SIZE_SMALL);
    text(OUT_ROW1_R[0], OUT_ROW1_R[1], mph, SIZE_SMALL);
    const cond = (data.weather||'Cloudy').split(/[ ,/:;-]/)[0];
    text(OUT_ROW2_L[0], OUT_ROW2_L[1], cond, SIZE_SMALL);
    // icon larger
    (async () => {
      const name = 'cloudy';
      const img = new Image();
      img.src = `icons/${name}.svg`;
      await new Promise(r=>{img.onload=r; img.onerror=r});
      const [x0,y0,w,h] = OUT_ICON; ctx.drawImage(img, x0, y0, w, h);
    })();
    // status (battery down 1px)
    const pct = parseInt(data.percent||'76',10);
    const bx = STATUS[0]; const by = STATUS[1]; const bw = 13, bh = 7;
    ctx.strokeStyle = '#000'; ctx.strokeRect(bx,by,bw,bh); ctx.fillStyle='#000';
    ctx.fillRect(bx+bw, by+2, 2, 4);
    const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100))));
    if (fillw>0) ctx.fillRect(bx+1, by+1, fillw, bh-2);
    const ip = `IP ${data.ip||'192.168.1.42'}`; const iw = ctx.measureText(ip).width;
    const ipX = STATUS[0]+STATUS[2]-2-iw; text(ipX, STATUS[1]-1, ip, 10);
    const left = `Batt ${data.voltage||'4.01'}V ${pct}% | ~${data.days||'128'}d`;
    text(STATUS[0]+bw+6, STATUS[1]-1, left, 10);
  }

  async function load(){
    draw({});
    try{
      const res = await fetch('sample_data.json');
      if (res.ok){ draw(await res.json()); }
    }catch(e){ /* ignore */ }
  }

  document.getElementById('refresh').addEventListener('click', load);
  load();
})();


