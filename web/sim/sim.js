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

  function draw(data){
    clear();
    // Header
    ctx.fillStyle = '#000';
    ctx.fillRect(0,0,WIDTH,18);
    ctx.fillStyle = '#fff';
    text(4,4,data.room_name || 'Room',12,'bold');

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
    rect(OUT_ICON[0], OUT_ICON[1], OUT_ICON[2], OUT_ICON[3]);
    text(OUT_ICON[0]+2, OUT_ICON[1]+6, (data.weather||'Cloudy').slice(0,4), 10);

    const status = `IP ${data.ip||'192.168.1.42'}  Batt ${data.voltage||'4.01'}V ${data.percent||'76'}%  ~${data.days||'128'}d`;
    text(STATUS[0], STATUS[1], status, 10);
  }

  async function load(){
    try{
      const res = await fetch('sample_data.json');
      const data = await res.json();
      draw(data);
    } catch(e){
      draw({});
    }
  }

  document.getElementById('refresh').addEventListener('click', load);
  load();
})();


