(function(){
  const WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h]
  const HEADER_NAME = [  6,  2, 160, 14];
  const HEADER_TIME = [172,  2,  72, 14];
  const INSIDE_TEMP = [  6, 36, 118, 28];
  const INSIDE_RH   = [  6, 66, 118, 14];
  const INSIDE_TIME = [  6, 82, 118, 12];
  const OUT_TEMP    = [131, 36,  90, 28];
  const OUT_ICON    = [210, 66,  28, 28];
  // Move outside non-temp rows up by one row (12px) to close white space
  const OUT_ROW1_L  = [131, 66,  44, 12]; // top row: outside RH
  const OUT_ROW1_R  = [177, 66,  44, 12]; // top row: wind mph
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
    drawTextInRect(OUT_ROW1_R, wind, SIZE_SMALL, 'normal', 'right', 1);
    const mode = (document.getElementById('layoutMode')||{value:'classic'}).value;
    if (mode === 'banner') {
      // Full-height right banner for weather: large icon + condition stacked
      const ICON = [200, 30, 48, 48];
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([ICON[0],ICON[1],ICON[0]+ICON[2],ICON[1]+ICON[3]], iconSelector);
      // condition centered below icon
      const cond = shortConditionLabel(data.weather||'Cloudy');
      const cw = ctx.measureText(cond).width;
      const cx = ICON[0] + Math.max(0, Math.floor((ICON[2]-cw)/2));
      text(cx, ICON[1]+ICON[3]+2, cond, SIZE_SMALL);
      // shift outside label a bit left to visually balance
      olx = OUT_TEMP[0] + 4;
      text(olx, 22, outsideLabel, SIZE_LABEL, 'bold');
    } else if (mode === 'badges') {
      // Pill badges for RH and mph to separate from condition
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([214,50,30,30], iconSelector);
      // draw badges
      function badge(x,y,label){
        const pad = 4; const w = ctx.measureText(label).width + pad*2; const h = 14;
        ctx.fillStyle = '#000'; ctx.fillRect(x,y,w,h);
        ctx.fillStyle = '#fff'; ctx.fillText(label, x+pad, y+2);
        ctx.fillStyle = '#000';
      }
      badge(OUT_ROW1_L[0], OUT_ROW1_L[1]-2, `${data.outside_hum||'53'}%`);
      badge(OUT_ROW1_R[0], OUT_ROW1_R[1]-2, `${((parseFloat(data.wind||'4.2')||4.2)*2.237).toFixed(1)} mph`);
      // condition on its own line
      text(OUT_ROW2_L[0], OUT_ROW2_L[1]+2, shortConditionLabel(data.weather||'Cloudy'), SIZE_SMALL);
    } else if (mode === 'split') {
      // Bottom split bar dedicated to icon + condition spanning width
      ctx.fillStyle = '#000'; ctx.fillRect(0, 98, WIDTH, 1); ctx.fillStyle = '#000';
      const ICON = [130, 100, 16, 16];
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([ICON[0],ICON[1],ICON[0]+ICON[2],ICON[1]+ICON[3]], iconSelector);
      const cond = shortConditionLabel(data.weather||'Cloudy');
      text(ICON[0]+ICON[2]+6, 100, cond, SIZE_SMALL);
    } else if (mode === 'splitxl') {
      // Full bottom-right corner as weather panel: keep IP/status intact
      ctx.fillStyle = '#000'; ctx.fillRect(0, 98, WIDTH, 1); ctx.fillStyle = '#000';
      const PANEL_X = 170, PANEL_Y = 96, PANEL_W = 74, PANEL_H = 24;
      const ICON = [PANEL_X, PANEL_Y+4, 18, 18];
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([ICON[0],ICON[1],ICON[0]+ICON[2],ICON[1]+ICON[3]], iconSelector);
      text(ICON[0]+ICON[2]+6, PANEL_Y+4, condition, SIZE_SMALL);
      // Clear any prior condition above to avoid duplicates
      ctx.fillStyle = '#fff';
      ctx.fillRect(OUT_ROW2_L[0], OUT_ROW2_L[1]-1, OUT_ROW2_L[2], OUT_ROW2_L[3]+2);
      ctx.fillStyle = '#000';
    } else if (mode === 'split2') {
      // Two-row status at bottom; bottom-right weather icon+cond
      ctx.fillStyle = '#000'; ctx.fillRect(0, 98, WIDTH, 1); ctx.fillStyle = '#000';
      const pct = parseInt(data.percent||'76', 10);
      // Move entire status block up by one row (approx 10px)
      const baseY = STATUS[1] - 10; // move whole two-row block up one row
      const bx = STATUS[0], by = baseY; const bw = 13, bh = 7;
      ctx.strokeStyle = '#000'; ctx.strokeRect(bx, by, bw, bh); ctx.fillStyle = '#000';
      ctx.fillRect(bx + bw, by + 2, 2, 4);
      const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100)))); if (fillw>0) ctx.fillRect(bx+1, by+1, fillw, bh-2);
      // top row: Batt V %
      text(bx + bw + 6, baseY-2, `Batt ${data.voltage||'4.01'}V ${pct}%`, SIZE_STATUS);
      // bottom row: ~days and IP right-aligned WITHIN LEFT COLUMN only (up to x=125)
      const rightText = `~${data.days||'128'}d    IP ${data.ip||'192.168.1.42'}`;
      const rw = ctx.measureText(rightText).width;
      const leftColRight = 125 - 2; // just inside the center divider
      const ipLeft = Math.max(STATUS[0] + bw + 6, leftColRight - rw);
      text(ipLeft, baseY+7, rightText, SIZE_STATUS);
      // Bottom-right bar: center icon+condition within a right-side panel to avoid clipping
      // Use most of the right half for centering; raise bar items by 1px
      const barX = 130, barW = 114, iconW = 16, iconH = 16, gap = 8, barY = 99;
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      // Fit condition text to available width
      let label = condition;
      const maxTextW = barW - iconW - gap;
      while (ctx.measureText(label).width > maxTextW && label.length > 1) {
        label = label.slice(0, -1);
      }
      if (label !== condition && label.length > 1) label = label.slice(0, -1) + '…';
      const totalW = iconW + gap + ctx.measureText(label).width;
      const startX = barX + Math.max(0, Math.floor((barW - totalW)/2));
      // Clear any prior condition above to avoid duplicates
      ctx.fillStyle = '#fff'; ctx.fillRect(OUT_ROW2_L[0], OUT_ROW2_L[1]-1, OUT_ROW2_L[2], OUT_ROW2_L[3]+2);
      ctx.fillStyle = '#000';
      weatherIcon([startX, barY, startX+iconW, barY+iconH], iconSelector);
      text(startX + iconW + gap, barY, label, SIZE_SMALL);
      // Clear any prior condition above to avoid duplicates
      ctx.fillStyle = '#fff';
      ctx.fillRect(OUT_ROW2_L[0], OUT_ROW2_L[1]-1, OUT_ROW2_L[2], OUT_ROW2_L[3]+2);
      ctx.fillStyle = '#000';
    } else if (mode === 'split3') {
      // Three-row left status: row1 Batt V %, row2 ~days, row3 IP; right: taller weather area
      // Clear previous single-row status artifacts in left & right halves
      ctx.fillStyle = '#fff';
      ctx.fillRect(STATUS[0], STATUS[1]-18, 125-STATUS[0], STATUS[3]+22);
      ctx.fillRect(125, STATUS[1]-18, WIDTH-125-1, STATUS[3]+22);
      ctx.fillStyle = '#000';
      const pct = parseInt(data.percent||'76', 10);
      // Slight right inset for cleaner left margin and subtle vertical lift
      const bx = STATUS[0] + 1, bw = 13, bh = 7;
      // Lift the left stack so the IP row fits fully within 122px height
      // baseY + 18 (IP row top) + 10 (font height) <= 122 → baseY <= 94
      const baseY = STATUS[1] - 18; // 112-18 = 94
      // Draw the horizontal rule just above the battery row across the entire screen
      ctx.fillStyle = '#000';
      ctx.fillRect(0, baseY - 2, WIDTH, 1);
      ctx.fillStyle = '#000';
      // Re-draw the center divider after the clears so it reaches the bottom
      ctx.fillRect(125, 18, 1, HEIGHT-18-1);
      // Battery glyph
      ctx.strokeStyle = '#000'; ctx.strokeRect(bx, baseY, bw, bh); ctx.fillStyle = '#000';
      ctx.fillRect(bx + bw, baseY + 2, 2, 4);
      const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100)))); if (fillw>0) ctx.fillRect(bx+1, baseY+1, fillw, bh-2);
      // Row 1: Batt V (percent moved to row 2 per request)
      const leftTextX = bx + bw + 6;
      text(leftTextX, baseY-2, `Batt ${data.voltage||'4.01'}V`, SIZE_STATUS);
      // Row 2: ~days plus percent
      text(leftTextX, baseY+8, `~${data.days||'128'}d   ${pct}%`, SIZE_STATUS);
      // Row 3: IP centered within the usable left column (avoid battery glyph area)
      const ip = `IP ${data.ip||'192.168.1.42'}`; const iw = ctx.measureText(ip).width;
      const leftColRight = 125 - 2;
      const ipAreaLeft = leftTextX; const ipAreaRight = leftColRight;
      const ipCenterLeft = ipAreaLeft + Math.max(0, Math.floor((ipAreaRight - ipAreaLeft - iw) / 2));
      // Clear IP row rect before drawing to prevent any previous overlap
      ctx.fillStyle = '#fff'; ctx.fillRect(ipAreaLeft-1, baseY+17, ipAreaRight-ipAreaLeft+2, SIZE_STATUS+2);
      ctx.fillStyle = '#000';
      text(ipCenterLeft, baseY+18, ip, SIZE_STATUS);
      // Right: larger icon + condition centered
      const cond = shortConditionLabel(data.weather||'Cloudy');
      // Allocate more height for icon
      const barX = 130, barW = 114, gap = 8, barY = 95;
      // Dynamically choose largest icon size that fits with label and 2px right padding
      let candidateIcon = 26; // try up to 26px tall
      let label = cond;
      // choose icon size and possibly shorten label
      function fitLabel(iconSize){
        const maxText = barW - iconSize - gap - 2;
        let s = cond;
        while (ctx.measureText(s).width > maxText && s.length > 1) s = s.slice(0,-1);
        if (s !== cond && s.length>1) s = s.slice(0,-1) + '…';
        return {label:s, fits: ctx.measureText(s).width <= maxText, icon: iconSize};
      }
      let fit = fitLabel(candidateIcon);
      while (!fit.fits && candidateIcon > 18){ candidateIcon--; fit = fitLabel(candidateIcon); }
      label = fit.label; const iconW = candidateIcon, iconH = candidateIcon;
      const totalW = iconW + gap + ctx.measureText(label).width;
      const startX = barX + Math.max(0, Math.floor((barW - totalW)/2));
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([startX, barY, startX+iconW, barY+iconH], iconSelector);
      const labelTop = barY + Math.max(0, Math.floor((iconH - SIZE_SMALL)/2)) + 1; // drop by 1px optically
      text(startX + iconW + gap, labelTop, label, SIZE_SMALL);
      // Ensure the divider is still visible on top (some icons may overlap)
      ctx.fillRect(125, 18, 1, HEIGHT-18-1);
    } else if (mode === 'icon') {
      // icon-dominant: big icon area, shift outside label left edge to align with OUT_TEMP
      const ICON = [204, 50, 44, 44];
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([ICON[0],ICON[1],ICON[0]+ICON[2],ICON[1]+ICON[3]], iconSelector);
      // draw a faint separator line between RH/mph and condition
      ctx.strokeStyle = '#000';
      ctx.globalAlpha = 0.25;
      ctx.beginPath(); ctx.moveTo(OUT_TEMP[0], 82); ctx.lineTo(OUT_TEMP[0]+OUT_TEMP[2], 82); ctx.stroke();
      ctx.globalAlpha = 1.0;
    } else if (mode === 'spacious') {
      // spacious: slightly larger icon and more breathing room for text
      const ICON = [212, 60,  34, 34];
      const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
      weatherIcon([ICON[0],ICON[1],ICON[0]+ICON[2],ICON[1]+ICON[3]], iconSelector);
      text(OUT_ROW2_L[0], OUT_ROW2_L[1], condition, SIZE_SMALL);
    } else {
    const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
    weatherIcon([OUT_ICON[0],OUT_ICON[1],OUT_ICON[0]+OUT_ICON[2],OUT_ICON[1]+OUT_ICON[3]], iconSelector);
      text(OUT_ROW2_L[0], OUT_ROW2_L[1], condition, SIZE_SMALL);
    }
    // Draw OUTSIDE label once with possibly adjusted x
    text(olx, 22, outsideLabel, SIZE_LABEL, 'bold');

    // Battery glyph + status text with IP, voltage, percent, ETA days
    const pct = parseInt(data.percent||'76', 10);
    if (mode !== 'split2' && mode !== 'split3') {
    const bx = STATUS[0];
      const by = STATUS[1]; // baseline
      const bw = 13, bh = 7;
    ctx.strokeStyle = '#000';
    ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = '#000';
      ctx.fillRect(bx + bw, by + 2, 2, 4);
    const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100))));
    if (fillw > 0) ctx.fillRect(bx+1, by+1, fillw, bh-2);
      if (pct < 20) { ctx.beginPath(); ctx.moveTo(bx + bw + 4, by + 1); ctx.lineTo(bx + bw + 8, by + 5); ctx.lineTo(bx + bw + 0, by + 5); ctx.closePath(); ctx.fill(); }
    const days = `${data.days||'128'}`;
    const voltageText = `${data.voltage||'4.01'}`;
    const pctText = `${pct||76}%`;
      const leftX = STATUS[0] + bw + 6;
      const statusTextY = STATUS[1] - 1;
    const ip = `IP ${data.ip||'192.168.1.42'}`;
      ctx.font = `${SIZE_STATUS}px ${FONT_STACK}`;
    const iw = ctx.measureText(ip).width;
      const ipX = STATUS[0] + STATUS[2] - 2 - iw;
      const maxLeftWidth = ipX - leftX - 2;
      const leftFull = `Batt ${voltageText}V ${pctText} | ~${days}d`;
      const leftNoBatt = `${voltageText}V ${pctText} | ~${days}d`;
      const leftTail = `${pctText} | ~${days}d`;
      let chosen = leftFull;
      if (ctx.measureText(chosen).width > maxLeftWidth) chosen = leftNoBatt;
      if (ctx.measureText(chosen).width > maxLeftWidth) chosen = ctx.measureText(leftTail).width <= maxLeftWidth ? leftTail : '';
      text(leftX, statusTextY, chosen, SIZE_STATUS);
      text(ipX, statusTextY, ip, SIZE_STATUS);
    }

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


