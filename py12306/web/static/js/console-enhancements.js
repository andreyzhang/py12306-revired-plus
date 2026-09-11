(function(){
function token(){return localStorage.getItem('user_token')||''} function api(u,o){o=o||{};o.headers=Object.assign({'Content-Type':'application/json','Authorization':'Bearer '+token()},o.headers||{});return fetch(u,o)}
function ui(){var a=document.querySelector('.actions ul');if(a&&!a.dataset.ticketBound){a.dataset.ticketBound='true';a.addEventListener('click',function(e){var item=e.target.closest('li');if(!item)return;var text=item.textContent.trim();if(text.indexOf('开始抢票')<0&&text.indexOf('抢票运行中')<0&&text.indexOf('停止抢票')<0)return;e.preventDefault();e.stopImmediatePropagation();if(text.indexOf('停止')>=0){if(!window.confirm('确定要停止抢票服务吗？当前查询任务将被停止。'))return;api('/app/ticketing/stop',{method:'POST'}).then(function(){location.reload()})}else{api('/app/ticketing/start',{method:'POST'}).then(function(){location.reload()})}},true)}bindConfigMenu()}
// The menu API owns menu entries and their order. Bind the existing Vue
// item rather than inserting another li while its asynchronous menu loads.
function bindConfigMenu() {
  var menu = document.querySelector('#menus .el-menu');
  if (!menu || menu.dataset.configBound === 'true') return;
  menu.dataset.configBound = 'true';
  function openFromMenu(event) {
    var item = event.target.closest('.el-menu-item');
    if (!item || !menu.contains(item) || item.textContent.trim() !== '配置中心') return;
    if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openConfigPanel();
  }
  menu.addEventListener('click', openFromMenu, true);
  menu.addEventListener('keydown', openFromMenu, true);
}
function openConfigPanel(){if(document.getElementById('config-panel'))return;var p=document.createElement('div');p.id='config-panel';p.innerHTML='<div class="config-modal"><div class="config-head"><h2>配置中心</h2><button id="config-close">×</button></div><p class="config-note">按分类填写，保存前会自动检查日期、车站、账号和任务。</p><div id="config-fields">加载中…</div><button id="config-save">检查并保存</button></div>';document.body.appendChild(p);p.querySelector('#config-close').onclick=function(){p.remove()};Promise.all([api('/app/config/schema').then(function(r){return r.json()}),api('/app/config').then(function(r){return r.json()})]).then(function(z){var s=z[0],v=z[1],groups={};s.forEach(function(i){(groups[i.title]||(groups[i.title]=[])).push(i)});p.querySelector('#config-fields').innerHTML=Object.keys(groups).map(function(g){return '<section><h3>'+g+'</h3>'+groups[g].map(function(i){var val=v[i.key],x=typeof val==='object'?JSON.stringify(val):val;return '<label>'+i.title+'<small>'+i.help+'</small><input data-key="'+i.key+'" value="'+String(x==null?'':x).replace(/"/g,'&quot;')+'"></label>'}).join('')+'</section>'}).join('')}).catch(function(e){p.querySelector('#config-fields').innerHTML='<p>配置加载失败，请刷新页面后重试：'+e.message+'</p>';});p.querySelector('#config-save').onclick=function(){var out={};p.querySelectorAll('[data-key]').forEach(function(x){try{out[x.dataset.key]=JSON.parse(x.value)}catch(e){out[x.dataset.key]=x.value}});api('/app/config/validate',{method:'POST',body:JSON.stringify(out)}).then(function(r){return r.json()}).then(function(d){if(!d.valid){p.querySelector('.config-note').textContent=d.errors.join('；');return}api('/app/config',{method:'PUT',body:JSON.stringify(out)}).then(function(){p.querySelector('.config-note').textContent='已保存，配置已热加载。'})})}}
setInterval(ui,800);ui();})();


