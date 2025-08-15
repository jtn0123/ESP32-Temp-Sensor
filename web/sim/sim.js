(function(){
  const WIDTH = 250, HEIGHT = 122;
  const INSIDE_TEMP = [6,38,124,64];
  const INSIDE_RH   = [6,64,124,80];
  const INSIDE_TIME = [6,78,124,92];
  const OUT_TEMP    = [131,38,220,64];
  const OUT_RH      = [131,64,220,80];
  const OUT_ICON    = [218,22,242,46];
  const STATUS      = [6,96,244,118];

  const canvas = document.getElementById('epd');
  const ctx = canvas.getContext('2d');

  function clear(){
    ctx.fillStyle = '#fff';
    ctx.fillRect(0,0,WIDTH,HEIGHT);
    ctx.strokeStyle = '#000';
  }

  function text(x,y,str,size=10,weight='normal'){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px Arial, Helvetica, sans-serif`;
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
      // Prefer MDI icons when available, fallback to our basic icons
      let res = await fetch(`../icons/mdi/${name}.svg`);
      if(!res.ok){
        res = await fetch(`../icons/${name}.svg`);
      }
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
    // Header
    ctx.fillStyle = '#000';
    ctx.fillRect(0,0,WIDTH,18);
    ctx.fillStyle = '#fff';
    text(4,4,data.room_name || 'Room',12,'bold');
    // header underline and column separator
    ctx.fillStyle = '#000';
    ctx.fillRect(0,18,WIDTH,1);
    ctx.fillRect(125,18,1,77);

    // Labels
    ctx.fillStyle = '#000';
    text(6,22,'INSIDE',10,'bold');
    text(131,22,'OUTSIDE',10,'bold');

    // Values
    text(INSIDE_TEMP[0], INSIDE_TEMP[1], `${data.inside_temp||'72.5'}° F`, 14, 'bold');
    text(INSIDE_RH[0], INSIDE_RH[1], `${data.inside_hum||'47'}% RH`, 10);
    text(INSIDE_TIME[0], INSIDE_TIME[1], data.time||'10:32', 10);

    text(OUT_TEMP[0], OUT_TEMP[1], `${data.outside_temp||'68.4'}° F`, 14, 'bold');
    text(OUT_RH[0], OUT_RH[1], `${data.outside_hum||'53'}% RH`, 10);
    const iconSelector = (data.moon_phase ? `moon_${(data.moon_phase||'').toLowerCase().replace(/\s+/g,'_')}` : (data.weather||'Cloudy'));
    weatherIcon(OUT_ICON, iconSelector);

    const status = `IP ${data.ip||'192.168.1.42'}  Batt ${data.voltage||'4.01'}V ${data.percent||'76'}%  ~${data.days||'128'}d`;
    text(STATUS[0], STATUS[1], status, 10);
  }

  async function load(){
    try{
      const res = await fetch('sample_data.json');
      const data = await res.json();
      console.log('[sim] loaded sample_data.json');
      draw(data);
    } catch(e){
      console.warn('[sim] falling back to defaults', e);
      draw({});
    }
  }

  // Partial update demo on refresh: only redraw time region
  document.getElementById('refresh').addEventListener('click', async ()=>{
    try{
      const res = await fetch('sample_data.json');
      const data = await res.json();
      data.time = new Date().toTimeString().slice(0,5);
      // clear the time box and redraw just that region
      const [x0,y0,x1,y1] = INSIDE_TIME;
      ctx.fillStyle = '#fff';
      ctx.fillRect(x0,y0,x1-x0,y1-y0);
      text(INSIDE_TIME[0], INSIDE_TIME[1], data.time, 10);
      // brief outline to show the partial region
      ctx.strokeStyle = '#000';
      ctx.strokeRect(x0,y0,x1-x0,y1-y0);
      setTimeout(()=>{ /* no-op */ }, 100);
    }catch(e){
      load();
    }
  });
  load();
})();


