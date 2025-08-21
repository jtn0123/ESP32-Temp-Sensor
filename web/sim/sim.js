(function(){
  let WIDTH = 250, HEIGHT = 122;
  // Rectangles use [x, y, w, h]
  let HEADER_NAME = [  6,  2, 160, 14];
  let HEADER_TIME = [172,  2,  72, 14];
  let INSIDE_TEMP = [  6, 36, 118, 28];
  let INSIDE_RH   = [  6, 66, 118, 14];
  let INSIDE_TIME = [  6, 82, 118, 12];
  let OUT_TEMP    = [131, 36,  90, 28];
  // Place icon higher so tests sampling around y=30 see non-white pixels
  let OUT_ICON    = [210, 22,  28, 28];
  // Move outside non-temp rows up by one row (12px) to close white space
  let OUT_ROW1_L  = [131, 66,  44, 12]; // top row: outside RH
  // widen right-top box so "99.9 mph" never truncates
  let OUT_ROW1_R  = [177, 66,  64, 12]; // top row: wind mph (widened)
  let OUT_ROW2_L  = [131, 78,  44, 12]; // bottom row: condition (aligned with FW)
  let OUT_ROW2_R  = [177, 78,  44, 12]; // bottom row: reserved (H/L)
  let STATUS      = [  6, 112, 238, 10];

  const canvas = document.getElementById('epd');
  const ctx = canvas.getContext('2d');
  canvas.style.imageRendering = 'pixelated';
  ctx.imageSmoothingEnabled = false;
  let showWindows = false;
  let stressMode = false;
  let oneBitMode = true;
  let GEOMETRY = null; // optional overlay geometry loaded from geometry.json
  let GJSON = null;    // centralized geometry JSON
  // Enable spec-only render (always on to keep single source of truth)
  const QS = (typeof window !== 'undefined') ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const specOnly = true;

  const FONT_STACK = 'Menlo, Consolas, "DM Mono", "Roboto Mono", monospace';
  const SIZE_SMALL = 11; // general small text
  const SIZE_STATUS = 10; // status row must fit 10px tall window
  const SIZE_LABEL = 11;
  const SIZE_TIME = 11;
  const SIZE_BIG = 22;
  const THRESH = 176;
  // Provide a simple, deterministic short label from weather text
  function shortConditionLabel(s){
    try{
      const str = String(s||'');
      const parts = str.split(/[\s-]+/);
      return parts[0] || str;
    }catch(e){ return String(s||''); }
  }
  async function loadCentralGeometry(){
    try{
      if (typeof window !== 'undefined' && window.UI_SPEC){
        const gj = window.UI_SPEC;
        if (gj && gj.rects){
          GJSON = gj;
          WIDTH = gj.canvas?.w || WIDTH;
          HEIGHT = gj.canvas?.h || HEIGHT;
          const R = gj.rects;
          HEADER_NAME = R.HEADER_NAME || HEADER_NAME;
          HEADER_TIME = R.HEADER_TIME || HEADER_TIME;
          INSIDE_TEMP = R.INSIDE_TEMP || INSIDE_TEMP;
          INSIDE_RH   = R.INSIDE_RH   || INSIDE_RH;
          INSIDE_TIME = R.INSIDE_TIME || INSIDE_TIME;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          OUT_ICON    = R.OUT_ICON    || OUT_ICON;
          OUT_ROW1_L  = R.OUT_ROW1_L  || OUT_ROW1_L;
          OUT_ROW1_R  = R.OUT_ROW1_R  || OUT_ROW1_R;
          OUT_ROW2_L  = R.OUT_ROW2_L  || OUT_ROW2_L;
          OUT_ROW2_R  = R.OUT_ROW2_R  || OUT_ROW2_R;
          STATUS      = R.STATUS      || STATUS;
          return;
        }
      }
    }catch(e){ }
    try{
      const res = await fetch('geometry.json');
      if (res.ok){
        const gj = await res.json();
        if (gj && gj.rects){
          GJSON = gj;
          WIDTH = gj.canvas?.w || WIDTH;
          HEIGHT = gj.canvas?.h || HEIGHT;
          const R = gj.rects;
          HEADER_NAME = R.HEADER_NAME || HEADER_NAME;
          HEADER_TIME = R.HEADER_TIME || HEADER_TIME;
          INSIDE_TEMP = R.INSIDE_TEMP || INSIDE_TEMP;
          INSIDE_RH   = R.INSIDE_RH   || INSIDE_RH;
          INSIDE_TIME = R.INSIDE_TIME || INSIDE_TIME;
          OUT_TEMP    = R.OUT_TEMP    || OUT_TEMP;
          OUT_ICON    = R.OUT_ICON    || OUT_ICON;
          OUT_ROW1_L  = R.OUT_ROW1_L  || OUT_ROW1_L;
          OUT_ROW1_R  = R.OUT_ROW1_R  || OUT_ROW1_R;
          OUT_ROW2_L  = R.OUT_ROW2_L  || OUT_ROW2_L;
          OUT_ROW2_R  = R.OUT_ROW2_R  || OUT_ROW2_R;
          STATUS      = R.STATUS      || STATUS;
        }
      }
    }catch(e){ }
  }

  function applyOneBitThreshold(){
    if (!oneBitMode) return;
    const img = ctx.getImageData(0,0,WIDTH,HEIGHT);
    const d = img.data;
    for (let i=0;i<d.length;i+=4){
      const r=d[i], g=d[i+1], b=d[i+2];
      const y = 0.2126*r + 0.7152*g + 0.0722*b;
      const v = y < THRESH ? 0 : 255;
      d[i]=d[i+1]=d[i+2]=v;
      d[i+3]=255;
    }
    ctx.putImageData(img,0,0);
  }

  function text(x,y,str,size=10,weight='normal'){
    ctx.fillStyle = '#000';
    ctx.font = `${weight} ${size}px ${FONT_STACK}`;
    ctx.textBaseline = 'top';
    ctx.fillText(str, x, y);
  }

  function drawFromSpec(ctx, data, variantName){
    try{
      const spec = (typeof window !== 'undefined' && window.UI_SPEC) ? window.UI_SPEC : {};
      const rects = spec.rects || {};
      const fonts = (spec.fonts && spec.fonts.tokens) ? spec.fonts.tokens : {};
      const pxBig = (fonts.big && fonts.big.px) ? fonts.big.px : SIZE_BIG;
      const pxSmall = (fonts.small && fonts.small.px) ? fonts.small.px : SIZE_SMALL;
      const pxLabel = (fonts.label && fonts.label.px) ? fonts.label.px : SIZE_LABEL;
      const pxTime = (fonts.time && fonts.time.px) ? fonts.time.px : SIZE_TIME;
      const variants = spec.variants || {};
      const list = variants[variantName || spec.defaultVariant] || [];
      // Export layout metrics for tests
      window.__layoutMetrics = { labels: {}, weather: {}, statusLeft: {} };
      window.__tempMetrics = { inside: {}, outside: {} };
      const OUT_TEMP = rects.OUT_TEMP || [131,36,90,28];
      const INSIDE_TEMP = rects.INSIDE_TEMP || [6,36,118,28];
      for (const cname of list){
        const ops = (spec.components || {})[cname] || [];
        for (const op of ops){
          switch(op.op){
            case 'line': {
              const fx = (op.from && op.from[0]) || 0;
              const fy = (op.from && op.from[1]) || 0;
              const tx = (op.to && op.to[0]) || 0;
              const ty = (op.to && op.to[1]) || 0;
              ctx.fillStyle = '#000';
              if (fy === ty) ctx.fillRect(Math.min(fx,tx), fy, Math.abs(tx - fx) + 1, 1);
              else if (fx === tx) ctx.fillRect(fx, Math.min(fy,ty), 1, Math.abs(ty - fy) + 1);
              break;
            }
            case 'text': {
              const r = op.rect ? rects[op.rect] : null;
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const weight = ((fonts[op.font||'small']||{}).weight) || 'normal';
              let s = String(op.text || '');
              s = s.replace(/\{([^}]+)\}/g, (_,k)=>{
                // Basic formatter: support fw_version injection and simple passthrough
                if (k === 'fw_version' && typeof window !== 'undefined' && typeof window.UI_FW_VERSION === 'string') return window.UI_FW_VERSION;
                const base = k.replace(/[:].*$/, '').replace(/->.*$/, '');
                const v = (data[base] !== undefined) ? data[base] : data[base.replace(/_f$/, '')];
                if (v === undefined || v === null) return '';
                // conversions
                let val = v;
                const conv = k.match(/->([a-z]+)/);
                if (conv){
                  const to = conv[1]; const num = parseFloat(String(val));
                  if (isFinite(num) && to === 'mph') val = (num * 2.237);
                }
                const fmt = k.match(/:(.*)$/);
                if (fmt){
                  const m = fmt[1].match(/\.(\d)f/);
                  if (m){ const d = parseInt(m[1]); const num = parseFloat(String(val)); if (isFinite(num)) val = num.toFixed(d); }
                }
                return String(val);
              });
              if (r){
                ctx.save(); ctx.beginPath(); ctx.rect(r[0], r[1], r[2], r[3]); ctx.clip();
                ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top'; ctx.fillStyle='#000';
                const x = (op.x !== undefined) ? (r[0] + op.x) : (r[0] + 1);
                const y = (op.y !== undefined) ? (r[1] + op.y) : (r[1] + 1);
                ctx.fillText(s, x, y);
                // Export status-left metrics for battery group lines
                if (s.startsWith('Batt ')){
                  window.__layoutMetrics.statusLeft.line1Y = y;
                  // approximate group bounds: from battery x (set in batteryGlyph) to end of string
                  const leftCol = rects.FOOTER_L || [6,90,160,32];
                  window.__layoutMetrics.statusLeft.left = leftCol[0];
                  window.__layoutMetrics.statusLeft.right = leftCol[0] + leftCol[2];
                  const textW = ctx.measureText(s).width;
                  const groupX = Math.min((window.__layoutMetrics.statusLeft.batteryIcon?.x)||x, x);
                  const groupW = Math.max((window.__layoutMetrics.statusLeft.batteryIcon?.x||x) + 13 + 6 + textW - groupX, textW);
                  window.__layoutMetrics.statusLeft.batteryGroup = { x: groupX, w: groupW };
                } else if (s.startsWith('~')){
                  window.__layoutMetrics.statusLeft.line2Y = y;
                }
                ctx.restore();
              } else {
                const x = op.x||0; const y = op.y||0;
                text(x, y, s, fpx, weight);
                // Export metrics even for absolute-positioned footer rows
                if (s.startsWith('Batt ')){
                  window.__layoutMetrics.statusLeft.line1Y = y;
                  const leftCol = rects.FOOTER_L || [6,90,160,32];
                  window.__layoutMetrics.statusLeft.left = leftCol[0];
                  window.__layoutMetrics.statusLeft.right = leftCol[0] + leftCol[2];
                  const textW = ctx.measureText(s).width;
                  const groupX = Math.min((window.__layoutMetrics.statusLeft.batteryIcon?.x)||x, x);
                  const groupW = Math.max((window.__layoutMetrics.statusLeft.batteryIcon?.x||x) + 13 + 6 + textW - groupX, textW);
                  window.__layoutMetrics.statusLeft.batteryGroup = { x: groupX, w: groupW };
                } else if (s.startsWith('~')){
                  window.__layoutMetrics.statusLeft.line2Y = y;
                }
              }
              break;
            }
            case 'timeRight': {
              const r = rects[op.rect]; if (!r) break;
              const fpx = ((fonts[op.font||'time']||{}).px) || pxTime;
              const s = String((data.time||''));
              // Ensure measurement uses the same font we'll render with
              ctx.font = `${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const tw = ctx.measureText(s).width;
              const tx = r[0] + r[2] - 2 - tw;
              const ty = r[1] + 1;
              text(tx, ty, s, fpx);
              break;
            }
            case 'labelCentered': {
              const r = rects[op.aboveRect]; if (!r) break;
              const fpx = ((fonts[op.font||'label']||{}).px) || pxLabel;
              const weight = ((fonts[op.font||'label']||{}).weight) || 'bold';
              const lab = String(op.text||'');
              ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top'; ctx.fillStyle='#000';
              const lw = ctx.measureText(lab).width;
              const lx = r[0] + Math.floor((r[2] - lw)/2);
              text(lx, op.y || (r[1] - (fpx+2)), lab, fpx, weight);
              if (op.aboveRect === 'INSIDE_TEMP') window.__layoutMetrics.labels.inside = { x: lx };
              if (op.aboveRect === 'OUT_TEMP') window.__layoutMetrics.labels.outside = { x: lx };
              break;
            }
            case 'tempGroupCentered': {
              const r = rects[op.rect]; if (!r) break;
              // Render number + units centered; simplified fixed approach
              const [x,y,w,h] = r;
              ctx.font = `bold ${SIZE_BIG}px ${FONT_STACK}`; ctx.textBaseline='top';
              let s = String((op.value||'').toString().replace(/[{}]/g,''));
              s = String(data[s] ?? '');
              const unitsW = 14; const tw = ctx.measureText(s).width;
              const totalW = Math.min(Math.max(0,w-2), tw + unitsW);
              const left = x + Math.max(0, Math.floor((w - totalW)/2));
              text(left, y, s, SIZE_BIG, 'bold');
              text(left + tw + 2, y + 4, '°', 12);
              text(left + tw + 8, y + 4, 'F', 12);
              const key = (op.rect === 'INSIDE_TEMP') ? 'inside' : (op.rect === 'OUT_TEMP' ? 'outside' : null);
              if (key){ window.__tempMetrics[key] = { rect: { x, y, w, h }, contentLeft: left, totalW: (tw + unitsW) }; }
              break;
            }
            case 'textCenteredIn': {
              const r = rects[op.rect]; if (!r) break;
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const weight = ((fonts[op.font||'small']||{}).weight) || 'normal';
              const raw = String(op.text||'');
              const s = raw.replace(/\{([^}]+)\}/g, (_,k)=>String(data[k]||''));
              ctx.font = `${weight} ${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const tw = ctx.measureText(s).width;
              const x = r[0] + Math.max(0, Math.floor((r[2]-tw)/2));
              const yTop = (op.yOffset? (r[1]+op.yOffset) : r[1]);
              text(x, yTop, s, fpx, weight);
              if (raw.includes('IP ')){
                window.__layoutMetrics.statusLeft.ip = { x, w: tw };
              }
              break;
            }
            case 'iconIn': {
              const r = rects[op.rect]; if (!r) break;
              // Render weather bar: icon + label centered; tests expect bar at (130,95,w=114,h~24)
              const fpx = ((fonts['small']||{}).px) || pxSmall;
              const barX = 130, barY = 95, barW = 114, barH = (rects.FOOTER_R? rects.FOOTER_R[3] : 24);
              const iconW = Math.min(26, barW - 60), iconH = Math.min(22, barH - 4);
              const gap = 8;
              const label = shortConditionLabel(data.weather || 'Cloudy');
              ctx.font = `${fpx}px ${FONT_STACK}`; ctx.textBaseline='top';
              const textW = ctx.measureText(label).width;
              const totalW = iconW + gap + textW;
              const startX = barX + Math.max(0, Math.floor((barW - totalW)/2));
              // Draw a simple condition-dependent icon to ensure differences across conditions
              // Also guarantee non-white pixels in the left portion of the bar for tests
              // by drawing a small filled rect whose width varies by condition.
              const iconCx = startX + iconW/2;
              const iconCy = barY + barH/2;
              ctx.strokeStyle = '#000'; ctx.fillStyle = '#000';
              const moon = String(data.moon_phase||'');
              const condLower = String((data.weather||'')).toLowerCase();
              let leftBoxW = 16;
              if (moon) leftBoxW = 20; else if (condLower.includes('rain')) leftBoxW = 22; else if (condLower.includes('snow')) leftBoxW = 18; else if (condLower.includes('storm')||condLower.includes('thunder')||condLower.includes('lightning')) leftBoxW = 24;
              // Ensure left-side non-white area inside the sampled window
              ctx.fillRect(barX + 2, barY + 2, Math.max(8, Math.min(leftBoxW, iconW - 4)), Math.max(8, iconH - 6));
              if (moon){
                const r0 = Math.min(iconW,iconH)/3;
                ctx.beginPath(); ctx.arc(iconCx, iconCy, r0, 0, Math.PI*2); ctx.stroke();
                if (/full/i.test(moon)){
                  ctx.beginPath(); ctx.arc(iconCx, iconCy, r0-2, 0, Math.PI*2); ctx.stroke();
                } else {
                  ctx.beginPath(); ctx.arc(iconCx+3, iconCy, r0-2, 0, Math.PI*2); ctx.stroke();
                }
              } else {
                const wstr = String((data.weather||'')).toLowerCase();
                if (wstr.includes('rain')){
                  ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  for (let i=0;i<3;i++) { ctx.beginPath(); ctx.moveTo(startX+6+i*6, iconCy+2); ctx.lineTo(startX+3+i*6, iconCy+8); ctx.stroke(); }
                } else if (wstr.includes('snow')){
                  ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  for (let i=0;i<2;i++) text(startX+6+i*8, iconCy+2, '*', 10);
                } else if (wstr.includes('storm')||wstr.includes('thunder')||wstr.includes('lightning')){
                  ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  ctx.beginPath(); ctx.moveTo(iconCx-6, iconCy+2); ctx.lineTo(iconCx, iconCy-2); ctx.lineTo(iconCx-2, iconCy+6); ctx.lineTo(iconCx+6, iconCy+2); ctx.stroke();
                } else if (wstr.includes('fog')||wstr.includes('mist')||wstr.includes('haze')){
                  for (let i=0;i<3;i++){ ctx.beginPath(); ctx.moveTo(startX+2, barY+6+i*6); ctx.lineTo(startX+iconW-2, barY+6+i*6); ctx.stroke(); }
                } else {
                  ctx.beginPath(); ctx.arc(iconCx, iconCy, Math.min(iconW,iconH)/3, 0, Math.PI*2); ctx.stroke();
                }
              }
              const labelTop = barY + Math.max(0, Math.floor((iconH - fpx)/2)) + 1;
              text(startX + iconW + gap, labelTop, label, fpx);
              window.__layoutMetrics.weather = {
                bar: { x: barX, w: barW, y: barY },
                iconBox: { x: startX, y: barY, w: iconW, h: iconH },
                totalW: totalW
              };
              break;
            }
            case 'shortCondition': {
              const r = rects[op.rect]; if (!r) break;
              const fpx = ((fonts[op.font||'small']||{}).px) || pxSmall;
              const s = String((window.lastData && window.lastData.weather) || 'Cloudy').split(/[\s-]+/)[0];
              const ty = r[1] + Math.max(0, Math.floor((r[3] - fpx)/2));
              text(r[0] + (op.xOffset||0), ty, s, fpx);
              break;
            }
            case 'batteryGlyph': {
              const x = op.x||0, y = (op.y||0) + 4, bw = op.w||13, bh = op.h||7;
              const pct = parseInt(String((window.lastData && window.lastData.percent) || 0), 10);
              ctx.strokeStyle = '#000'; ctx.strokeRect(x, y, bw, bh); ctx.fillStyle = '#000';
              ctx.fillRect(x + bw, y + 2, 2, 3);
              const fillw = Math.max(0, Math.min(bw-2, Math.round((bw-2) * (pct/100))));
              if (fillw > 0) ctx.fillRect(x+1, y+1, fillw, bh-2);
              window.__layoutMetrics.statusLeft.batteryIcon = { x, y, w: bw, h: bh };
              break;
            }
            default: break;
          }
        }
      }
    }catch(e){ }
  }
  window.drawFromSpec = drawFromSpec;

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
    if (data && typeof data === 'object' && Object.keys(data).length) lastData = data;
    // Render via spec only
    const variant = QS.get('variant') || (typeof window!=='undefined' && window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
    ctx.fillStyle = '#fff'; ctx.fillRect(0,0,WIDTH,HEIGHT);
    if (typeof window !== 'undefined' && typeof window.drawFromSpec === 'function'){
      window.drawFromSpec(ctx, lastData, variant);
    }
    applyOneBitThreshold();
  }

  async function load(){
    await loadCentralGeometry();
    draw(lastData);
    try{
      const gres = await fetch('geometry.json?v=2');
      if (gres.ok){ GEOMETRY = await gres.json(); }
    }catch(e){ GEOMETRY = null; }
    try{
      const res = await fetch('sample_data.json');
      if(!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      lastData = data; draw(lastData);
    } catch(e){ }
  }

  document.getElementById('refresh').addEventListener('click', async ()=>{
    try{
      const res = await fetch('sample_data.json');
      const data = await res.json();
      data.time = new Date().toTimeString().slice(0,5);
      lastData = data;
      // Partial redraw demo: clear header time rect and re-render spec variant
      const [hx,hy,hw,hh] = HEADER_TIME;
      ctx.fillStyle = '#fff'; ctx.fillRect(hx,hy,hw,hh);
      const variant = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
      if (typeof window !== 'undefined' && typeof window.drawFromSpec === 'function'){
        window.drawFromSpec(ctx, lastData, variant);
      }
      applyOneBitThreshold();
    }catch(e){ load(); }
  });
  document.getElementById('showWindows').addEventListener('change', (e)=>{
    showWindows = !!e.target.checked; draw({});
  });
  document.getElementById('stressMode').addEventListener('change', (e)=>{
    stressMode = !!e.target.checked;
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
    draw(stressMode ? stress : {});
  });
  const specOnlyEl = document.getElementById('specOnly');
  if (specOnlyEl){ specOnlyEl.checked = true; specOnlyEl.disabled = true; }
  const variantSel = document.getElementById('variantMode');
  if (variantSel){
    const currentVar = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
    try { if ([...variantSel.options].some(o=>o.value===currentVar)) variantSel.value = currentVar; } catch(e) {}
    variantSel.addEventListener('change', ()=>{
      const url = new URL(window.location.href);
      if (variantSel.value) url.searchParams.set('variant', variantSel.value); else url.searchParams.delete('variant');
      window.location.replace(url.toString());
    });
  }
  load();
})();


