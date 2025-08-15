(function(){
  const names = [
    'weather-cloudy','weather-sunny','weather-partly-cloudy','weather-fog','weather-pouring','weather-lightning','weather-snowy','weather-windy','weather-windy-variant','weather-night','weather-night-partly-cloudy',
    'moon-new','moon-waxing-crescent','moon-first-quarter','moon-waxing-gibbous','moon-full','moon-waning-gibbous','moon-last-quarter','moon-waning-crescent'
  ];
  const grid = document.getElementById('grid');
  names.forEach(n=>{
    const card = document.createElement('div');
    card.className = 'card';
    const link = document.createElement('a');
    link.href = `${n}.svg`;
    link.target = '_blank';
    const img = document.createElement('img');
    img.src = `${n}.svg`;
    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = n;
    link.appendChild(img);
    card.appendChild(link);
    card.appendChild(name);
    grid.appendChild(card);
  });
})();


