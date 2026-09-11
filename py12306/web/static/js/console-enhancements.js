(function () {
  function token(){ return localStorage.getItem('user_token') || ''; }
  function call(path, opts){ opts=opts||{}; opts.headers=Object.assign({'Content-Type':'application/json','Authorization':'Bearer '+token()},opts.headers||{}); return fetch(path,opts); }
  function addUi(){
    if(document.getElementById('console-start')) return;
    var actions=document.querySelector('.actions ul');
    if(actions){
      var li=document.createElement('li'); li.className='float-left margin-left-3-rem';
      li.innerHTML='<a id="console-start" class="color-white vertical-center" href="#"><i class="fa fa-play margin-right-s5-rem"></i><span>开始抢票</span></a>';
      actions.insertBefore(li, actions.firstChild); li.firstChild.onclick=function(e){e.preventDefault(); call('/app/ticketing/start',{method:'POST'}).then(function(){li.firstChild.querySelector('span').textContent='抢票运行中';});};
    }
    var menu=document.querySelector('#menus .el-menu');
    if(menu && !document.getElementById('console-config')){ var item=document.createElement('li'); item.className='el-menu-item'; item.id='console-config'; item.innerHTML='<i class="fa fa-sliders-h"></i><span>配置中心</span>'; menu.appendChild(item); item.onclick=openConfig; }
  }
  function openConfig(){
    if(document.getElementById('config-panel')) return;
    var panel=document.createElement('div'); panel.id='config-panel'; panel.innerHTML='<div class="config-modal"><div class="config-head"><h2>配置中心</h2><button id="config-close">×</button></div><p class="config-note">修改后立即写入运行配置并热加载。</p><div id="config-fields">加载中…</div><button id="config-save">保存配置</button></div>';
    document.body.appendChild(panel); document.getElementById('config-close').onclick=function(){panel.remove();};
    call('/app/config').then(function(r){return r.json();}).then(function(data){var box=document.getElementById('config-fields'); box.innerHTML=Object.keys(data).map(function(k){var v=typeof data[k]==='object'?JSON.stringify(data[k]):data[k]; return '<label>'+k+'<input data-key="'+k+'" value="'+String(v).replace(/"/g,'&quot;')+'"></label>';}).join('');});
    document.getElementById('config-save').onclick=function(){var out={}; panel.querySelectorAll('[data-key]').forEach(function(x){try{out[x.dataset.key]=JSON.parse(x.value);}catch(e){out[x.dataset.key]=x.value;}}); call('/app/config',{method:'PUT',body:JSON.stringify(out)}).then(function(){document.querySelector('.config-note').textContent='已保存，配置已热加载。';});};
  }
  setInterval(addUi,800); addUi();
})();
