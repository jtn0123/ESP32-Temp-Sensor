(function(){
  const WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h]
  const HEADER_NAME = [  6,  2, 160, 14];
  const HEADER_TIME = [172,  2,  72, 14];
  const INSIDE_TEMP = [  6, 36, 118, 28];
  const INSIDE_RH   = [  6, 66, 118, 14];
  const INSIDE_TIME = [  6, 82, 118, 12];
  const OUT_TEMP    = [131, 36,  90, 28];
  const OUT_ICON    = [224, 22,  20, 20];
  const OUT_ROW1_L  = [131, 86,  44, 12];
  const OUT_ROW1_R  = [177, 86,  44, 12];
  const OUT_ROW2_L  = [131, 98,  44, 12];
  const OUT_ROW2_R  = [177, 98,  44, 12];
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

  async function weatherIcon(box, weather){
    const [x0,y0,x1,y1] = box;
    const w = x1-x0, h=y1-y0; const cx=x0+w/2, cy=y0+h/2;
    const kind = (weather||'').toLowerCase();
    // Try SVG first
    const name = kind.startsWith('moon_') ? kind : mapWeatherToIconName(kind);
    const svg = await loadSvgIcon(name);
    if(svg){
      // draw centered at native size (24x24) scaled to fit
      const iw = Math.min(24, w), ih = Math.min(24, h);
      const px = x0 + (w - iw)/2;
      const py = y0 + (h - ih)/2;
      ctx.drawImage(svg, px, py, iw, ih);
      return;
    }
    ctx.strokeStyle = '#000';
    if(kind.includes('sun') || kind.includes('clear')){
      const r = Math.min(w,h)/3;
      ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
      const spikes = [[0,-r-4],[0,r+4],[-r-4,0],[r+4,0],[-3,-3],[3,3],[-3,3],[3,-3]];
      spikes.forEach(([dx,dy])=>{ ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+dx,cy+dy); ctx.stroke(); });
    } else if(kind.includes('part')){
      ctx.beginPath(); ctx.arc(x0+10,y0+10,8,0,Math.PI*2); ctx.stroke();
      ctx.strokeRect(x0+2,y0+h/2,x1-x0-4,y1-y0-6);
    } else if(kind.includes('cloud')){
      ctx.strokeRect(x0+2,y0+8,x1-x0-4,y1-y0-12);
      ctx.beginPath(); ctx.arc(x0+12,y0+10,8,0,Math.PI*2); ctx.stroke();
      ctx.beginPath(); ctx.arc(x0+24,y0+8,8,0,Math.PI*2); ctx.stroke();
    } else if(kind.includes('rain')){
      weatherIcon(box,'cloudy');
      for(let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(x0+8+i*6,y0+18); ctx.lineTo(x0+4+i*6,y0+26); ctx.stroke(); }
    } else if(kind.includes('snow')){
      weatherIcon(box,'cloudy');
      ctx.fillText('*', x0+10, y0+18);
      ctx.fillText('*', x0+18, y0+18);
    } else if(kind.includes('fog')){
      for(let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(x0+2,y0+8+i*6); ctx.lineTo(x1-2,y0+8+i*6); ctx.stroke(); }
    } else {
      rect(x0,y0,x1,y1);
    }
  }

  function draw(data){
    console.log('[sim] draw()', data);
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
    ctx.fillRect(125,18,1,77);
    // left name, right time
    ctx.fillStyle = '#000';
    text(HEADER_NAME[0], HEADER_NAME[1]+1, data.room_name || 'Room', 12, 'bold');
    const t = data.time || '10:32';
    const tw = ctx.measureText(t).width;
    text(HEADER_TIME[0] + HEADER_TIME[2] - 2 - tw, HEADER_TIME[1]+1, t, SIZE_TIME);

    // Labels
    ctx.fillStyle = '#000';
    text(6,22,'INSIDE',SIZE_LABEL,'bold');
    text(131,22,'OUTSIDE',SIZE_LABEL,'bold');

    // Values: right-align degrees and unit
    const numIn = `${data.inside_temp||'72.5'}`;
    const deg = '°';
    const unit = 'F';
    ctx.font = `bold ${SIZE_BIG}px ${FONT_STACK}`;
    // Left-justify number; place degree and F immediately after the number
    text(INSIDE_TEMP[0], INSIDE_TEMP[1], numIn, 22, 'bold');
    const nwi = ctx.measureText(numIn).width;
    text(INSIDE_TEMP[0] + nwi + 2, INSIDE_TEMP[1]+4, deg, 12);
    text(INSIDE_TEMP[0] + nwi + 8, INSIDE_TEMP[1]+4, unit, 12);
    text(INSIDE_RH[0], INSIDE_RH[1], `${data.inside_hum||'47'}% RH`, SIZE_SMALL);
    text(INSIDE_TIME[0], INSIDE_TIME[1], data.time||'10:32', SIZE_SMALL);

    const numOut = `${data.outside_temp||'68.4'}`;
    text(OUT_TEMP[0], OUT_TEMP[1], numOut, 22, 'bold');
    const nwo = ctx.measureText(numOut).width;
    text(OUT_TEMP[0] + nwo + 2, OUT_TEMP[1]+4, deg, 12);
    text(OUT_TEMP[0] + nwo + 8, OUT_TEMP[1]+4, unit, 12);
    // two-column lower info
    text(OUT_ROW1_L[0], OUT_ROW1_L[1], (data.weather||'Cloudy'), SIZE_SMALL);
    text(OUT_ROW1_R[0], OUT_ROW1_R[1], `${data.outside_hum||'53'}% RH`, SIZE_SMALL);
    const wind = (data.wind || '4.2') + ' m/s';
    text(OUT_ROW2_L[0], OUT_ROW2_L[1], wind, SIZE_SMALL);
    const hilo = `H ${data.high||'75.0'}°  L ${data.low||'60.0'}°`;
    text(OUT_ROW2_R[0], OUT_ROW2_R[1], hilo, SIZE_SMALL);
    const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
    weatherIcon([OUT_ICON[0],OUT_ICON[1],OUT_ICON[0]+OUT_ICON[2],OUT_ICON[1]+OUT_ICON[3]], iconSelector);

    // Battery glyph + status text with IP, voltage, percent, ETA days
    const pct = parseInt(data.percent||'76', 10);
    const bx = STATUS[0];
    const by = STATUS[1]; // raised 2px total to center within 10px status row
    const bw = 14, bh = 8;
    ctx.strokeStyle = '#000';
    ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = '#000';
    ctx.fillRect(bx + bw, by + 2, 2, 4); // terminal
    const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100))));
    if (fillw > 0) ctx.fillRect(bx+1, by+1, fillw, bh-2);
    // Low-battery glyph if <20%
    if (pct < 20) {
      ctx.beginPath();
      ctx.moveTo(bx + bw + 4, by + 1);
      ctx.lineTo(bx + bw + 8, by + 5);
      ctx.lineTo(bx + bw + 0, by + 5);
      ctx.closePath();
      ctx.fill();
    }
    // Left status (Batt and ETA) with separators; right-aligned IP
    let left = `Batt ${data.voltage||'4.01'}V ${pct||76}%  |  ~${data.days||'128'}d`;
    let leftX = STATUS[0] + bw + 8;
    const statusTextY = STATUS[1] - 1; // nudge up 1px to avoid bottom clip
    // Right-aligned IP
    const ip = `IP ${data.ip||'192.168.1.42'}`;
    const iw = ctx.measureText(ip).width;
    const ipX = STATUS[0] + STATUS[2] - 2 - iw;
    // Clamp left text to avoid overlap with IP
    const maxLeftWidth = ipX - leftX - 4;
    if (ctx.measureText(left).width > maxLeftWidth) {
      while (left.length > 0 && ctx.measureText(left + '…').width > maxLeftWidth) {
        left = left.slice(0, -1);
      }
      left = left + '…';
    }
    text(leftX, statusTextY, left, SIZE_STATUS);
    text(ipX, statusTextY, ip, SIZE_STATUS);

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
    draw({});
    try{
      const res = await fetch('sample_data.json');
      if(!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      console.log('[sim] loaded sample_data.json');
      draw(data);
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
      // clear the time box and redraw just that region
      const [x0,y0,w,h] = INSIDE_TIME;
      ctx.fillStyle = '#fff';
      ctx.fillRect(x0,y0,w,h);
      text(x0,y0, data.time, 10);
      // brief outline to show the partial region
      ctx.strokeStyle = '#000';
      ctx.strokeRect(x0,y0,w,h);
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


