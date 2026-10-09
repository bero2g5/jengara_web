(()=>{const map=document.querySelector('.enterprise-map');if(!map)return;
const flow=[
{nodes:['request','ribyos'],line:'context',text:'01 / A person gives Ribyos one business goal. Ribyos breaks the request into work for specialist agents.'},
{nodes:['knowledge','systems','ribyos'],line:'context',text:'02 / Ribyos makes approved company context available to the agents, within the user’s access permissions.'},
{nodes:['ribyos','research','planning','finance','risk','communication'],line:'agents',text:'03 / Agents share findings through Ribyos. Research informs Planning; Finance and Risk check the plan; Communication prepares the handoff.'},
{nodes:['ribyos','approval'],line:'review',text:'04 / Ribyos combines the outputs and evidence into one review package. A person decides which actions can proceed.'},
{nodes:['approval','ribyos','systems','communication'],line:'context',text:'05 / After approval, Ribyos coordinates scoped actions in business tools and records the activity. This showcase simulates that entire flow.'}
];let index=0,timer=null,playing=!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const control=document.getElementById('map-play');
function draw(n){index=n;map.querySelectorAll('[data-node]').forEach(el=>el.classList.toggle('active',flow[n].nodes.includes(el.dataset.node)));map.querySelectorAll('[data-line]').forEach(el=>el.classList.toggle('active',el.dataset.line===flow[n].line));document.getElementById('map-status').textContent=flow[n].text;document.querySelectorAll('[data-map-step]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.mapStep)===n)));control.textContent=playing?'Pause animation':'Play animation';map.classList.toggle('paused',!playing)}
function schedule(){clearTimeout(timer);if(playing&&!document.hidden)timer=setTimeout(()=>{draw((index+1)%flow.length);schedule()},3800)}
control.onclick=()=>{playing=!playing;draw(index);schedule()};document.querySelectorAll('[data-map-step]').forEach(b=>b.onclick=()=>{playing=false;clearTimeout(timer);draw(Number(b.dataset.mapStep))});document.addEventListener('visibilitychange',schedule);draw(0);schedule();
})();
