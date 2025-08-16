(function(){
  const WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h]
  const HEADER_NAME = [  6,  2, 160, 14];
  const HEADER_TIME = [172,  2,  72, 14];
  const INSIDE_TEMP = [  6, 36, 118, 28];
  const INSIDE_RH   = [  6, 66, 118, 14];
  const INSIDE_TIME = [  6, 82, 118, 12];
  const OUT_TEMP    = [131, 36,  90, 28];
  // Place icon higher so tests sampling around y=30 see non-white pixels
  const OUT_ICON    = [210, 22,  28, 28];
  // Move outside non-temp rows up by one row (12px) to close white space
  const OUT_ROW1_L  = [131, 66,  44, 12]; // top row: outside RH
  // widen right-top box so "99.9 mph" never truncates
  const OUT_ROW1_R  = [177, 66,  64, 12]; // top row: wind mph (widened)
  const OUT_ROW2_L  = [131, 84,  44, 12]; // bottom row: condition (spaced)
  const OUT_ROW2_R  = [177, 84,  44, 12]; // bottom row: reserved (H/L)
  const STATUS      = [  6, 112, 238, 10];

  const canvas = document.getElementById('epd');
  const ctx = canvas.getContext('2d');
  canvas.style.imageRendering = 'pixelated';
  ctx.imageSmoothingEnabled = false;
  let showWindows = false;
  let stressMode = false;
  let oneBitMode = true;

  const FONT_STACK = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
  const SIZE_SMALL = 11; // general small text
  const SIZE_STATUS = 10; // status row must fit 10px tall window
  const SIZE_LABEL = 11;
  const SIZE_TIME = 11;
  const SIZE_BIG = 22;
  const THRESH = 176;

  function clear(){
    ctx.fillStyle = '#fff';
    ctx.fillRect(0,0,WIDTH,HEIGHT);
    ctx.strokeStyle = '#000';
  }

  function text(x,y,str,size=10,weight='normal'){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px ${FONT_STACK}`;
    ctx.textBaseline = 'top';
    ctx.fillText(str, x, y);
  }

  function textTruncated(x, y, maxWidth, str, size=10, weight='normal'){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px ${FONT_STACK}`;
    ctx.textBaseline = 'top';
    let s = String(str||'');
    if (ctx.measureText(s).width <= maxWidth){ ctx.fillText(s, x, y); return; }
    while (s.length>1 && ctx.measureText(s + '…').width > maxWidth){ s = s.slice(0,-1); }
    ctx.fillText(s + '…', x, y);
  }

  function drawTextInRect(rect, str, size=10, weight='normal', align='left', pad=1){
    const [x,y,w,h] = rect;
    const maxW = Math.max(0, w - pad*2);
    ctx.save();
    ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
    ctx.font = `${weight} ${size}px ${FONT_STACK}`; ctx.textBaseline='top'; ctx.fillStyle='#000';
    let s = String(str||'');
    // truncate with ellipsis if needed
    if (ctx.measureText(s).width > maxW){
      while (s.length>1 && ctx.measureText(s + '…').width > maxW){ s = s.slice(0,-1); }
      s = s + '…';
    }
    let tx = x + pad;
    const tw = ctx.measureText(s).width;
    if (align === 'right') tx = x + w - pad - tw;
    else if (align === 'center') tx = x + Math.max(0, Math.floor((w - tw)/2));
    ctx.fillText(s, tx, y);
    ctx.restore();
  }

  function drawTempWithUnits(rect, valueStr){
    const [x, y, w, h] = rect;
    const unitsW = 14;
    // measure numeric width with big font and center within numeric sub-rect
    ctx.font = `bold ${SIZE_BIG}px ${FONT_STACK}`;
    const tw = ctx.measureText(valueStr).width;
    const numW = w - unitsW;
    const rx = x + Math.max(0, Math.floor((numW - tw) / 2));
    text(rx, y, valueStr, SIZE_BIG, 'bold');
    // Place units right after the number for tighter look
    const degX = rx + tw + 2;
    const fX = degX + 6;
    const unitY = y + 5; // drop by 1px for better baseline alignment
    text(degX, unitY, '°', 12);
    text(fX, unitY, 'F', 12);
  }

  function rect(x0,y0,x1,y1){
    ctx.strokeStyle = '#000';
    ctx.strokeRect(x0,y0,x1-x0,y1-y0);
  }

  // ---- SVG icon support (crisper icons) ----
  const iconCache = new Map(); // name -> HTMLImageElement or 'pending'
  async function loadSvgIcon(name){
    if(iconCache.has(name)) return iconCache.get(name);
    iconCache.set(name, 'pending');
    try{
      // Prefer local sim icons, then web/icons/mdi, then web/icons basic
      let res = await fetch(`icons/${name}.svg`);
      if(!res.ok){ res = await fetch(`../icons/mdi/${name}.svg`); }
      if(!res.ok){ res = await fetch(`../icons/${name}.svg`); }
      if(!res.ok) throw new Error('not ok');
      const svgText = await res.text();
      const blob = new Blob([svgText], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const img = new Image();
      const ready = new Promise((resolve)=>{ img.onload = ()=>resolve(img); });
      img.src = url;
      await ready;
      iconCache.set(name, img);
      return img;
    }catch(e){
      iconCache.delete(name);
      return null;
    }
  }

  function mapWeatherToIconName(w){
    const s = (w||'').toLowerCase();
    if(s.includes('clear')||s.includes('sun')) return 'clear';
    if(s.includes('part')) return 'partly';
    if(s.includes('cloud')) return 'cloudy';
    if(s.includes('rain')) return 'rain';
    if(s.includes('snow')) return 'snow';
    if(s.includes('storm')||s.includes('thunder')) return 'storm';
    if(s.includes('fog')||s.includes('mist')||s.includes('haze')) return 'fog';
    return 'cloudy';
  }

  function shortConditionLabel(w){
    const s = String(w||'').trim();
    if (!s) return 'Cloudy';
    // Split on common separators/qualifiers and keep the first token/word
    const lowered = s.toLowerCase();
    const cutPhrases = [' with ', ' and ', ',', '/', ' - '];
    let cutIndex = s.length;
    for (const sep of cutPhrases){
      const idx = lowered.indexOf(sep);
      if (idx >= 0 && idx < cutIndex) cutIndex = idx;
    }
    const first = s.slice(0, cutIndex).trim();
    // Additionally reduce to the first word to guarantee a single token like "Cloudy"
    return first.split(/\s+/)[0] || 'Cloudy';
  }

  async function weatherIcon(box, weather){
    const [x0,y0,x1,y1] = box;
    const w = x1-x0, h=y1-y0; const cx=x0+w/2, cy=y0+h/2;
    const scale = 1.5; // ~50% larger than base 20x20 box
    const effW = Math.round(Math.min(32, w*scale));
    const effH = Math.round(Math.min(32, h*scale));
    const ex0 = Math.round(x0 + (w - effW)/2);
    const ey0 = Math.round(y0 + (h - effH)/2);
    const ex1 = ex0 + effW;
    const ey1 = ey0 + effH;
    const kind = (weather||'').toLowerCase();
    // Try SVG first
    const name = kind.startsWith('moon_') ? kind : mapWeatherToIconName(kind);
    const svg = await loadSvgIcon(name);
    if(svg){
      // draw centered, allow to extend up to 24x24 (about 20% larger than 20x20 box)
      ctx.drawImage(svg, ex0, ey0, effW, effH);
      return;
    }
    ctx.strokeStyle = '#000';
    if(kind.includes('sun') || kind.includes('clear')){
      const rc = Math.min(effW,effH)/3;
      const ccx = (ex0+ex1)/2, ccy = (ey0+ey1)/2;
      ctx.beginPath(); ctx.arc(ccx,ccy,rc,0,Math.PI*2); ctx.stroke();
      const spikes = [[0,-rc-4],[0,rc+4],[-rc-4,0],[rc+4,0],[-3,-3],[3,3],[-3,3],[3,-3]];
      spikes.forEach(([dx,dy])=>{ ctx.beginPath(); ctx.moveTo(ccx,ccy); ctx.lineTo(ccx+dx,ccy+dy); ctx.stroke(); });
    } else if(kind.includes('part')){
      const rr = Math.min(effW,effH)/3;
      ctx.beginPath(); ctx.arc(ex0+rr+2,ey0+rr+2,rr,0,Math.PI*2); ctx.stroke();
      ctx.strokeRect(ex0+2,ey0+effH/2,effW-4,effH-6);
    } else if(kind.includes('cloud')){
      ctx.strokeRect(ex0+2,ey0+8,effW-4,effH-12);
      ctx.beginPath(); ctx.arc(ex0+Math.min(12,effW/2),ey0+10,8,0,Math.PI*2); ctx.stroke();
      ctx.beginPath(); ctx.arc(ex0+Math.min(24,effW-2),ey0+8,8,0,Math.PI*2); ctx.stroke();
    } else if(kind.includes('rain')){
      weatherIcon([ex0,ey0,ex1,ey1],'cloudy');
      for(let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(ex0+8+i*6,ey0+effH-6); ctx.lineTo(ex0+4+i*6,ey0+effH+2); ctx.stroke(); }
    } else if(kind.includes('snow')){
      weatherIcon([ex0,ey0,ex1,ey1],'cloudy');
      ctx.fillText('*', ex0+10, ey0+effH-6);
      ctx.fillText('*', ex0+18, ey0+effH-6);
    } else if(kind.includes('fog')){
      for(let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(ex0+2,ey0+8+i*6); ctx.lineTo(ex1-2,ey0+8+i*6); ctx.stroke(); }
    } else {
      rect(ex0,ey0,ex1,ey1);
    }
  }

  const DEFAULTS = {
    room_name: 'Office',
    time: '10:32',
    inside_temp: '72.5',
    inside_hum: '47',
    outside_temp: '68.4',
    outside_hum: '53',
    weather: 'Cloudy',
    wind: '4.2',
    percent: 76,
    voltage: '4.01',
    days: '128',
    ip: '192.168.1.42'
  };
  let lastData = { ...DEFAULTS };

  function draw(data){
    console.log('[sim] draw()', data);
    if (data && typeof data === 'object' && Object.keys(data).length) lastData = data;
    clear();
    // Frame (crisp 1px border)
    ctx.fillStyle = '#000';
    ctx.fillRect(0,0,WIDTH,1);
    ctx.fillRect(0,HEIGHT-1,WIDTH,1);
    ctx.fillRect(0,0,1,HEIGHT);
    ctx.fillRect(WIDTH-1,0,1,HEIGHT);
    // Header
    ctx.fillStyle = '#000';
    // thin rules only
    ctx.fillRect(0,18,WIDTH,1);
    // extend center divider all the way to the bottom frame (to y=HEIGHT-1)
    ctx.fillRect(125,18,1,HEIGHT-18-1);
    // left name, right time
    ctx.fillStyle = '#000';
    const t = data.time || '10:32';
    const tw = ctx.measureText(t).width;
    const timeX = HEADER_TIME[0] + HEADER_TIME[2] - 2 - tw;
    // Reserve a hard 4px gap before the time block
    const maxNameW = Math.max(0, timeX - 4 - HEADER_NAME[0]);
    textTruncated(HEADER_NAME[0], HEADER_NAME[1]+1, Math.min(maxNameW, HEADER_NAME[2]-2), data.room_name || 'Room', 12, 'bold');
    text(timeX, HEADER_TIME[1]+1, t, SIZE_TIME);

    // Labels centered above their columns
    ctx.fillStyle = '#000';
    const insideLabel = 'INSIDE';
    const outsideLabel = 'OUTSIDE';
    ctx.font = `${SIZE_LABEL}px ${FONT_STACK}`;
    const ilw = ctx.measureText(insideLabel).width;
    const olw = ctx.measureText(outsideLabel).width;
    const ilx = INSIDE_TEMP[0] + Math.floor((INSIDE_TEMP[2] - ilw) / 2);
    let olx = OUT_TEMP[0] + Math.floor((OUT_TEMP[2] - olw) / 2);
    text(ilx, 22, insideLabel, SIZE_LABEL, 'bold');

    // Values: numeric right-aligned with fixed units strip
    const numIn = `${data.inside_temp||'72.5'}`;
    drawTempWithUnits(INSIDE_TEMP, numIn);
    text(INSIDE_RH[0], INSIDE_RH[1], `${data.inside_hum||'47'}% RH`, SIZE_SMALL);
    // Omit duplicate time here; header shows time

    const numOut = `${data.outside_temp||'68.4'}`;
    drawTempWithUnits(OUT_TEMP, numOut);
    // two-column lower info: move condition to left-top, swap wind/humidity positions, show wind in mph
    const condition = shortConditionLabel(data.weather || 'Cloudy');
    const rhText = `${data.outside_hum||'53'}% RH`;
    let windMps = parseFloat(data.wind || '4.2');
    if (!isFinite(windMps)) windMps = 4.2;
    const wind = `${(windMps*2.237).toFixed(1)} mph`;
    // Left/right small rows within clipped boxes to prevent overlap
    drawTextInRect(OUT_ROW1_L, rhText, SIZE_SMALL, 'normal', 'left', 1);
    // keep wind fully readable; prefer full text over ellipsis
    ctx.font = `${SIZE_SMALL}px ${FONT_STACK}`;
    const wBox = OUT_ROW1_R; const needed = ctx.measureText(wind).width + 2;
    const windRect = [wBox[0], wBox[1], Math.max(wBox[2], needed), wBox[3]];
    drawTextInRect(windRect, wind, SIZE_SMALL, 'normal', 'right', 1);
    // Unified layout: split + three-row status
    // Three-row left status and right weather area
    ctx.fillStyle = '#fff';
    ctx.fillRect(STATUS[0], STATUS[1]-18, 125-STATUS[0], STATUS[3]+22);
    ctx.fillRect(125, STATUS[1]-18, WIDTH-125-1, STATUS[3]+22);
    ctx.fillStyle = '#000';
    const pct = parseInt(data.percent||'76', 10);
    const bx = STATUS[0] + 1, bw = 13, bh = 7;
    const baseY = STATUS[1] - 18;
    // horizontal rule above status
    ctx.fillStyle = '#000';
    ctx.fillRect(0, baseY - 2, WIDTH, 1);
    ctx.fillStyle = '#000';
    // ensure center divider reaches bottom
    ctx.fillRect(125, 18, 1, HEIGHT-18-1);
    // Battery glyph
    ctx.strokeStyle = '#000'; ctx.strokeRect(bx, baseY, bw, bh); ctx.fillStyle = '#000';
    ctx.fillRect(bx + bw, baseY + 2, 2, 4);
    const fillw3 = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100)))); if (fillw3>0) ctx.fillRect(bx+1, baseY+1, fillw3, bh-2);
    // Rows
    const leftTextX = bx + bw + 6;
    text(leftTextX, baseY-2, `Batt ${data.voltage||'4.01'}V`, SIZE_STATUS);
    text(leftTextX, baseY+8, `~${data.days||'128'}d   ${pct}%`, SIZE_STATUS);
    const ip = `IP ${data.ip||'192.168.1.42'}`; const iw = ctx.measureText(ip).width;
    const leftColRight = 125 - 2;
    const ipAreaLeft = leftTextX; const ipAreaRight = leftColRight;
    const ipCenterLeft = ipAreaLeft + Math.max(0, Math.floor((ipAreaRight - ipAreaLeft - iw) / 2));
    ctx.fillStyle = '#fff'; ctx.fillRect(ipAreaLeft-1, baseY+17, ipAreaRight-ipAreaLeft+2, SIZE_STATUS+2);
    ctx.fillStyle = '#000';
    text(ipCenterLeft, baseY+18, ip, SIZE_STATUS);
    // Right weather: scale icon and fit label
    const cond = shortConditionLabel(data.weather||'Cloudy');
    const barX = 130, barW = 114, gap = 8, barY = 95;
    let candidateIcon = 26;
    function fitLabel(iconSize){
      const maxText = barW - iconSize - gap - 2;
      let s = cond;
      while (ctx.measureText(s).width > maxText && s.length > 1) s = s.slice(0,-1);
      if (s !== cond && s.length>1) s = s.slice(0,-1) + '…';
      return {label:s, fits: ctx.measureText(s).width <= maxText, icon: iconSize};
    }
    let fit = fitLabel(candidateIcon);
    while (!fit.fits && candidateIcon > 18){ candidateIcon--; fit = fitLabel(candidateIcon); }
    const label = fit.label; const iconW = fit.icon, iconH = fit.icon;
    const totalW = iconW + gap + ctx.measureText(label).width;
    const startX = barX + Math.max(0, Math.floor((barW - totalW)/2));
    const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
    weatherIcon([startX, barY, startX+iconW, barY+iconH], iconSelector);
    const labelTop = barY + Math.max(0, Math.floor((iconH - SIZE_SMALL)/2)) + 1;
    text(startX + iconW + gap, labelTop, label, SIZE_SMALL);
    // Draw OUTSIDE label once
    text(olx, 22, outsideLabel, SIZE_LABEL, 'bold');

    // Single-row status removed; unified split3 layout renders status above

    // partial window overlay
    if (showWindows){
      ctx.strokeStyle = '#888';
      ctx.setLineDash([3,2]);
      const rects = [HEADER_NAME, HEADER_TIME, INSIDE_TEMP, INSIDE_RH, INSIDE_TIME, OUT_TEMP, OUT_ICON, OUT_ROW1_L, OUT_ROW1_R, OUT_ROW2_L, OUT_ROW2_R, STATUS];
      rects.forEach(([x,y,w,h])=>{ ctx.strokeRect(x,y,w,h); });
      ctx.setLineDash([]);
    }

    // Optional: convert to 1-bit threshold rendering pass
    if (oneBitMode){
      const img = ctx.getImageData(0,0,WIDTH,HEIGHT);
      const d = img.data;
      // Simple luminance threshold; e-ink tends to dither, but we do hard threshold for clarity
      for (let i=0;i<d.length;i+=4){
        const r=d[i], g=d[i+1], b=d[i+2];
        const y = 0.2126*r + 0.7152*g + 0.0722*b;
        const v = y < THRESH ? 0 : 255; // slightly lighter to reduce blotting
        d[i]=d[i+1]=d[i+2]=v;
        d[i+3]=255;
      }
      ctx.putImageData(img,0,0);
    }
  }

  async function load(){
    // Draw defaults immediately for instant feedback
    draw(lastData);
    try{
      const res = await fetch('sample_data.json');
      if(!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      console.log('[sim] loaded sample_data.json');
      lastData = data;
      draw(lastData);
    } catch(e){
      console.warn('[sim] using defaults', e);
    }
  }

  // Partial update demo on refresh: only redraw time region
  document.getElementById('refresh').addEventListener('click', async ()=>{
    try{
      const res = await fetch('sample_data.json');
      const data = await res.json();
      data.time = new Date().toTimeString().slice(0,5);
      // clear the header time box and redraw just that region (right-aligned)
      const [hx,hy,hw,hh] = HEADER_TIME;
      ctx.fillStyle = '#fff';
      ctx.fillRect(hx,hy,hw,hh);
      const tw = ctx.measureText(data.time).width;
      text(hx + hw - 2 - tw, hy+1, data.time, SIZE_TIME);
      // brief outline to show the partial region
      ctx.strokeStyle = '#000';
      ctx.strokeRect(hx,hy,hw,hh);
      setTimeout(()=>{ /* no-op */ }, 100);
    }catch(e){
      load();
    }
  });
  document.getElementById('showWindows').addEventListener('change', (e)=>{
    showWindows = !!e.target.checked;
    clear();
    draw({});
  });
  document.getElementById('stressMode').addEventListener('change', (e)=>{
  const layoutSel = document.getElementById('layoutMode');
  if (layoutSel){
    layoutSel.addEventListener('change', ()=>{
      clear();
      draw(lastData);
      setTimeout(()=>draw(lastData), 0);
    });
  }
    stressMode = !!e.target.checked;
    // draw immediately with extreme values to reveal layout issues
    const stress = {
      room_name: 'Extremely Long Room Name Example',
      time: '23:59',
      inside_temp: '-10.2',
      inside_hum: '100',
      outside_temp: '-10.2',
      outside_hum: '100',
      weather: 'Thunderstorms and very windy with heavy rain bands',
      wind: '99.9',
      high: '199.9',
      low: '-40.0',
      moon_phase: '',
      percent: 12,
      voltage: '3.42',
      days: '1',
      ip: '10.1.2.3'
    };
    clear();
    draw(stressMode ? stress : {});
  });
  load();
})();


