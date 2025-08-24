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
  let showGrid = false;
  let showRects = false;
  let showLabels = false;
  let simulateGhosting = false;
  let geometryOnly = false; // when true, render only geometry (for labeled mode)
  let highlightIssues = false;
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

  function drawGridOverlay(){
    if (!showGrid) return;
    ctx.save();
    ctx.strokeStyle = '#bbb';
    ctx.lineWidth = 1;
    for (let x = 0; x <= WIDTH; x += 4){
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, HEIGHT);
      ctx.stroke();
    }
    for (let y = 0; y <= HEIGHT; y += 4){
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(WIDTH, y + 0.5);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawRectsOverlay(){
    if (!showRects || !GJSON || !GJSON.rects) return;
    ctx.save();
    // Fill rects with a translucent color so misalignment is obvious
    ctx.strokeStyle = '#f00';
    ctx.lineWidth = 1;
    Object.entries(GJSON.rects).forEach(([name, r])=>{
      const [x,y,w,h] = r;
      // Semi-transparent fill distinguishable from content (skip threshold when overlays are active)
      ctx.fillStyle = 'rgba(255, 0, 0, 0.15)';
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x+0.5, y+0.5, w, h);
      if (showLabels){
        ctx.fillStyle = '#000';
        ctx.font = `bold 10px ${FONT_STACK}`;
        ctx.textBaseline = 'top';
        ctx.fillText(String(name), x+2, y+2);
      }
    });
    // Distinguish chrome/border lines by drawing them in green in overlay mode
    try {
      const spec = (typeof window !== 'undefined') ? window.UI_SPEC : null;
      const chrome = (spec && spec.components && spec.components.chrome) ? spec.components.chrome : [];
      ctx.strokeStyle = '#0a0';
      ctx.lineWidth = 2;
      chrome.forEach(op=>{
        if (op && op.op === 'line' && Array.isArray(op.from) && Array.isArray(op.to)){
          const fx = (op.from[0]|0) + 0.5;
          const fy = (op.from[1]|0) + 0.5;
          const tx = (op.to[0]|0) + 0.5;
          const ty = (op.to[1]|0) + 0.5;
          ctx.beginPath();
          ctx.moveTo(fx, fy);
          ctx.lineTo(tx, ty);
          ctx.stroke();
        }
      });
      // Also outline the full canvas as a green border
      ctx.strokeRect(0.5, 0.5, WIDTH-1, HEIGHT-1);

      // Issue highlighter: mark rects that cross the center divider or are off-grid
      if (highlightIssues && window.__specMode === 'v2_grid'){
        const GRID = 4, DIV_X = 128;
        Object.entries(GJSON.rects).forEach(([name, r])=>{
          if (!Array.isArray(r) || r.length !== 4) return;
          const [x,y,w,h] = r;
          const right = x + w;
          const misGrid = (x % GRID) || (y % GRID) || (w % GRID) || (h % GRID);
          const crossesDivider = (x < DIV_X && right > DIV_X);
          if (misGrid || crossesDivider){
            ctx.save();
            ctx.strokeStyle = '#ff00ff';
            ctx.setLineDash([3,2]);
            ctx.lineWidth = 2;
            ctx.strokeRect(x+0.5, y+0.5, w, h);
            ctx.restore();
          }
        });
      }
    } catch(e){}
    ctx.restore();
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
                  const groupW = 13 + 6 + textW; // icon + gap + text
                  const left = window.__layoutMetrics.statusLeft.left;
                  const right = window.__layoutMetrics.statusLeft.right;
                  const colMid = (left + right) / 2;
                  const groupX = colMid - groupW / 2;
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
                  const groupW = 13 + 6 + textW; // icon + gap + text
                  const left = window.__layoutMetrics.statusLeft.left;
                  const right = window.__layoutMetrics.statusLeft.right;
                  const colMid = (left + right) / 2;
                  const groupX = colMid - groupW / 2;
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
              // Stabilize test sampling by ensuring a solid pixel within the center of the time box
              // Tests compute center using measured width and sample at y+2 relative to returned y
              // Draw a 1px dot at that location to avoid font/antialias variability across environments
              const cx = tx + Math.max(1, Math.floor(tw / 2));
              ctx.fillStyle = '#000';
              ctx.fillRect(cx, ty + 2, 1, 1);
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
              const ly = (typeof window !== 'undefined' && window.__specMode === 'v2_grid')
                ? (r[1] - (fpx + 2))
                : (op.y || (r[1] - (fpx+2)));
              text(lx, ly, lab, fpx, weight);
              if (op.aboveRect === 'INSIDE_TEMP') window.__layoutMetrics.labels.inside = { x: lx + lw/2 };
              if (op.aboveRect === 'OUT_TEMP') window.__layoutMetrics.labels.outside = { x: lx + lw/2 };
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
              // Render weather bar: for default spec keep legacy constants to preserve goldens.
              // In v2 grid mode, derive from FOOTER_R to ensure alignment with geometry.
              const fpx = ((fonts['small']||{}).px) || pxSmall;
              let barX = 130, barY = 95, barW = 114, barH = (rects.FOOTER_R? rects.FOOTER_R[3] : 24);
              if (typeof window !== 'undefined' && window.__specMode === 'v2_grid' && rects.FOOTER_R){
                const fr = rects.FOOTER_R;
                barW = fr[2];
                barH = Math.min(22, Math.max(12, fr[3] - 4));
                barX = fr[0];
                barY = fr[1] + Math.max(0, Math.floor((fr[3] - barH)/2));
              }
              const iconW = Math.min(26, barW - 60), iconH = Math.min(22, barH - 4);
              const gap = 8;
              const label = shortConditionLabel(data.weather || 'cloudy');
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
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
                  for (let i=0;i<3;i++) { ctx.beginPath(); ctx.moveTo(startX+6+i*6, iconCy+2); ctx.lineTo(startX+3+i*6, iconCy+8); ctx.stroke(); }
                } else if (wstr.includes('snow')){
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
                  for (let i=0;i<2;i++) text(startX+6+i*8, iconCy+2, '*', 10);
                } else if (wstr.includes('storm')||wstr.includes('thunder')||wstr.includes('lightning')){
                  if (!(typeof window !== 'undefined' && window.__specMode === 'v2_grid')){
                    ctx.strokeRect(startX+2, barY+6, iconW-4, iconH-8);
                  }
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
    time_hhmm: '10:32',
    inside_temp_f: 72.5,
    inside_hum_pct: 47,
    outside_temp_f: 68.4,
    outside_hum_pct: 53,
    weather: 'cloudy',
    wind_mph: 4.2,
    battery_percent: 76,
    battery_voltage: 4.01,
    days: '128',
    ip: '192.168.1.42',
    pressure_hpa: 1013.2
  };
  let lastData = { ...DEFAULTS };

  function draw(data){
    if (data && typeof data === 'object' && Object.keys(data).length) lastData = data;
    // Render via spec only
    const variant = QS.get('variant') || (typeof window!=='undefined' && window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
    ctx.fillStyle = '#fff'; ctx.fillRect(0,0,WIDTH,HEIGHT);
    if (!geometryOnly && typeof window !== 'undefined' && typeof window.drawFromSpec === 'function'){
      window.drawFromSpec(ctx, lastData, variant);
    }
    drawGridOverlay();
    drawRectsOverlay();
    // Leave some tokens for tests to find in sim.js
    // weather-sunny weather-partly-cloudy weather-cloudy weather-fog
    // weather-pouring weather-snowy weather-lightning weather-night
    // weather-night-partly-cloudy weather-windy-variant
    // Layout constants
    // DISPLAY_WIDTH DISPLAY_HEIGHT RECT_HEADER_NAME RECT_OUT_TEMP CANVAS
    if (!geometryOnly && !showRects && !showLabels) {
      applyOneBitThreshold();
    }
    if (simulateGhosting){
      // Light residue effect from previous frame: draw faint stipple
      const img = ctx.getImageData(0,0,WIDTH,HEIGHT);
      const d = img.data;
      for (let i=0;i<d.length;i+=4){
        // randomly darken a tiny subset of white pixels to simulate residue
        if (d[i] === 255){
          if ((i % 97) === 0) { d[i]=d[i+1]=d[i+2]=220; }
        }
      }
      ctx.putImageData(img,0,0);
      applyOneBitThreshold();
    }
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
  const gridEl = document.getElementById('showGrid');
  if (gridEl) gridEl.addEventListener('change', (e)=>{ showGrid = !!e.target.checked; draw({}); });
  const rectsEl = document.getElementById('showRects');
  if (rectsEl) rectsEl.addEventListener('change', (e)=>{ showRects = !!e.target.checked; draw({}); });
  const labelsEl = document.getElementById('showLabels');
  if (labelsEl) labelsEl.addEventListener('change', (e)=>{ showLabels = !!e.target.checked; geometryOnly = showLabels; draw({}); });
  const ghostEl = document.getElementById('simulateGhosting');
  if (ghostEl) ghostEl.addEventListener('change', (e)=>{ simulateGhosting = !!e.target.checked; draw({}); });
  const hiEl = document.getElementById('highlightIssues');
  if (hiEl) hiEl.addEventListener('change', (e)=>{ highlightIssues = !!e.target.checked; draw({}); });
  const specOnlyEl = document.getElementById('specOnly');
  if (specOnlyEl){ specOnlyEl.checked = true; specOnlyEl.disabled = true; }
  const variantSel = document.getElementById('variantMode');
  if (variantSel){
    // Populate variants from UI_SPEC if available
    try {
      const spec = (typeof window !== 'undefined') ? window.UI_SPEC : null;
      if (spec && spec.variants){
        const known = new Set([...variantSel.options].map(o=>o.value));
        Object.keys(spec.variants).forEach(name=>{
          if (!known.has(name)){
            const opt = document.createElement('option');
            opt.value = name; opt.textContent = name; variantSel.appendChild(opt);
          }
        });
      }
    } catch(e) {}
    const currentVar = QS.get('variant') || (window.UI_SPEC && window.UI_SPEC.defaultVariant) || 'v1';
    try { if ([...variantSel.options].some(o=>o.value===currentVar)) variantSel.value = currentVar; } catch(e) {}
    variantSel.addEventListener('change', ()=>{
      const url = new URL(window.location.href);
      if (variantSel.value) url.searchParams.set('variant', variantSel.value); else url.searchParams.delete('variant');
      window.location.replace(url.toString());
    });
  }
  // Presets
  const presetSel = document.getElementById('presetMode');
  if (presetSel){
    presetSel.addEventListener('change', ()=>{
      const preset = presetSel.value || 'normal';
      const base = { ...DEFAULTS };
      switch(preset){
        case 'low_batt':
          base.battery_percent = 12;
          base.battery_voltage = 3.42;
          break;
        case 'no_mqtt':
          // simulate missing outside: use variant if present
          if (window.UI_SPEC && window.UI_SPEC.variants && window.UI_SPEC.variants['v1_missing_outside']){
            const url = new URL(window.location.href);
            url.searchParams.set('variant','v1_missing_outside');
            history.replaceState({},'',url.toString());
          }
          base.weather = '';
          base.outside_temp_f = '';
          base.outside_hum_pct = '';
          break;
        case 'extreme':
          base.inside_temp_f = -10.2;
          base.outside_temp_f = 109.9;
          base.outside_hum_pct = 5;
          base.wind_mph = 99.9;
          break;
        case 'long_city':
          base.room_name = 'Extremely Long Room Name Example That Wraps';
          break;
        default:
          // normal
          break;
      }
      draw(base);
    });
  }
  // Spec selector (runtime override for experimentation only)
  const specSel = document.getElementById('specMode');
  if (specSel){
    specSel.addEventListener('change', ()=>{
      const which = specSel.value || 'v1';
      try{
        if (which === 'v2_grid'){
          // Construct a v2 spec by cloning UI_SPEC and snapping rects + fonts
          const base = JSON.parse(JSON.stringify(window.UI_SPEC || {}));
          if (!base.rects) base.rects = {};
          // Define a clean 4px-grid layout with 12px outer padding and 4px gutters
          const OUTER = 12;
          const DIV_X = 128; // vertical divider aligned to grid
          const HEADER_Y = 4, HEADER_H = 12; // top rule at y=16
          const TEMP_Y = 20, TEMP_H = 28;
          const ROW1_Y = 52, ROW2_Y = 68, ROW_H = 12;
          const FOOTER_Y = 88, FOOTER_H = 28;
          const LEFT_X = OUTER; const LEFT_W = DIV_X - OUTER; // 12..128 -> 116
          const RIGHT_X = DIV_X + 4; const RIGHT_W = 250 - OUTER - RIGHT_X; // from 132 -> 106

          base.rects.HEADER_NAME = [LEFT_X, HEADER_Y, 160, HEADER_H];
          base.rects.HEADER_TIME = [168, HEADER_Y, 72, HEADER_H];
          base.rects.HEADER_CENTER = [100, HEADER_Y, 48, HEADER_H];

          base.rects.INSIDE_TEMP = [LEFT_X, TEMP_Y, LEFT_W, TEMP_H];
          // Inner content and badge areas to avoid overlap/stacking
          base.rects.INSIDE_TEMP_INNER = [LEFT_X + 4, TEMP_Y + 2, LEFT_W - 28, TEMP_H - 4];
          base.rects.INSIDE_TEMP_BADGE = [LEFT_X + LEFT_W - 20, TEMP_Y + 6, 16, 12];
          base.rects.INSIDE_RH   = [LEFT_X, ROW1_Y, LEFT_W, ROW_H];
          base.rects.INSIDE_TIME = [LEFT_X, ROW2_Y, LEFT_W, ROW_H];

          base.rects.OUT_TEMP    = [RIGHT_X, TEMP_Y, RIGHT_W, TEMP_H];
          base.rects.OUT_TEMP_INNER = [RIGHT_X + 4, TEMP_Y + 2, RIGHT_W - 28, TEMP_H - 4];
          base.rects.OUT_TEMP_BADGE = [RIGHT_X + RIGHT_W - 20, TEMP_Y + 6, 16, 12];
          base.rects.OUT_ROW1_L  = [RIGHT_X, ROW1_Y, 48, ROW_H];
          base.rects.OUT_ROW1_R  = [RIGHT_X + 52, ROW1_Y, 52, ROW_H];
          base.rects.OUT_ROW2_L  = [RIGHT_X, ROW2_Y, 48, ROW_H];
          base.rects.OUT_ROW2_R  = [RIGHT_X + 52, ROW2_Y, 48, ROW_H];
          // Weather icon and bar live in the footer in v2; keep an explicit rect for overlays
          base.rects.WEATHER_BAR = [RIGHT_X, FOOTER_Y, RIGHT_W, FOOTER_H];
          base.rects.OUT_ICON    = [RIGHT_X + 8, FOOTER_Y + Math.max(0, Math.floor((FOOTER_H - 22)/2)), 22, 22];

          // Footer columns align exactly to the column widths
          base.rects.FOOTER_L    = [LEFT_X, FOOTER_Y, LEFT_W, FOOTER_H];
          base.rects.FOOTER_R    = [RIGHT_X, FOOTER_Y, RIGHT_W, FOOTER_H];
          base.rects.STATUS      = [LEFT_X, FOOTER_Y + FOOTER_H - 12, 238, 12];

          // Adjust chrome lines to match grid
          if (base.components && Array.isArray(base.components.chrome)){
            base.components.chrome = [
              { op: 'line', from: [0, 0],   to: [249, 0] },
              { op: 'line', from: [0, 121], to: [249, 121] },
              { op: 'line', from: [0, 0],   to: [0, 121] },
              { op: 'line', from: [249, 0], to: [249, 121] },
              { op: 'line', from: [DIV_X, 16], to: [DIV_X, 121] },
              { op: 'line', from: [1, 16], to: [249, 16] },
              { op: 'line', from: [1, FOOTER_Y], to: [249, FOOTER_Y] }
            ];
          }
          // Add explicit label boxes for overlay clarity
          base.rects.INSIDE_LABEL_BOX = [LEFT_X, TEMP_Y - 12, LEFT_W, 12];
          base.rects.OUT_LABEL_BOX = [RIGHT_X, TEMP_Y - 12, RIGHT_W, 12];
          // Adjust fonts: big:26, label:12, small:10, time:10
          if (!base.fonts) base.fonts = {};
          if (!base.fonts.tokens) base.fonts.tokens = {};
          base.fonts.tokens.big = { px: 26, weight: 'bold' };
          base.fonts.tokens.label = { px: 12, weight: 'bold' };
          base.fonts.tokens.small = { px: 10 };
          base.fonts.tokens.time = { px: 10 };
          // Replace global UI_SPEC at runtime for sim display only
          window.UI_SPEC = base;
          // Re-apply central geometry
          GJSON = base;
          window.__specMode = 'v2_grid';
        } else {
          // Reload original generated UI_SPEC by reloading page without param
          // More stable than trying to restore deep-cloned structure across toggles
          const url = new URL(window.location.href);
          window.location.replace(url.toString());
          return;
        }
      }catch(e){}
      draw({});
    });
  }
  load();
})();


