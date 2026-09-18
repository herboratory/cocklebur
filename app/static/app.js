(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const esc = (v = '') => String(v).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmtDate = (v, withTime=true) => {
    if (!v) return '—';
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return String(v);
    const opts = {day:'2-digit', month:'short', year:'numeric'};
    if (withTime && String(v).includes('T')) Object.assign(opts,{hour:'2-digit',minute:'2-digit'});
    return d.toLocaleString([], opts);
  };
  const fmtShortDate = v => {
    if(!v) return '—'; const d=new Date(v); if(Number.isNaN(d.getTime())) return String(v);
    return d.toLocaleDateString([],{day:'2-digit',month:'short',year:'numeric'});
  };
  const fmtBytes = (n = 0) => { const u=['B','KB','MB','GB']; let i=0,x=Number(n); while(x>=1024&&i<u.length-1){x/=1024;i++;} return `${x.toFixed(i?1:0)} ${u[i]}`; };
  const nowIso = () => new Date().toISOString();
  const lsGet = (key, fallback='') => { try { return window.localStorage.getItem(key) ?? fallback; } catch { return fallback; } };
  const lsSet = (key, value) => { try { window.localStorage.setItem(key, value); } catch {} };
  const icon = (name, cls='') => {
    const paths={
      edit:'<path d="M4 20h4l11-11-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
      trash:'<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/>',
      calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
      download:'<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/>',
      copy:'<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
      pin:'<path d="m9 3 6 6M7 9l8 8M6 8l8-5 7 7-5 8-10-10ZM4 20l5-5"/>',
      chevron:'<path d="m8 10 4 4 4-4"/>',
      plus:'<path d="M12 5v14M5 12h14"/>',
      settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21h-4v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1A1.7 1.7 0 0 0 4.6 15 1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V3h4v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.1v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
      eye:'<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.5"/>'
    };
    return `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${paths[name]||''}</svg>`;
  };

  function toast(msg, error=false) {
    // Native <dialog> elements live in the browser top layer. A page-level toast,
    // even with a huge z-index, still renders beneath the dialog backdrop.
    // When a modal is open, place a temporary toast inside that dialog instead.
    const activeDialog=document.querySelector('dialog[open]');
    let el=activeDialog?.querySelector('[data-dialog-toast]')||null;
    if(activeDialog && !el){
      el=document.createElement('div');
      el.className='toast';
      el.dataset.dialogToast='true';
      el.setAttribute('aria-live','polite');
      activeDialog.appendChild(el);
    }
    if(!el) el=$('#toast');
    if(!el){ alert(msg); return; }
    el.textContent=msg; el.className='toast show'+(error?' error':'');
    clearTimeout(window.__cbToast); window.__cbToast=setTimeout(()=>el.className='toast',3200);
  }
  async function api(url, opts={}) {
    const cfg={credentials:'same-origin', ...opts};
    if(cfg.body && !(cfg.body instanceof FormData) && typeof cfg.body !== 'string') {
      cfg.headers={...cfg.headers,'Content-Type':'application/json'}; cfg.body=JSON.stringify(cfg.body);
    }
    const r=await fetch(url,cfg);
    if(!r.ok){ let d={}; try{d=await r.json();}catch{} const e=new Error(d.detail||`${r.status} ${r.statusText}`); e.status=r.status; e.data=d; throw e; }
    const ct=r.headers.get('content-type')||''; return ct.includes('application/json') ? r.json() : r;
  }
  function rememberProject(id){ const ids=new Set(JSON.parse(lsGet('pw_projects','[]'))); ids.add(id); lsSet('pw_projects',JSON.stringify([...ids])); }
  function forgetProject(id){ const ids=new Set(JSON.parse(lsGet('pw_projects','[]'))); ids.delete(id); lsSet('pw_projects',JSON.stringify([...ids])); }
  function openDialog(html){ const d=$('#genericDialog'); if(!d) return null; $('#genericDialogContent').innerHTML=html; d.showModal(); return d; }
  function closeDialog(){ const d=$('#genericDialog'); if(d?.open)d.close(); }
  function dialogHeader(kicker,title){ return `<div class="modal-head"><div><p class="eyebrow">${esc(kicker)}</p><h2>${esc(title)}</h2></div><button class="icon-btn" type="button" data-close-dialog aria-label="Close">×</button></div>`; }
  document.addEventListener('click',e=>{ if(e.target.closest('[data-close-dialog]')) closeDialog(); });

  async function copyText(text){
    try{ await navigator.clipboard.writeText(text); toast('Copied'); }
    catch{ const ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); toast('Copied'); }
  }
  function hasPywebviewBridge(){ return Boolean(window.pywebview?.api?.save_url); }
  function hasTauriBridge(){ return Boolean(window.__TAURI__?.core?.invoke); }
  function isDesktopBridge(){ return hasPywebviewBridge() || hasTauriBridge(); }
  async function desktopChooseFolder(){
    if(hasTauriBridge()) return window.__TAURI__.core.invoke('choose_folder');
    if(window.pywebview?.api?.choose_folder) return window.pywebview.api.choose_folder();
    return null;
  }
  async function desktopSaveUrl(url, suggestedName='download'){
    if(hasTauriBridge()) return window.__TAURI__.core.invoke('save_url',{relativeUrl:url,suggestedName});
    if(window.pywebview?.api?.save_url) return window.pywebview.api.save_url(url, suggestedName);
    return null;
  }
  async function downloadResource(url, suggestedName='download'){
    if(isDesktopBridge()){
      try{ const saved=await desktopSaveUrl(url, suggestedName); if(saved) toast(`Saved to ${saved}`); return Boolean(saved); }
      catch(err){ toast(`Could not save file: ${err.message||err}`, true); return false; }
    }
    try{
      const r=await fetch(url,{credentials:'same-origin'}); if(!r.ok){let d={};try{d=await r.json();}catch{}throw new Error(d.detail||'Download failed');}
      const blob=await r.blob(), cd=r.headers.get('content-disposition')||'';
      const filename=(cd.match(/filename="?([^";]+)"?/)||[])[1]||suggestedName;
      const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),1500); return true;
    }catch(err){ toast(err.message||'Download failed',true); return false; }
  }

  function tagEditorHtml(name,tags=[]){
    const clean=[...new Set((tags||[]).map(x=>String(x).trim()).filter(Boolean))];
    return `<div class="tag-editor" data-tag-editor data-name="${esc(name)}" data-tags='${esc(JSON.stringify(clean))}'><div class="tag-token-list"></div><input type="text" aria-label="Add tag" placeholder="Type + Space or comma"><input type="hidden" name="${esc(name)}"></div><span class="tag-help">Space or comma makes a tag.</span>`;
  }
  function initTagEditors(root=document){
    $$('[data-tag-editor]',root).forEach(editor=>{
      const input=$('input[type="text"]',editor), hidden=$('input[type="hidden"]',editor), list=$('.tag-token-list',editor);
      let tags=[]; try{tags=JSON.parse(editor.dataset.tags||'[]');}catch{}
      const sync=()=>{ editor.dataset.tags=JSON.stringify(tags); hidden.value=tags.join(','); list.innerHTML=tags.map((t,i)=>`<span class="tag-token">${esc(t)}<button type="button" data-tag-remove="${i}" aria-label="Remove ${esc(t)}">×</button></span>`).join(''); $$('[data-tag-remove]',list).forEach(b=>b.onclick=()=>{tags.splice(Number(b.dataset.tagRemove),1);sync();}); };
      const commit=()=>{ const vals=input.value.split(/[\s,]+/).map(x=>x.trim()).filter(Boolean); vals.forEach(v=>{if(!tags.includes(v))tags.push(v);}); input.value=''; sync(); };
      input.addEventListener('keydown',e=>{ if((e.key===' '||e.key===','||e.key==='Enter')&&input.value.trim()){e.preventDefault();commit();} else if(e.key==='Backspace'&&!input.value&&tags.length){tags.pop();sync();} });
      input.addEventListener('input',()=>{if(/[\s,]/.test(input.value)&&input.value.trim().length>1)commit();}); input.addEventListener('blur',()=>{if(input.value.trim())commit();}); sync();
    });
  }
  function tagsFromForm(form,name='tags'){ const editor=form.querySelector(`[data-tag-editor][data-name="${name}"]`); if(!editor)return[]; try{return JSON.parse(editor.dataset.tags||'[]');}catch{return[];} }
  function multiCheckHtml(name,items,selected=[]){
    return `<div class="multi-check" data-multi-check="${esc(name)}"><div class="tag-token-list selected-token-list"></div><details class="multi-dropdown"><summary>Select…</summary><div class="dropdown-checks check-stack">${items.map(it=>`<label class="check-row"><input type="checkbox" value="${esc(it.value)}" data-label="${esc(it.label)}" ${selected.includes(it.value)?'checked':''}> <span>${esc(it.label)}</span></label>`).join('')}<div class="dropdown-done-row"><button type="button" class="btn compact secondary multi-done">Done</button></div></div></details></div>`;
  }
  function initMultiChecks(root=document){
    $$('[data-multi-check]',root).forEach(group=>{
      const list=$('.selected-token-list',group),boxes=$$('input[type=checkbox]',group),details=$('details',group);
      const sync=()=>{list.innerHTML=boxes.filter(x=>x.checked).map(x=>`<span class="tag-token">${esc(x.dataset.label||x.value)}</span>`).join('');};
      boxes.forEach(x=>x.onchange=sync); $('.multi-done',group)?.addEventListener('click',()=>details.removeAttribute('open'));
      details?.addEventListener('keydown',e=>{if(e.key==='Escape')details.removeAttribute('open');});
      sync();
    });
  }
  function multiValues(form,name){ const g=form.querySelector(`[data-multi-check="${name}"]`); return g?$$('input[type=checkbox]:checked',g).map(x=>x.value):[]; }
  document.addEventListener('click',e=>{ $$('details.multi-dropdown[open]').forEach(d=>{ if(!d.contains(e.target)) d.removeAttribute('open'); }); });

  function showRecoveryCodeDialog(project, onContinue){
    const code=project?.owner_recovery_code;
    if(!code){onContinue?.();return;}
    openDialog(`${dialogHeader('RECOVERY','Save your Owner recovery code')}<div class="banner warn"><strong>This code is your break-glass Owner recovery.</strong><br>Keep it somewhere safe. Cocklebur stores only a hash and cannot show this same code again.</div><label>Owner recovery code<input id="ownerRecoveryCodeValue" value="${esc(code)}" readonly></label><div class="modal-actions"><button type="button" class="btn secondary" id="copyOwnerRecoveryCode">Copy code</button><button type="button" class="btn" id="continueAfterRecovery">I saved it</button></div>`);
    $('#copyOwnerRecoveryCode').onclick=()=>copyText(code);
    $('#continueAfterRecovery').onclick=()=>{closeDialog();onContinue?.();};
  }

  function showHostRecoveryCodeDialog(result, onContinue){
    const code=result?.host_recovery_code;
    if(!code){onContinue?.();return;}
    openDialog(`${dialogHeader('INSTANCE HOST','Save your Host recovery code')}<div class="banner warn"><strong>This code recovers Instance Host access on another browser.</strong><br>The bootstrap key is not accepted after the instance has been claimed. Save this code somewhere safe; recovery rotates it.</div><label>Host recovery code<input id="hostRecoveryCodeValue" value="${esc(code)}" readonly></label><div class="modal-actions"><button type="button" class="btn secondary" id="copyHostRecoveryCode">Copy code</button><button type="button" class="btn" id="continueAfterHostRecovery">I saved it</button></div>`);
    $('#copyHostRecoveryCode').onclick=()=>copyText(code);
    $('#continueAfterHostRecovery').onclick=()=>{closeDialog();onContinue?.();};
  }

  async function initHome(){
    const mode=document.body.dataset.mode;
    let access={host:mode!=='server',host_claimed:mode!=='server',can_create_projects:true,can_import_projects:true,sources:[]};
    const projectDialog=$('#projectDialog'), projectForm=$('#projectForm');
    const modeSelect=$('#projectForm select[name=mode]');
    const updateStorageVisibility=()=>{const row=$('#customStorageRow');if(row)row.hidden=!(mode==='local'&&modeSelect.value==='local'&&(hasTauriBridge()||window.pywebview?.api?.choose_folder));};
    const applyInstanceUI=()=>{
      $$('.host-admin-only').forEach(el=>el.style.display=access.host?'':'none');
      $$('.create-permission').forEach(el=>el.style.display=access.can_create_projects?'':'none');
      $$('.import-permission').forEach(el=>el.style.display=access.can_import_projects?'':'none');
      const btn=$('#hostAccessBtn');
      if(btn)btn.textContent=access.host?'Host access ✓':access.host_claimed?'Host recovery':'Claim Host';
      if(mode==='local'){
        $('#modeNotice').textContent='Local mode — project data stays on this machine unless you export or share it.';
      }else if(access.host){
        $('#modeNotice').textContent='Server mode — Instance Host access is enabled. Host can manage instance permissions; project roles remain separate.';
      }else if(access.can_create_projects||access.can_import_projects){
        const caps=[access.can_create_projects?'Create projects':'',access.can_import_projects?'Import packs':''].filter(Boolean).join(' + ');
        $('#modeNotice').textContent=`Server mode — delegated instance permission enabled: ${caps}. Your Owner/Member/Viewer roles remain project-specific.`;
      }else{
        $('#modeNotice').textContent='Server mode — open an invitation or recover project access. Creating or importing projects requires an instance permission.';
      }
    };
    const refreshAccess=async()=>{
      if(mode!=='server'){applyInstanceUI();return access;}
      try{access=await api('/api/instance/access');}catch{access={host:false,host_claimed:false,can_create_projects:false,can_import_projects:false,sources:[]};}
      applyInstanceUI();return access;
    };
    await refreshAccess();

    $('#newProjectBtn').onclick=()=>projectDialog.showModal();
    $$('.project-dialog-cancel',projectDialog).forEach(b=>b.onclick=()=>projectDialog.close());
    const bindFolderPicker=()=>{updateStorageVisibility();const b=$('#chooseFolderBtn');if(b&&(hasTauriBridge()||window.pywebview?.api?.choose_folder))b.onclick=async()=>{try{const path=await desktopChooseFolder();if(path)$('#storagePath').value=path;}catch(err){toast(`Could not open folder picker: ${err.message||err}`,true);}};};
    modeSelect.addEventListener('change',updateStorageVisibility); bindFolderPicker();
    window.addEventListener('pywebviewready',bindFolderPicker);

    const openHostPanel=async()=>{
      if(access.host){
        let status={};try{status=await api('/api/host/status');}catch{}
        const name=status.host_profile?.display_name||'Host';
        openDialog(`${dialogHeader('INSTANCE HOST','Host access')}<div class="banner"><strong>${esc(name)}</strong><br>Host manages the Cocklebur instance. Project ownership remains separate.</div><div class="form-stack"><button type="button" class="btn secondary" id="rotateHostRecoveryBtn">Generate new Host recovery code</button><button type="button" class="btn secondary" id="openInstancePermissionsFromHost">Manage instance permissions</button></div><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Close</button><button type="button" class="btn danger" id="hostLogoutBtn">Sign out Host access</button></div>`);
        $('#rotateHostRecoveryBtn').onclick=async()=>{try{const r=await api('/api/host/recovery/rotate',{method:'POST'});showHostRecoveryCodeDialog(r,()=>refreshAccess());}catch(err){toast(err.message,true);}};
        $('#openInstancePermissionsFromHost').onclick=()=>{closeDialog();openInstancePermissions();};
        $('#hostLogoutBtn').onclick=async()=>{try{await api('/api/host/logout',{method:'POST'});closeDialog();await refreshAccess();toast('Host access signed out');}catch(err){toast(err.message,true);}};
        return;
      }
      if(!access.host_claimed){
        openDialog(`${dialogHeader('INSTANCE HOST','Claim this Cocklebur instance')}<p class="muted">The deployment bootstrap key is used once to designate the application-level Host. After claim, the bootstrap key no longer grants Host access.</p><form id="hostClaimForm" class="form-stack"><label>Host display name<input name="display_name" maxlength="100" value="Host" required></label><label>Bootstrap key<input name="key" type="password" autocomplete="off" required></label><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">Claim Host</button></div></form>`);
        $('#hostClaimForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{const r=await api('/api/host/login',{method:'POST',body:{key:String(fd.get('key')||''),display_name:String(fd.get('display_name')||'Host')}});closeDialog();await refreshAccess();showHostRecoveryCodeDialog(r,()=>refreshAccess());}catch(err){toast(err.message,true);}};
      }else{
        openDialog(`${dialogHeader('INSTANCE HOST','Recover Host access')}<div class="banner warn"><strong>The bootstrap key is disabled after Host claim.</strong><br>Use the current Host recovery code on a new browser. Successful recovery keeps existing Host sessions and rotates the code.</div><form id="hostRecoverForm" class="form-stack"><label>Host recovery code<input name="code" autocomplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX" required autofocus></label><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">Recover Host access</button></div></form>`);
        $('#hostRecoverForm').onsubmit=async e=>{e.preventDefault();try{const r=await api('/api/host/recover',{method:'POST',body:{code:String(new FormData(e.currentTarget).get('code')||'')}});closeDialog();await refreshAccess();showHostRecoveryCodeDialog(r,()=>refreshAccess());}catch(err){toast(err.message,true);}};
      }
    };
    $('#hostAccessBtn')?.addEventListener('click',openHostPanel);

    async function openInstancePermissions(){
      try{
        const people=await api('/api/instance/people');
        const body=people.length?people.map(p=>`<div class="instance-person-row" data-project-id="${esc(p.project_id)}" data-person-id="${esc(p.person_id)}"><div class="instance-person-main"><strong>${esc(p.display_name)}</strong><span>${esc(p.project_name)} · ${esc(p.role)}</span></div><label class="instance-cap"><input type="checkbox" data-cap="create" ${p.can_create_projects?'checked':''}> Create</label><label class="instance-cap"><input type="checkbox" data-cap="import" ${p.can_import_projects?'checked':''}> Import</label><button class="btn compact secondary instance-cap-save" type="button">Save</button></div>`).join(''):'<div class="empty">No project identities exist yet. People appear here after they join or own a Server project.</div>';
        openDialog(`${dialogHeader('INSTANCE','Instance permissions')}<p class="muted">Create / Import are instance-level capabilities added on top of a person’s project role. Granting them does not make that person Host or Owner of other projects.</p><div class="banner"><strong>Host</strong> always has Create + Import. Infrastructure administrators are outside Cocklebur’s app roles.</div><div class="instance-people-list">${body}</div><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Close</button></div>`);
        $$('.instance-cap-save').forEach(btn=>btn.onclick=async()=>{const row=btn.closest('.instance-person-row'),projectId=row.dataset.projectId,personId=row.dataset.personId;const canCreate=$('[data-cap="create"]',row).checked,canImport=$('[data-cap="import"]',row).checked;try{await api(`/api/instance/people/${encodeURIComponent(projectId)}/${encodeURIComponent(personId)}/permissions`,{method:'PATCH',body:{can_create_projects:canCreate,can_import_projects:canImport}});toast('Instance permissions updated');}catch(err){toast(err.message,true);}});
      }catch(err){toast(err.message,true);}
    }
    $('#instancePermissionsBtn')?.addEventListener('click',openInstancePermissions);

    $('#ownerRecoveryBtn')?.addEventListener('click',()=>{
      const remembered=JSON.parse(lsGet('pw_projects','[]'));
      openDialog(`${dialogHeader('OWNER RECOVERY','Recover project ownership')}<div class="banner warn"><strong>Use Owner recovery only on a browser with no project session.</strong><br>It restores the existing Owner identity on this browser; it does not promote a Member account. Members/Viewers should use an Owner-generated one-time recovery link.</div><form id="ownerRecoverHomeForm" class="form-stack"><label>Project ID<input name="project_id" required value="${esc(remembered.length===1?remembered[0]:'')}" placeholder="p_..."></label><label>Owner recovery code<input name="code" required autocomplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX"></label><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">Recover Owner access</button></div></form>`);
      $('#ownerRecoverHomeForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget),projectId=String(fd.get('project_id')||'').trim();try{const r=await api(`/api/projects/${encodeURIComponent(projectId)}/owner-recover`,{method:'POST',body:{code:String(fd.get('code')||'').trim()}});rememberProject(projectId);showRecoveryCodeDialog({...r,owner_recovery_code:r.owner_recovery_code},()=>location.href=`/project/${projectId}`);}catch(err){toast(err.message,true);}};
    });

    projectForm.addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.currentTarget),body=Object.fromEntries(fd.entries());body.expiry=body.expiry||null;try{const p=await api('/api/projects',{method:'POST',body});rememberProject(p.id);projectDialog.close();showRecoveryCodeDialog(p,()=>location.href=`/project/${p.id}`);}catch(err){toast(err.message,true);}});
    $('#importBtn').onclick=()=>{const input=$('#importFile');input.value='';input.click();};
    $('#importFile').onchange=async()=>{const input=$('#importFile'),f=input.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{const p=await api('/api/projects/import',{method:'POST',body:fd});rememberProject(p.id);toast('Project imported');showRecoveryCodeDialog(p,()=>location.href=`/project/${p.id}`);}catch(err){toast(err.message,true);}finally{input.value='';}};
    await loadProjects();
    async function loadProjects(){
      let items=[];
      if(mode==='local'){try{items=await api('/api/local/projects');}catch(err){toast(err.message,true);}}
      else{const ids=JSON.parse(lsGet('pw_projects','[]'));items=(await Promise.all(ids.map(async id=>{try{return await api(`/api/projects/${id}/summary`);}catch{return null;}}))).filter(Boolean);}
      const grid=$('#projectGrid');
      if(!items.length){grid.innerHTML=`<div class="empty-card"><div><strong>No accessible projects in this browser.</strong><p class="muted">${mode==='server'?'Open an invitation, recover project access, or use an authorized Create / Import action.':'Create a project or import a project pack.'}</p></div></div>`;return;}
      grid.innerHTML=items.map(p=>`<a class="project-card" href="/project/${p.id}"><div><span class="status-pill">${esc(p.status||'active')}</span></div><h3>${esc(p.name)}</h3><p>${esc(p.description||'No description yet.')}</p><div class="project-meta"><span>${esc(p.role||p.mode||'local')}</span><span>${p.expiry?`Ends ${esc(fmtShortDate(p.expiry))}`:'No end date'}</span></div></a>`).join('');
    }
  }

  async function initLocked(){
    const pid=document.body.dataset.projectId, form=$('#ownerRecoverLockedForm');
    form.onsubmit=async e=>{e.preventDefault();const code=new FormData(form).get('code');try{const r=await api(`/api/projects/${pid}/owner-recover`,{method:'POST',body:{code}});rememberProject(pid);showRecoveryCodeDialog(r,()=>location.href=`/project/${pid}`);}catch(err){toast(err.message,true);}};
  }

  async function initJoin(){
    const pid=document.body.dataset.projectId, token=document.body.dataset.token;
    $('#joinForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{await api(`/api/projects/${pid}/join`,{method:'POST',body:{display_name:fd.get('display_name'),pin:fd.get('pin')||null,token}});rememberProject(pid);location.href=`/project/${pid}`;}catch(err){toast(err.message,true);}};
  }

  async function initProject(){
    const pid=window.PW_PROJECT||document.body.dataset.projectId; rememberProject(pid);
    const state={project:null,me:null,cards:[],people:[],announcements:[],channels:[],files:[],activity:[],settings:null,uploadLimits:null,channel:'general',overviewThreads:[],threads:[],cardScope:'active',selectedFiles:new Set(),pendingThread:null};
    const isOwner=()=>state.me?.role==='owner', canWrite=()=>['owner','member'].includes(state.me?.role);
    const isLocalProject=()=>state.project?.mode==='local';
    const canEditCard=c=>Boolean(c&&canWrite()&&((c.edit_access||'public')==='public'||c.created_by===state.me?.id));
    const canDeleteCard=c=>Boolean(c&&canWrite()&&c.created_by===state.me?.id);
    const canChangeCardAccess=c=>Boolean(c&&c.created_by===state.me?.id&&canWrite());
    const canChangeCardVisibility=c=>Boolean(c&&c.created_by===state.me?.id&&canWrite());
    const personName=id=>id==='system'?'System':(state.people.find(p=>p.id===id)?.display_name||id||'System');
    const initials=id=>(personName(id)||'?').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
    const nl2br=s=>esc(s||'').replace(/\n/g,'<br>');

    function go(tab){
      $$('.tab-panel').forEach(x=>x.classList.toggle('active',x.dataset.panel===tab)); $$('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab));
      const mark=tab==='settings'?null:tab; if(['cards','announcements','discussion','files'].includes(mark)) api(`/api/projects/${pid}/mark-seen`,{method:'POST',body:{module:mark,cursor:nowIso()}}).then(loadUnread).catch(()=>{});
      if(tab==='people')renderPeople(); if(tab==='settings')fillSettings();
      const active=$(`[data-tab="${tab}"]`); active?.scrollIntoView({behavior:'smooth',inline:'center',block:'nearest'}); window.scrollTo({top:0,behavior:'smooth'});
    }
    function setSettingsTab(tab){ $$('.settings-tabs [data-settings-tab]').forEach(b=>b.classList.toggle('active',b.dataset.settingsTab===tab));$$('[data-settings-panel]').forEach(p=>p.classList.toggle('active',p.dataset.settingsPanel===tab));if(tab==='activities'){api(`/api/projects/${pid}/activity`).then(items=>{state.activity=items;renderActivity();}).catch(()=>renderActivity());}go('settings'); }
    $$('[data-tab]').forEach(b=>b.onclick=()=>go(b.dataset.tab));
    document.addEventListener('click',e=>{const target=e.target.closest('[data-go]');if(target)go(target.dataset.go);const st=e.target.closest('[data-settings-tab]');if(st&&st.closest('.panel-heading'))setSettingsTab(st.dataset.settingsTab);});
    $$('.settings-tabs [data-settings-tab]').forEach(b=>b.onclick=()=>setSettingsTab(b.dataset.settingsTab));
    $$('[data-filter-toggle]').forEach(b=>b.onclick=()=>{const p=$(`#${b.dataset.filterToggle}`);p.hidden=!p.hidden;b.classList.toggle('active',!p.hidden);});

    try{await loadAll();}catch(err){toast(err.message,true);return;}
    applyRoleUI(); bindActions(); renderAll();
    if(window.matchMedia?.('(max-width: 620px)').matches){requestAnimationFrame(()=>$('[data-tab].active')?.scrollIntoView({inline:'center',block:'nearest'}));}

    async function loadAll(){
      const [project,me,cards,people,announcements,channels,files,activity,unread]=await Promise.all([api(`/api/projects/${pid}`),api(`/api/projects/${pid}/me`),api(`/api/projects/${pid}/cards`),api(`/api/projects/${pid}/people`),api(`/api/projects/${pid}/announcements`),api(`/api/projects/${pid}/channels`),api(`/api/projects/${pid}/files`),api(`/api/projects/${pid}/activity`),api(`/api/projects/${pid}/unread-counts`)]);
      Object.assign(state,{project,me,cards,people,announcements,channels,files,activity}); if(isOwner()){try{state.settings=await api(`/api/projects/${pid}/settings`);}catch{}} await loadOverviewThreads(); renderUnread(unread); populateFilters();
    }
    async function loadOverviewThreads(){ const all=[];for(const ch of state.channels){try{const threads=await api(`/api/projects/${pid}/channels/${ch.id}/threads`);threads.forEach(t=>all.push({...t,channel_id:ch.id,channel_name:ch.name}));}catch{}}state.overviewThreads=all.sort((a,b)=>String(b.last_activity||'').localeCompare(String(a.last_activity||''))); }
    function applyRoleUI(){
      $$('.owner-only').forEach(el=>el.style.display=isOwner()?'':'none');
      $$('.server-only').forEach(el=>el.style.display=isLocalProject()?'none':'');
      $$('.writable').forEach(el=>{el.disabled=!canWrite();el.title=canWrite()?'':'Viewer access is read-only';});
      if(isLocalProject()){
        if($('#peopleEyebrow'))$('#peopleEyebrow').textContent='USER';
        if($('#peopleTitle'))$('#peopleTitle').textContent='User';
        if($('#peopleSubtitle'))$('#peopleSubtitle').textContent='Local identity and Owner recovery for this project.';
      }
    }
    function renderAll(){renderOverview();renderCards();renderAnnouncements();renderChannels();renderFiles();renderPeople();renderActivity();fillSettings();}
    function renderUnread(u){$('#cardsUnread').textContent=u.cards||'';$('#annUnread').textContent=u.announcements||'';$('#discussionUnread').textContent=u.discussion||'';$('#filesUnread').textContent=u.files||'';}
    async function loadUnread(){try{renderUnread(await api(`/api/projects/${pid}/unread-counts`));}catch{}}
    async function refreshActivity(){try{state.activity=await api(`/api/projects/${pid}/activity`);$('#recentActivity').innerHTML=activityHtml(state.activity.slice(0,6));renderActivity();}catch{}}
    function populateFilters(){
      const people=state.people.map(p=>`<label class="check-row"><input type="checkbox" value="${p.id}"> <span>${esc(p.display_name)}</span></label>`).join('');
      $('#cardAssigneeChecks').innerHTML=people; $('#discussionAuthorChecks').innerHTML=people; $('#fileUploaderChecks').innerHTML=people;
      const exts=[...new Set(state.files.map(f=>(f.name.split('.').pop()||'').toLowerCase()).filter(Boolean))].sort(); $('#fileTypeChecks').innerHTML=exts.map(x=>`<label class="check-row"><input type="checkbox" value="${esc(x)}"> <span>.${esc(x)}</span></label>`).join('')||'<span class="muted">No file types yet.</span>';
      const tags=[...new Set(state.overviewThreads.flatMap(t=>t.root?.tags||[]))].sort(); $('#discussionTagFilter').innerHTML=tags.map(x=>`<label class="check-row"><input type="checkbox" value="${esc(x)}"> <span>${esc(x)}</span></label>`).join('')||'<span class="muted">No tags yet.</span>';
      $$('#cardFilterPanel input').forEach(x=>x.onchange=renderCards); $$('#discussionFilterPanel input').forEach(x=>x.onchange=renderThreads); $$('#fileFilterPanel input').forEach(x=>x.onchange=renderFiles);
    }

    function activityLabel(type=''){
      const map={
        'card.created':'Card created','card.updated':'Card updated','card.deleted':'Card deleted','card.content_updated':'Card content updated','card.title_updated':'Card title updated','card.status_changed':'Card status changed','card.checklist_completed':'Checklist item completed','card.checklist_reopened':'Checklist item reopened','card.edit_access_changed':'Card edit access changed','card.visibility_changed':'Card visibility changed','card.assignees_updated':'Card assignees updated','card.tags_updated':'Card tags updated','card.schedule_updated':'Card schedule updated',
        'file.uploaded':'File uploaded','file.updated':'File updated','file.deleted':'File deleted',
        'announcement.created':'Announcement created','announcement.edit':'Announcement updated','announcement.delete':'Announcement deleted',
        'thread.created':'Discussion started','reply.created':'Reply added','message.edit':'Message updated','message.delete':'Message deleted',
        'member.joined':'Member joined','member.updated':'Member updated','member.removed':'Member removed','member.access_regenerated':'Recovery link generated','member.access_issued':'Member access issued','member.recovered':'Member recovered','owner.recovered':'Owner recovered','owner.recovery_rotated':'Owner recovery code rotated',
        'invite.regenerated':'Invite regenerated','channel.created':'Channel created','channel.updated':'Channel updated','channel.deleted':'Channel deleted','settings.updated':'Settings updated',
        'project.created':'Project created','project.updated':'Project updated','project.closing':'Project closing','project.archived':'Project archived','project.exported':'Project exported','project.imported':'Project imported'
      };
      if(map[type]) return map[type];
      return 'Activity';
    }
    function activityDetail(a){
      const who=a.actor_name||personName(a.actor_id),m=a.meta||{},title=a.summary||'this card';
      if(a.type==='card.created')return `${who} created “${title}”`;
      if(a.type==='card.checklist_completed')return `${who} completed “${m.item||'checklist item'}”`;
      if(a.type==='card.checklist_reopened')return `${who} reopened “${m.item||'checklist item'}”`;
      if(a.type==='card.status_changed')return `${who} changed status to ${statusLabel(m.to)}`;
      if(a.type==='card.content_updated')return `${who} updated the card content`;
      if(a.type==='card.title_updated')return `${who} changed the card title`;
      if(a.type==='card.edit_access_changed')return `${who} changed edit access to ${(m.to||'public').replace(/^./,x=>x.toUpperCase())}`;
      if(a.type==='card.visibility_changed')return `${who} changed visibility to ${m.to==='private'?'Only me':'Everyone'}`;
      if(a.type==='card.assignees_updated')return `${who} updated assignees`;
      if(a.type==='card.tags_updated')return `${who} updated tags`;
      if(a.type==='card.schedule_updated')return `${who} updated the schedule`;
      if(a.type==='card.deleted')return `${who} deleted “${title}”`;
      return `${who} · ${activityLabel(a.type)}${a.summary?` · ${a.summary}`:''}`;
    }
    function activityHtml(items){return items.length?items.map(a=>`<div class="activity-row"><time>${esc(fmtDate(a.ts))}</time><div><strong>${esc(activityLabel(a.type))}</strong><div class="muted">${esc(activityDetail(a))}</div></div></div>`).join(''):'<div class="empty">No activity yet.</div>';}
    function statusLabel(v){return ({todo:'Pending',doing:'In Progress',done:'Done',scheduled:'Scheduled',happened:'Done',archived:'Archived'})[v]||v||'Pending';}
    function isArchivedCard(c){return ['done','archived','happened'].includes(c.status);}
    function contentSummary(text=''){return text.split('\n').map(x=>x.replace(/^\s*(?:[-*]\s+)?\[[ xX]\]\s*/,'').replace(/^[-*#>]+\s*/,'').trim()).filter(Boolean).join(' ').slice(0,220);}
    function checklistLines(content=''){const out=[];content.split('\n').forEach((line,i)=>{const m=line.match(/^(\s*(?:[-*]\s+)?\[)( |x|X)(\]\s+)(.*)$/);if(m)out.push({lineIndex:i,checked:m[2].toLowerCase()==='x',text:m[4]});});return out;}

    function renderOverview(){
      const openDashboardCards=new Set($$('.dashboard-accordion.open').map(el=>el.dataset.dashboardCard).filter(Boolean));
      $('#projectName').textContent=state.project.name; $('#projectDescription').textContent=state.project.description||'No description yet.';
      const anns=state.announcements.filter(a=>!a.deleted).slice(0,3); $('#overviewAnnouncements').innerHTML=anns.length?anns.map(a=>`<div class="mini-timeline-item"><button data-go="announcements"><strong>${esc(a.title||'Announcement')}</strong><p>${esc(contentSummary(a.body))}</p></button></div>`).join(''):'<div class="empty">No announcements yet.</div>';
      const todos=state.cards.filter(c=>c.type==='task'&&!isArchivedCard(c)).slice(0,3); $('#overviewTodos').innerHTML=dashboardCards(todos);
      const events=state.cards.filter(c=>c.type==='event'&&!isArchivedCard(c)).sort((a,b)=>String(a.start||'').localeCompare(String(b.start||''))).slice(0,3); $('#overviewEvents').innerHTML=dashboardCards(events,true);
      $$('.dashboard-accordion[data-dashboard-card]').forEach(el=>{if(openDashboardCards.has(el.dataset.dashboardCard))el.classList.add('open');});
      const threads=state.overviewThreads.slice(0,3); $('#overviewDiscussions').innerHTML=threads.length?threads.map(t=>`<button class="dashboard-thread" data-thread-go="${t.channel_id}|${t.id}"><strong>${esc(t.root?.title||'Thread')}</strong><span>#${esc(t.channel_name)} · ${t.reply_count||0} replies</span></button>`).join(''):'<div class="empty">No discussions yet.</div>';
      $('#recentActivity').innerHTML=activityHtml(state.activity.slice(0,6));
      api(`/api/projects/${pid}/activity`).then(items=>{state.activity=items;$('#recentActivity').innerHTML=activityHtml(state.activity.slice(0,6));}).catch(()=>{});
      const e=$('#expiryBanner');e.innerHTML='';if(state.project.expiry){const d=new Date(`${state.project.expiry}T23:59:59`),days=Math.ceil((d-Date.now())/86400000);if(days<=14)e.innerHTML=`<div class="banner ${days<0?'warn':''}">${days<0?'Expected end date passed':`${days} day${days===1?'':'s'} until the expected end date`}.</div>`;}
      $$('[data-thread-go]').forEach(b=>b.onclick=()=>{const [ch,tid]=b.dataset.threadGo.split('|');state.channel=ch;state.pendingThread=tid;go('discussion');renderChannels();});
      $$('.dashboard-accordion>button').forEach(b=>b.onclick=()=>b.parentElement.classList.toggle('open'));
      bindChecklistControls($('#overviewTodos')); bindChecklistControls($('#overviewEvents')); return Promise.all([renderMdElements($('#overviewTodos')),renderMdElements($('#overviewEvents'))]);
    }
    function dashboardCards(items,isEvent=false){
      if(!items.length)return'<div class="empty">Nothing here yet.</div>';
      return items.map(c=>`<div class="dashboard-accordion" data-dashboard-card="${c.id}"><button><div class="dashboard-accordion-title"><strong>${esc(c.title)}</strong><span>${isEvent&&c.start?esc(fmtDate(c.start)):esc(statusLabel(c.status))}</span>${(c.tags||[]).length?`<div class="dashboard-card-tags">${c.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>`:''}</div><span>${icon('chevron')}</span></button><div class="dashboard-accordion-body">${cardPreview(c)}</div></div>`).join('');
    }

    function selectedFilterValues(root,name){return $$(`input[name="${name}"]:checked`,root).map(x=>x.value);}
    function cardFiltered(){
      const q=($('#cardSearch').value||'').toLowerCase().trim(),types=selectedFilterValues($('#cardFilterPanel'),'card_type'),statuses=selectedFilterValues($('#cardFilterPanel'),'card_status'),assignees=$$('#cardAssigneeChecks input:checked').map(x=>x.value);
      return state.cards.filter(c=>{const scope=state.cardScope==='archive'?isArchivedCard(c):!isArchivedCard(c);return scope&&(!q||`${c.title} ${c.content} ${(c.tags||[]).join(' ')}`.toLowerCase().includes(q))&&(!types.length||types.includes(c.type))&&(!statuses.length||statuses.includes(c.status)||(statuses.includes('done')&&c.status==='happened'))&&(!assignees.length||assignees.some(id=>(c.assignees||[]).includes(id)));});
    }
    function cardPreview(c){
      const checks=checklistLines(c.content||''), non=(c.content||'').split('\n').filter(line=>!/^\s*(?:[-*]\s+)?\[[ xX]\]\s+/.test(line)).join('\n').trim();
      let html='';
      if(non)html+=`<div data-md="${esc(non)}">${esc(non)}</div>`;
      if(checks.length)html+=`<div class="card-checklist">${checks.map(it=>`<label class="card-check-row ${it.checked?'done':''}"><input type="checkbox" data-check-card="${c.id}" data-check-line="${it.lineIndex}" ${it.checked?'checked':''} ${canEditCard(c)?'':'disabled'}><span>${esc(it.text)}</span></label>`).join('')}</div>`;
      return html||'<span class="muted">No content yet.</span>';
    }
    function statusChoices(c){
      return c.type==='event'
        ? [['scheduled','Scheduled'],['done','Done'],['archived','Archived']]
        : [['todo','Pending'],['doing','In Progress'],['done','Done'],['archived','Archived']];
    }
    function cardTile(c){
      const avatars=(c.assignees||[]).slice(0,4).map(id=>`<span class="mini-avatar" title="${esc(personName(id))}">${esc(initials(id))}</span>`).join('');
      const editable=canEditCard(c),deletable=canDeleteCard(c),access=(c.edit_access||'public'),visibility=(c.visibility||'everyone');
      const statusUi=editable?`<details class="status-quick"><summary class="status-badge">${esc(statusLabel(c.status))}</summary><div class="status-popover">${statusChoices(c).map(([value,label])=>`<button type="button" data-card-status="${esc(value)}" class="${(c.status==='happened'?'done':c.status)===value?'active':''}">${esc(label)}</button>`).join('')}</div></details>`:`<span class="status-badge">${esc(statusLabel(c.status))}</span>`;
      const openButton=`<button class="mini-icon-btn card-open" aria-label="${editable?'Edit':'View'} card">${icon(editable?'edit':'eye')}</button>`;
      return `<article class="work-card" data-card-id="${c.id}"><div class="work-card-head"><div class="work-card-title"><div class="work-card-badges"><span class="type-badge">${c.type==='event'?'Event':'To-do'}</span>${statusUi}<span class="access-badge">${access==='private'?'Creator edit':'Shared edit'}</span><span class="visibility-badge">${visibility==='private'?'Only me':'Everyone'}</span></div><h3>${esc(c.title)}</h3></div><div class="work-card-actions">${openButton}${deletable?`<button class="mini-icon-btn danger card-delete" aria-label="Delete card">${icon('trash')}</button>`:''}</div></div>${c.start?`<div class="work-card-meta"><span class="meta-inline">${icon('calendar')}<span>${esc(fmtDate(c.start))}</span>${c.type==='event'?`<button class="text-link card-ics" data-url="/api/projects/${pid}/cards/${c.id}/ics">Add to calendar</button>`:''}</span></div>`:''}${(c.tags||[]).length?`<div class="work-card-tags">${c.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>`:''}<div class="work-card-body">${cardPreview(c)}</div><div class="work-card-footer"><div><div class="avatar-stack">${avatars}</div><span class="card-author">Created by ${esc(personName(c.created_by))}</span></div><span>v${c.version}</span></div></article>`;
    }
    function checklistScrollState(cb){
      const workCard=cb.closest('[data-card-id]'),dashCard=cb.closest('[data-dashboard-card]');
      const container=cb.closest('.work-card-body, .dashboard-accordion-body');
      return {kind:workCard?'card':dashCard?'dashboard':null,cardId:workCard?.dataset.cardId||dashCard?.dataset.dashboardCard||cb.dataset.checkCard||null,top:container?.scrollTop||0,left:container?.scrollLeft||0,pageX:window.scrollX,pageY:window.scrollY};
    }
    function restoreChecklistScroll(pos){
      if(!pos?.cardId)return;
      const selector=pos.kind==='dashboard'?`.dashboard-accordion[data-dashboard-card="${CSS.escape(pos.cardId)}"] .dashboard-accordion-body`:`.work-card[data-card-id="${CSS.escape(pos.cardId)}"] .work-card-body`;
      const apply=()=>{const container=$(selector);if(container){container.scrollTop=pos.top;container.scrollLeft=pos.left;}window.scrollTo(pos.pageX,pos.pageY);};
      requestAnimationFrame(()=>{apply();requestAnimationFrame(apply);});
    }
    function checklistPeers(cardId,lineIndex){const cid=CSS.escape(String(cardId)),line=CSS.escape(String(lineIndex));return $$(`input[data-check-card="${cid}"][data-check-line="${line}"]`);}
    function setChecklistDom(cardId,lineIndex,checked,{pending=false}={}){checklistPeers(cardId,lineIndex).forEach(peer=>{peer.checked=checked;peer.dataset.checkPending=pending?'1':'0';peer.closest('.card-check-row')?.classList.toggle('done',checked);});}
    function setCardVersionDom(cardId,version){const node=$(`.work-card[data-card-id="${CSS.escape(String(cardId))}"] .work-card-footer > span:last-child`);if(node)node.textContent=`v${version}`;}
    function bindChecklistControls(root=document){$$('[data-check-card]',root).forEach(cb=>cb.onchange=()=>toggleInlineChecklist(cb));}
    function renderCards(){
      const items=cardFiltered(),newTile=canWrite()&&state.cardScope==='active'?`<button class="new-card-tile" id="newCardTile" aria-label="New card">${icon('plus')}</button>`:'';
      $('#cardsView').innerHTML=newTile+items.map(cardTile).join('')||'<div class="empty">No cards match this view.</div>';
      $('#newCardTile')?.addEventListener('click',()=>openCard());
      $$('.card-open').forEach(b=>b.onclick=()=>openCard(b.closest('[data-card-id]').dataset.cardId));
      $$('.card-delete').forEach(b=>b.onclick=()=>deleteCard(b.closest('[data-card-id]').dataset.cardId));
      $$('.card-ics').forEach(b=>b.onclick=()=>{const c=state.cards.find(x=>x.id===b.closest('[data-card-id]').dataset.cardId);downloadResource(b.dataset.url,`${(c?.title||'event').replace(/[^a-z0-9_-]+/gi,'-')}.ics`);});
      $$('.status-popover [data-card-status]').forEach(b=>b.onclick=e=>{e.preventDefault();e.stopPropagation();const card=b.closest('[data-card-id]');quickSetCardStatus(card.dataset.cardId,b.dataset.cardStatus);});
      bindChecklistControls($('#cardsView')); return renderMdElements($('#cardsView'));
    }
    async function quickSetCardStatus(id,status){
      const card=state.cards.find(c=>c.id===id);if(!card||card.status===status||!canEditCard(card))return;
      try{const updated=await api(`/api/projects/${pid}/cards/${id}`,{method:'PATCH',body:{expected_version:card.version,status}});state.cards=state.cards.map(x=>x.id===id?updated:x);renderCards();renderOverview();refreshActivity();toast(`Status changed to ${statusLabel(status)}`);}catch(err){if(err.status===409)openConflict(err,card);else toast(err.message,true);}
    }
    async function toggleInlineChecklist(cb){
      const card=state.cards.find(c=>c.id===cb.dataset.checkCard);if(!card||!canEditCard(card)){cb.checked=!cb.checked;return;}
      const idx=Number(cb.dataset.checkLine);
      if(cb.dataset.checkPending==='1'){const current=(card.content||'').split('\n')[idx]?.match(/^(\s*(?:[-*]\s+)?\[)( |x|X)(\]\s+)(.*)$/);if(current)cb.checked=current[2].toLowerCase()==='x';return;}
      const scrollPos=checklistScrollState(cb),parts=(card.content||'').split('\n');const m=parts[idx]?.match(/^(\s*(?:[-*]\s+)?\[)( |x|X)(\]\s+)(.*)$/);if(!m)return;
      const previousChecked=m[2].toLowerCase()==='x',nextChecked=cb.checked,baseVersion=card.version,previousContent=card.content||'';
      parts[idx]=m[1]+(nextChecked?'x':' ')+m[3]+m[4];const nextContent=parts.join('\n');
      state.cards=state.cards.map(x=>x.id===card.id?{...x,content:nextContent}:x);setChecklistDom(card.id,idx,nextChecked,{pending:true});
      try{const updated=await api(`/api/projects/${pid}/cards/${card.id}`,{method:'PATCH',body:{expected_version:baseVersion,content:nextContent}});state.cards=state.cards.map(x=>x.id===card.id?updated:x);setChecklistDom(card.id,idx,nextChecked,{pending:false});setCardVersionDom(card.id,updated.version);refreshActivity();toast(nextChecked?'Checklist item completed':'Checklist item reopened');}
      catch(err){state.cards=state.cards.map(x=>x.id===card.id?{...card,content:previousContent}:x);setChecklistDom(card.id,idx,previousChecked,{pending:false});restoreChecklistScroll(scrollPos);if(err.status===409)openConflict(err,card);else toast(err.message,true);}
    }
    function statusOptions(type,current){const vals=type==='event'?[['scheduled','Scheduled'],['done','Done'],['archived','Archived']]:[['todo','Pending'],['doing','In Progress'],['done','Done'],['archived','Archived']];const cur=current==='happened'?'done':current;return vals.map(([v,l])=>`<option value="${v}" ${cur===v?'selected':''}>${l}</option>`).join('');}
    function cardFormHtml(c={}){
      const type=c.type||'task',existing=Boolean(c.id),editable=!existing?canWrite():canEditCard(c),access=c.edit_access||'public',visibility=c.visibility||'everyone';
      const people=state.people.filter(p=>p.role!=='viewer').map(p=>({value:p.id,label:p.display_name}));
      return `${dialogHeader('CARD',type==='event'?'Event':'Task')}<form id="cardForm" class="form-stack"><div class="card-owner-line">${existing?`Created by <strong>${esc(personName(c.created_by))}</strong> · ${access==='private'?'Creator editing':'Shared editing'} · ${visibility==='private'?'Only me':'Everyone'}`:'New cards are visible to everyone in the project by default.'}</div><div class="type-switch"><button type="button" data-card-type="task" class="${type==='task'?'active':''}">Task</button><button type="button" data-card-type="event" class="${type==='event'?'active':''}">Event</button></div><input type="hidden" name="type" value="${type}"><label>Title<input name="title" required value="${esc(c.title||'')}"></label><div class="two-col"><label>Status<select name="status">${statusOptions(type,c.status||'todo')}</select></label><label>Edit access<select name="edit_access"><option value="public" ${access==='public'?'selected':''}>Shared — Owners & Members may edit</option><option value="private" ${access==='private'?'selected':''}>Creator only — only the creator may edit</option></select></label></div><label>Visibility<select name="visibility"><option value="everyone" ${visibility==='everyone'?'selected':''}>Everyone — all project members can see</option><option value="private" ${visibility==='private'?'selected':''}>Only me — hidden from other project members</option></select><span class="field-help">Visibility controls who can see this card. Edit access is a separate setting.</span></label><div class="two-col"><label class="event-only" ${type==='event'?'':'hidden'}>Start<input name="start" type="datetime-local" value="${esc((c.start||'').replace('Z','').slice(0,16))}"></label><label class="event-only" ${type==='event'?'':'hidden'}>End <span class="optional">Optional</span><input name="end" type="datetime-local" value="${esc((c.end||'').replace('Z','').slice(0,16))}"></label></div><label>Assignees${multiCheckHtml('assignees',people,c.assignees||[])}</label><label>Tags${tagEditorHtml('tags',c.tags||[])}</label><label>Content <span class="optional">Markdown supported · use [ ] or - [ ] for checklist items</span><textarea name="content" rows="9">${esc(c.content||'')}</textarea></label>${c.id&&c.type==='event'&&c.start?`<button type="button" class="btn secondary" id="cardIcsBtn">${icon('calendar')} Add to my calendar</button>`:''}${existing?'<section class="card-activity-panel"><div class="modal-section-title">Card activity</div><div id="cardActivityList" class="card-activity-list"><div class="muted">Loading…</div></div></section>':''}<div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>${editable?'Cancel':'Close'}</button>${editable?'<button class="btn" type="submit">Save</button>':''}</div></form>`;
    }
    async function loadCardActivity(id){
      const el=$('#cardActivityList');if(!el)return;
      try{const items=await api(`/api/projects/${pid}/cards/${id}/activity`);el.innerHTML=items.length?items.map(a=>`<div class="card-activity-row"><time>${esc(fmtDate(a.ts))}</time><div>${esc(activityDetail(a))}</div></div>`).join(''):'<div class="muted">No activity yet.</div>';}catch(err){el.innerHTML=`<div class="muted">${esc(err.message)}</div>`;}
    }
    function openCard(id=null){
      const c=id?state.cards.find(x=>x.id===id):{type:'task',status:'todo',assignees:[],tags:[],edit_access:'public',visibility:'everyone'};if(!c)return;
      const editable=!c.id?canWrite():canEditCard(c);openDialog(cardFormHtml(c));const form=$('#cardForm');initTagEditors(form);initMultiChecks(form);
      if(!editable){$$('input,textarea,select',form).forEach(el=>el.disabled=true);$$('[data-card-type]',form).forEach(el=>el.disabled=true);$$('.multi-done',form).forEach(el=>el.disabled=true);}
      else if(c.id){
        if(!canChangeCardAccess(c)) form.edit_access.disabled=true;
        if(!canChangeCardVisibility(c)) form.visibility.disabled=true;
      }
      $$('[data-card-type]',form).forEach(b=>b.onclick=()=>{if(!editable)return;const type=b.dataset.cardType;$$('[data-card-type]',form).forEach(x=>x.classList.toggle('active',x===b));form.type.value=type;$$('.event-only',form).forEach(x=>x.hidden=type!=='event');form.status.innerHTML=statusOptions(type,type==='event'?'scheduled':'todo');$('.modal-head h2').textContent=type==='event'?'Event':'Task';});
      if($('#cardIcsBtn'))$('#cardIcsBtn').onclick=()=>downloadResource(`/api/projects/${pid}/cards/${c.id}/ics`,`${c.title.replace(/[^a-z0-9_-]+/gi,'-')}.ics`);
      if(c.id)loadCardActivity(c.id);
      if(editable)form.onsubmit=async e=>{e.preventDefault();const fd=new FormData(form),body={title:fd.get('title'),type:fd.get('type'),status:fd.get('status'),start:fd.get('type')==='event'&&fd.get('start')?new Date(fd.get('start')).toISOString():null,end:fd.get('type')==='event'&&fd.get('end')?new Date(fd.get('end')).toISOString():null,assignees:multiValues(form,'assignees'),tags:tagsFromForm(form),content:fd.get('content')||'',edit_access:c.id&&!canChangeCardAccess(c)?(c.edit_access||'public'):(fd.get('edit_access')||'public'),visibility:c.id&&!canChangeCardVisibility(c)?(c.visibility||'everyone'):(fd.get('visibility')||'everyone')};try{if(c.id){body.expected_version=c.version;const updated=await api(`/api/projects/${pid}/cards/${c.id}`,{method:'PATCH',body});state.cards=state.cards.map(x=>x.id===c.id?updated:x);}else{state.cards.unshift(await api(`/api/projects/${pid}/cards`,{method:'POST',body}));}closeDialog();renderCards();renderOverview();populateFilters();refreshActivity();toast('Card saved');}catch(err){if(err.status===409)openConflict(err,c);else toast(err.message,true);}};
    }
    async function deleteCard(id){const c=state.cards.find(x=>x.id===id);if(!c||!canDeleteCard(c))return;if(!confirm(`Permanently delete “${c.title}”? Only the original creator can do this.`))return;try{await api(`/api/projects/${pid}/cards/${id}`,{method:'DELETE'});state.cards=state.cards.filter(x=>x.id!==id);renderCards();renderOverview();refreshActivity();toast('Card deleted');}catch(err){toast(err.message,true);}}
    function openConflict(err,c){const current=err.data.current||{};openDialog(`${dialogHeader('CONFLICT','This card changed while you were editing')}<div class="banner warn">Cocklebur will not silently merge or overwrite a newer version.</div><section class="panel"><strong>Latest</strong><p>${esc(current.title||'')}</p><span class="microcopy">version ${current.version||'?'}</span></section><div class="modal-actions"><button class="btn" id="reloadConflict">Load latest</button><button class="btn secondary" data-close-dialog>Cancel</button></div>`);$('#reloadConflict').onclick=()=>openCard(current.id||c.id);}

    async function renderMdElements(root=document){for(const el of $$('[data-md]',root)){try{const r=await api('/api/render-markdown',{method:'POST',body:{text:el.dataset.md||''}});el.innerHTML=r.html;}catch{el.innerHTML=nl2br(el.dataset.md||'');}}}
    function announcementBubble(a){return `<article class="announcement-item ${a.pinned?'pinned':''}" data-ann-id="${a.id}"><time class="announcement-date">${esc(fmtShortDate(a.ts))}</time><div class="announcement-bubble"><div class="announcement-bubble-head"><div class="announcement-main"><div class="announcement-title-row"><strong>${a.pinned?'Pinned · ':''}${esc(a.title||'Announcement')}</strong></div>${(a.tags||[]).length?`<div class="announcement-tag-row">${a.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>`:''}</div><div class="announcement-actions">${canWrite()&&(isOwner()||a.actor_id===state.me.id)?`<button class="mini-icon-btn edit-ann" aria-label="Edit">${icon('edit')}</button><button class="mini-icon-btn danger delete-ann" aria-label="Delete">${icon('trash')}</button>`:''}${isOwner()?`<button class="mini-icon-btn pin-ann" aria-label="${a.pinned?'Unpin':'Pin'}">${icon('pin')}</button>`:''}</div></div><div class="announcement-body"><div data-md="${esc(a.body)}">${nl2br(a.body)}</div><div class="microcopy" style="margin-top:10px">${esc(personName(a.actor_id))}${a.edited_at?' · edited':''}</div></div></div></article>`;}
    function renderAnnouncements(){const list=$('#announcementsList'),add=$('#newAnnouncementBtn');$$('.announcement-item',list).forEach(x=>x.remove());[...state.announcements.filter(a=>!a.deleted)].reverse().forEach(a=>add.insertAdjacentHTML('afterend',announcementBubble(a))); $$('.announcement-bubble-head',list).forEach(h=>h.onclick=e=>{if(e.target.closest('button'))return;h.closest('.announcement-item').classList.toggle('open');}); $$('.edit-ann',list).forEach(b=>b.onclick=()=>editAnnouncementInline(b.closest('[data-ann-id]').dataset.annId)); $$('.delete-ann',list).forEach(b=>b.onclick=()=>deleteAnnouncement(b.closest('[data-ann-id]').dataset.annId)); $$('.pin-ann',list).forEach(b=>b.onclick=()=>pinAnnouncement(b.closest('[data-ann-id]').dataset.annId)); renderMdElements(list);}
    function newAnnouncementInline(){if($('#newAnnouncementEditor'))return;const add=$('#newAnnouncementBtn');add.insertAdjacentHTML('afterend',`<article class="announcement-item" id="newAnnouncementEditor"><time class="announcement-date">Today</time><div class="announcement-bubble"><form class="announcement-edit" id="announcementInlineForm"><label>Title<input name="title" required autofocus></label><label>Tags${tagEditorHtml('tags',[])}</label><label>Announcement<textarea name="body" rows="6" required></textarea></label><div class="done-row"><button type="button" class="btn secondary" id="cancelNewAnn">Cancel</button><button class="btn done-btn">Done</button></div></form></div></article>`);const form=$('#announcementInlineForm');initTagEditors(form);$('#cancelNewAnn').onclick=()=>$('#newAnnouncementEditor').remove();form.onsubmit=async e=>{e.preventDefault();const f=new FormData(form);try{state.announcements=await (async()=>{await api(`/api/projects/${pid}/announcements`,{method:'POST',body:{title:f.get('title'),body:f.get('body'),tags:tagsFromForm(form)}});return api(`/api/projects/${pid}/announcements`);})();renderAnnouncements();renderOverview();toast('Announcement posted');}catch(err){toast(err.message,true);}};}
    function editAnnouncementInline(id){const a=state.announcements.find(x=>x.id===id),item=$(`[data-ann-id="${id}"]`);if(!a||!item)return;item.querySelector('.announcement-bubble').innerHTML=`<form class="announcement-edit" id="editAnn_${id}"><label>Title<input name="title" required value="${esc(a.title||'')}"></label><label>Tags${tagEditorHtml('tags',a.tags||[])}</label><label>Announcement<textarea name="body" rows="7" required>${esc(a.body||'')}</textarea></label><div class="done-row"><button class="btn done-btn">Done</button></div></form>`;const form=$(`#editAnn_${id}`);initTagEditors(form);form.querySelector('input[name=title]').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();form.requestSubmit();}});form.onsubmit=async e=>{e.preventDefault();const f=new FormData(form);try{await api(`/api/projects/${pid}/announcements/${id}`,{method:'PATCH',body:{title:f.get('title'),body:f.get('body'),tags:tagsFromForm(form)}});state.announcements=await api(`/api/projects/${pid}/announcements`);renderAnnouncements();renderOverview();toast('Announcement updated');}catch(err){toast(err.message,true);}};}
    async function deleteAnnouncement(id){if(!confirm('Delete this announcement?'))return;try{await api(`/api/projects/${pid}/announcements/${id}`,{method:'DELETE'});state.announcements=await api(`/api/projects/${pid}/announcements`);renderAnnouncements();renderOverview();toast('Announcement deleted');}catch(err){toast(err.message,true);}}
    async function pinAnnouncement(id){const a=state.announcements.find(x=>x.id===id);try{await api(`/api/projects/${pid}/announcements/${id}/pin`,{method:'POST',body:{pinned:!a.pinned}});state.announcements=await api(`/api/projects/${pid}/announcements`);renderAnnouncements();renderOverview();}catch(err){toast(err.message,true);}}

    function channelVisibleCount(ch){return state.people.filter(p=>ch.visibility==='everyone'||p.role==='owner'||(ch.visibility==='roles'&&(ch.roles||[]).includes(p.role))||(ch.visibility==='members'&&(ch.members||[]).includes(p.id))).length;}
    function renderChannels(){if(!state.channels.find(c=>c.id===state.channel))state.channel=state.channels[0]?.id||'general';$('#channelList').innerHTML=state.channels.map(c=>`<button class="channel-item ${c.id===state.channel?'active':''}" data-channel-id="${c.id}"><span># ${esc(c.name)}</span><span class="count-badge">${channelVisibleCount(c)}</span></button>`).join('');$$('[data-channel-id]').forEach(b=>b.onclick=()=>{state.channel=b.dataset.channelId;state.pendingThread=null;renderChannels();loadThreads();});const ch=state.channels.find(c=>c.id===state.channel);$('#currentChannelName').textContent=ch?`# ${ch.name}`:'# discussion';$('#currentChannelCount').textContent=ch?`${channelVisibleCount(ch)} members`:'';loadThreads();}
    async function loadThreads(){const el=$('#threadsList');if(!state.channel){el.innerHTML='<div class="empty">No channels.</div>';return;}try{state.threads=await api(`/api/projects/${pid}/channels/${state.channel}/threads`);renderThreads();}catch(err){el.innerHTML=`<div class="empty">${esc(err.message)}</div>`;}}
    function renderThreads(){
      const q=($('#discussionSearch').value||'').toLowerCase().trim(),authors=$$('#discussionAuthorChecks input:checked').map(x=>x.value),tags=$$('#discussionTagFilter input:checked').map(x=>x.value);const threads=state.threads.filter(t=>(!q||`${t.root.title} ${t.root.body}`.toLowerCase().includes(q))&&(!authors.length||authors.includes(t.root.actor_id))&&(!tags.length||tags.some(tag=>(t.root.tags||[]).includes(tag))));
      $('#threadsList').innerHTML=threads.length?threads.map(t=>`<article class="thread-card ${state.pendingThread===t.id?'open':''}" data-thread-id="${t.id}"><div class="thread-summary"><div class="thread-summary-main"><h3>${esc(t.root.title||'Discussion')}</h3><p>${esc(contentSummary(t.root.body))}</p></div><span class="count-badge">${t.reply_count||0}</span></div><div class="thread-body"><div class="messages"><div class="muted">Loading…</div></div>${canWrite()?`<form class="reply-form"><input name="body" required placeholder="Reply to this thread"><button class="btn compact">Reply</button></form>`:''}</div></article>`).join(''):'<div class="empty">No discussions match this view.</div>';
      $$('.thread-summary').forEach(s=>s.onclick=()=>{const card=s.closest('.thread-card');card.classList.toggle('open');if(card.classList.contains('open'))loadThreadMessages(card);});$$('.reply-form').forEach(f=>f.onsubmit=async e=>{e.preventDefault();const card=f.closest('[data-thread-id]'),tid=card.dataset.threadId,body=new FormData(f).get('body');try{await api(`/api/projects/${pid}/channels/${state.channel}/threads/${tid}/replies`,{method:'POST',body:{body}});f.reset();const t=state.threads.find(x=>x.id===tid);if(t){t.reply_count=(t.reply_count||0)+1;$('.thread-summary .count-badge',card).textContent=t.reply_count;}card.classList.add('open');await loadThreadMessages(card);await loadOverviewThreads();renderOverview();toast('Reply posted');}catch(err){toast(err.message,true);}});if(state.pendingThread){const card=$(`[data-thread-id="${state.pendingThread}"]`);if(card){card.classList.add('open');loadThreadMessages(card);card.scrollIntoView({behavior:'smooth',block:'center'});}state.pendingThread=null;}
    }
    async function loadThreadMessages(card){const tid=card.dataset.threadId;try{const msgs=await api(`/api/projects/${pid}/channels/${state.channel}/threads/${tid}`);$('.messages',card).innerHTML=msgs.map((m,i)=>`<div class="message-row ${m.deleted?'deleted':''}" data-msg-id="${m.id}"><div class="message-meta"><span>${esc(personName(m.actor_id))} · ${esc(fmtDate(m.ts))}${m.edited_at?' · edited':''}</span>${!m.deleted&&(isOwner()||m.actor_id===state.me.id)?`<span class="message-actions"><button class="text-link edit-msg">Edit</button><button class="text-link danger-text delete-msg">Delete</button></span>`:''}</div>${i===0&&m.title?`<strong>${esc(m.title)}</strong>`:''}<div class="message-content" ${m.deleted?'':`data-md="${esc(m.body)}"`}>${m.deleted?'Message deleted':nl2br(m.body)}</div></div>`).join('');renderMdElements($('.messages',card));$$('.edit-msg',card).forEach(b=>b.onclick=()=>editThreadMessage(tid,b.closest('[data-msg-id]').dataset.msgId));$$('.delete-msg',card).forEach(b=>b.onclick=()=>deleteThreadMessage(tid,b.closest('[data-msg-id]').dataset.msgId));}catch(err){toast(err.message,true);}}
    async function editThreadMessage(tid,msgid){try{const msgs=await api(`/api/projects/${pid}/channels/${state.channel}/threads/${tid}`),m=msgs.find(x=>x.id===msgid);if(!m)return;openDialog(`${dialogHeader('DISCUSSION','Edit message')}<form id="editMessageForm" class="form-stack"><label>Message<textarea name="body" rows="8" required>${esc(m.body||'')}</textarea></label><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">Save</button></div></form>`);$('#editMessageForm').onsubmit=async e=>{e.preventDefault();try{await api(`/api/projects/${pid}/channels/${state.channel}/threads/${tid}/messages/${msgid}`,{method:'PATCH',body:{body:new FormData(e.currentTarget).get('body')}});closeDialog();await loadThreads();await loadOverviewThreads();renderOverview();toast('Message updated');}catch(err){toast(err.message,true);}};}catch(err){toast(err.message,true);}}
    async function deleteThreadMessage(tid,msgid){if(!confirm('Delete this message?'))return;try{await api(`/api/projects/${pid}/channels/${state.channel}/threads/${tid}/messages/${msgid}`,{method:'DELETE'});await loadThreads();await loadOverviewThreads();renderOverview();toast('Message deleted');}catch(err){toast(err.message,true);}}
    function threadModal(){openDialog(`${dialogHeader('DISCUSSION','New discussion')}<form id="threadForm" class="form-stack"><label>Title<input name="title" required></label><label>Message<textarea name="body" rows="8" required></textarea></label><label>Tags${tagEditorHtml('tags',[])}</label><div class="modal-actions"><button class="btn secondary" type="button" data-close-dialog>Cancel</button><button class="btn">Post</button></div></form>`);const form=$('#threadForm');initTagEditors(form);form.onsubmit=async e=>{e.preventDefault();const f=new FormData(form);try{await api(`/api/projects/${pid}/channels/${state.channel}/threads`,{method:'POST',body:{title:f.get('title'),body:f.get('body'),tags:tagsFromForm(form)}});closeDialog();await loadThreads();await loadOverviewThreads();populateFilters();renderOverview();toast('Discussion posted');}catch(err){toast(err.message,true);}};}
    function channelForm(ch=null){const roles=[{value:'owner',label:'Owner'},{value:'member',label:'Member'},{value:'viewer',label:'Viewer'}],people=state.people.map(p=>({value:p.id,label:`${p.display_name} · ${p.role}`}));return `${dialogHeader('CHANNEL',ch?'Manage channel':'New channel')}<form id="channelForm" class="form-stack"><label>Name<input name="name" required value="${esc(ch?.name||'')}"></label><label>Visibility<select name="visibility"><option value="everyone" ${ch?.visibility==='everyone'?'selected':''}>Everyone</option><option value="roles" ${ch?.visibility==='roles'?'selected':''}>Specific roles</option><option value="members" ${ch?.visibility==='members'?'selected':''}>Specific people</option></select></label><div class="visibility-options roles-options"><label>Roles${multiCheckHtml('roles',roles,ch?.roles||[])}</label></div><div class="visibility-options members-options"><label>People${multiCheckHtml('members',people,ch?.members||[])}</label></div><div class="modal-actions">${ch&&ch.id!=='general'?'<button type="button" class="btn danger" id="deleteChannelBtn">Delete channel</button>':''}<button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">${ch?'Save':'Create'}</button></div></form>`;}
    function openChannelModal(ch=null){openDialog(channelForm(ch));const form=$('#channelForm');initMultiChecks(form);const vis=()=>{$('.roles-options',form).hidden=form.visibility.value!=='roles';$('.members-options',form).hidden=form.visibility.value!=='members';};form.visibility.onchange=vis;vis();form.onsubmit=async e=>{e.preventDefault();const f=new FormData(form),payload={name:f.get('name'),visibility:f.get('visibility'),roles:multiValues(form,'roles'),members:multiValues(form,'members')};try{if(ch){const updated=await api(`/api/projects/${pid}/channels/${ch.id}`,{method:'PATCH',body:payload});state.channels=state.channels.map(x=>x.id===ch.id?updated:x);}else{const created=await api(`/api/projects/${pid}/channels`,{method:'POST',body:payload});state.channels.push(created);state.channel=created.id;}closeDialog();renderChannels();await loadOverviewThreads();renderOverview();toast(ch?'Channel updated':'Channel created');}catch(err){toast(err.message,true);}};if(ch&&ch.id!=='general')$('#deleteChannelBtn').onclick=async()=>{if(!confirm(`Delete #${ch.name} and all its threads?`))return;try{await api(`/api/projects/${pid}/channels/${ch.id}`,{method:'DELETE'});state.channels=state.channels.filter(x=>x.id!==ch.id);state.channel='general';closeDialog();renderChannels();await loadOverviewThreads();renderOverview();}catch(err){toast(err.message,true);}};}

    function fileExt(name=''){return (name.split('.').pop()||'file').toLowerCase();}
    function renderFiles(){
      const q=($('#fileSearch').value||'').toLowerCase().trim(),uploaders=$$('#fileUploaderChecks input:checked').map(x=>x.value),types=$$('#fileTypeChecks input:checked').map(x=>x.value);const items=state.files.filter(f=>(!q||`${f.name} ${f.description||''}`.toLowerCase().includes(q))&&(!uploaders.length||uploaders.includes(f.uploader_id))&&(!types.length||types.includes(fileExt(f.name))));
      $('#filesList').innerHTML=items.length?items.map(f=>`<div class="file-row" data-file-id="${f.id}">${canWrite()?`<input class="file-check" type="checkbox" ${state.selectedFiles.has(f.id)?'checked':''}>`:'<span></span>'}<div class="file-name-block"><div class="file-name">${esc(f.name)}</div><div class="file-desc">${esc(f.description||'No description')}</div></div><span>${esc(fmtShortDate(f.uploaded_at))}</span><span>${esc(personName(f.uploader_id))}</span><span>${fmtBytes(f.size)}</span><button class="mini-icon-btn file-download-icon file-download" data-url="/api/projects/${pid}/files/${f.id}/download" data-name="${esc(f.name)}" aria-label="Download">${icon('download')}</button></div>`).join(''):'<div class="empty">No files match this view.</div>';
      $$('.file-download').forEach(b=>b.onclick=()=>downloadResource(b.dataset.url,b.dataset.name));$$('.file-check').forEach(cb=>cb.onchange=()=>{const id=cb.closest('[data-file-id]').dataset.fileId;cb.checked?state.selectedFiles.add(id):state.selectedFiles.delete(id);renderBulkFiles();});renderBulkFiles();
    }
    function renderBulkFiles(){const bar=$('#fileBulkBar');bar.hidden=!state.selectedFiles.size;$('#fileSelectedCount').textContent=`${state.selectedFiles.size} selected`;}
    async function refreshUploadLimits(){
      try{state.uploadLimits=await api(`/api/projects/${pid}/upload-limits`);return state.uploadLimits;}catch(err){toast(`Could not read upload limits: ${err.message}`,true);return state.uploadLimits;}
    }
    async function openUploadModal(){
      const limits=await refreshUploadLimits();
      const cardItems=state.cards.map(c=>({value:c.id,label:c.title}));
      const limitHint=limits
        ? `Per-file limit ${fmtBytes(limits.max_upload_bytes)} · ${fmtBytes(limits.remaining_bytes)} remaining of ${fmtBytes(limits.quota_bytes)}`
        : 'Upload limits will still be enforced by the app.';
      openDialog(`${dialogHeader('FILES','Upload files')}<form id="uploadForm" class="form-stack"><div class="drop-zone" id="dropZone"><div>${icon('plus')}</div><strong>Drop files here</strong><span class="muted">or</span><button type="button" class="btn secondary" id="pickFilesBtn">Choose files</button><input id="modalFilePicker" type="file" multiple hidden><div id="selectedUploadFiles" class="upload-file-summary"></div></div><p class="microcopy" id="uploadLimitHint">${esc(limitHint)}</p><div id="uploadValidationError" class="inline-error" role="alert" aria-live="assertive" tabindex="-1" hidden></div><label>Description <span class="optional">Optional; applies to all selected files</span><input name="description"></label><label>Link to Cards <span class="optional">Optional · select one or more</span>${multiCheckHtml('linked_card_ids',cardItems,[])}</label><div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn" id="uploadConfirm" disabled>Upload</button></div></form>`);
      const form=$('#uploadForm'),picker=$('#modalFilePicker'),drop=$('#dropZone'),errorEl=$('#uploadValidationError'),summaryEl=$('#selectedUploadFiles');
      initMultiChecks(form);
      let files=[],selectionErrors=[];
      const setSelectionError=(messages=[])=>{selectionErrors=[...messages];};
      const validate=()=>{
        const errors=[...selectionErrors];
        const maxBytes=Number(state.uploadLimits?.max_upload_bytes||0);
        const remaining=state.uploadLimits?.remaining_bytes;
        const packageFiles=files.filter(f=>/\.app$/i.test(f.name||''));
        if(packageFiles.length){
          const names=packageFiles.slice(0,3).map(f=>f.name).join(', ');
          errors.push(`${names}${packageFiles.length>3?` and ${packageFiles.length-3} more`:''} is a macOS app bundle, not a single uploadable file. Compress it to a .zip first.`);
        }
        const oversized=maxBytes?files.filter(f=>f.size>maxBytes):[];
        if(oversized.length){
          const names=oversized.slice(0,3).map(f=>`${f.name} (${fmtBytes(f.size)})`).join(', ');
          errors.push(`${names}${oversized.length>3?` and ${oversized.length-3} more`:''} exceed${oversized.length===1?'s':''} the ${fmtBytes(maxBytes)} per-file limit.`);
        }
        const batchBytes=files.reduce((n,f)=>n+Number(f.size||0),0);
        if(remaining!=null && batchBytes>Number(remaining)){
          errors.push(`Selected files total ${fmtBytes(batchBytes)}, but this project has only ${fmtBytes(remaining)} remaining.`);
        }
        errorEl.hidden=!errors.length; errorEl.textContent=errors.join(' ');
        drop.classList.toggle('invalid',Boolean(errors.length));
        if(errors.length){requestAnimationFrame(()=>errorEl.scrollIntoView({block:'nearest'}));}
        $('#uploadConfirm').disabled=!files.length||Boolean(errors.length);
        return !errors.length;
      };
      const sync=()=>{
        summaryEl.innerHTML=files.length?files.map(f=>`<div><strong>${esc(f.name)}</strong><span>${fmtBytes(f.size)}</span></div>`).join(''):'<div class="upload-empty-note">No file selected. Folders and macOS .app bundles must be compressed before upload.</div>';
        validate();
      };
      $('#pickFilesBtn').onclick=()=>{setSelectionError([]);picker.click();};
      picker.onchange=()=>{
        files=[...picker.files];
        setSelectionError(!files.length?['No uploadable file was selected. Folders and macOS .app bundles cannot be uploaded directly; compress them to a .zip first.']:[]);
        sync();
      };
      ['dragenter','dragover'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('dragging');}));
      ['dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('dragging');if(ev==='drop'){
        const items=[...(e.dataTransfer?.items||[])];
        const hasDirectory=items.some(item=>{try{return item.webkitGetAsEntry?.()?.isDirectory===true;}catch(_){return false;}});
        files=[...(e.dataTransfer?.files||[])];
        const errs=[];
        if(hasDirectory)errs.push('Folders and macOS app bundles cannot be uploaded directly. Compress them to a .zip first.');
        if(!files.length&&!hasDirectory)errs.push('No uploadable file was found in that drop.');
        setSelectionError(errs);sync();
      }}));
      sync();
      form.onsubmit=async e=>{
        e.preventDefault();
        if(!validate())return;
        const meta=new FormData(form),linked=multiValues(form,'linked_card_ids');
        const submit=$('#uploadConfirm'); submit.disabled=true; submit.textContent='Uploading…';
        try{
          for(const file of files){
            const fd=new FormData();fd.append('file',file);fd.append('description',meta.get('description')||'');linked.forEach(id=>fd.append('linked_card_ids',id));
            state.files.push(await api(`/api/projects/${pid}/files`,{method:'POST',body:fd}));
          }
          await refreshUploadLimits();
          closeDialog();populateFilters();renderFiles();renderOverview();toast(`${files.length} file${files.length===1?'':'s'} uploaded`);
        }catch(err){
          await refreshUploadLimits();
          errorEl.hidden=false; errorEl.textContent=err.message||'Upload failed';
          submit.textContent='Upload'; validate();
        }
      };
    }
    async function bulkDeleteFiles(){if(!state.selectedFiles.size||!confirm(`Permanently delete ${state.selectedFiles.size} selected file(s)?`))return;try{for(const id of [...state.selectedFiles])await api(`/api/projects/${pid}/files/${id}`,{method:'DELETE'});state.files=state.files.filter(f=>!state.selectedFiles.has(f.id));state.selectedFiles.clear();populateFilters();renderFiles();renderOverview();toast('Selected files deleted');}catch(err){toast(err.message,true);}}

    function renderPeople(){
      const visiblePeople=isLocalProject()?state.people.filter(p=>p.id===state.me.id):state.people;
      $('#invitePanel').style.display=isLocalProject()?'none':'';
      $('#peopleList').innerHTML=visiblePeople.map(p=>{
        const self=p.id===state.me.id;
        const actions=[];
        if(self)actions.push('<button class="btn compact secondary edit-profile">Edit profile</button>');
        if(isOwner()&&!self&&!isLocalProject())actions.push('<button class="btn compact secondary person-settings">Settings</button>');
        return `<div class="person-row" data-person-id="${p.id}"><div class="people-name"><span class="person-avatar">${esc(initials(p.id))}</span><div><strong>${esc(p.display_name)}</strong><div class="file-desc">${self?'You · ':''}Joined ${esc(fmtShortDate(p.joined_at))}</div></div></div><span class="person-role">${esc(p.role)}</span><div class="person-actions">${actions.join('')}</div></div>`;
      }).join('');
      $$('.edit-profile').forEach(b=>b.onclick=()=>editMyProfile());
      $$('.person-settings').forEach(b=>b.onclick=()=>memberSettings(b.closest('[data-person-id]').dataset.personId));
    }
    function editMyProfile(){
      openDialog(`${dialogHeader('PROFILE','Your profile')}<form id="myProfileForm" class="form-stack"><label>Display name<input name="display_name" required maxlength="100" value="${esc(state.me.display_name||'')}"></label><label>Role<input value="${esc(state.me.role)}" disabled></label>${isOwner()?'<div class="recovery-box"><strong>Owner recovery</strong><p class="microcopy">Rotate your break-glass recovery code if you need a fresh copy. Rotating invalidates the previous code.</p><button type="button" class="btn secondary" id="rotateOwnerRecoveryBtn">Generate new Owner recovery code</button></div>':''}<div class="modal-actions"><button type="button" class="btn secondary" data-close-dialog>Cancel</button><button class="btn">Save name</button></div></form>`);
      $('#myProfileForm').onsubmit=async e=>{e.preventDefault();try{const updated=await api(`/api/projects/${pid}/me`,{method:'PATCH',body:{display_name:new FormData(e.currentTarget).get('display_name')}});state.me={...state.me,...updated};state.people=state.people.map(x=>x.id===state.me.id?{...x,...updated}:x);closeDialog();populateFilters();renderPeople();renderChannels();renderOverview();refreshActivity();toast('Display name updated');}catch(err){toast(err.message,true);}};
      $('#rotateOwnerRecoveryBtn')?.addEventListener('click',rotateOwnerRecovery);
    }
    async function rotateOwnerRecovery(){
      try{const r=await api(`/api/projects/${pid}/me/owner-recovery/rotate`,{method:'POST'});showRecoveryCodeDialog(r,()=>editMyProfile());}catch(err){toast(err.message,true);}
    }
    function memberSettings(id){
      const p=state.people.find(x=>x.id===id);if(!p||!isOwner())return;
      openDialog(`${dialogHeader('MEMBER',p.display_name)}<form id="memberSettingsForm" class="form-stack"><label>Role<select name="role"><option value="owner" ${p.role==='owner'?'selected':''}>Owner</option><option value="member" ${p.role==='member'?'selected':''}>Member</option><option value="viewer" ${p.role==='viewer'?'selected':''}>Viewer</option></select></label><p class="microcopy">Members can collaborate. Viewers are read-only. Only Owners can change roles.</p><div class="modal-actions"><button class="btn" type="submit">Update role</button><button type="button" class="btn danger" id="deleteMemberBtn">Delete</button><button type="button" class="btn secondary" data-close-dialog>Cancel</button></div><button type="button" class="text-link" id="recoveryMemberBtn">Generate one-time recovery link</button></form>`);
      $('#memberSettingsForm').onsubmit=async e=>{e.preventDefault();try{const updated=await api(`/api/projects/${pid}/people/${id}`,{method:'PATCH',body:{role:new FormData(e.currentTarget).get('role')}});state.people=state.people.map(x=>x.id===id?{...x,...updated}:x);closeDialog();populateFilters();renderPeople();renderChannels();refreshActivity();toast('Role updated');}catch(err){toast(err.message,true);}};
      $('#deleteMemberBtn').onclick=()=>removePerson(id);$('#recoveryMemberBtn').onclick=()=>makeRecovery(id);
    }
    async function makeRecovery(id){
      const target=state.people.find(p=>p.id===id);
      try{const r=await api(`/api/projects/${pid}/people/${id}/regenerate-link`,{method:'POST'});openDialog(`${dialogHeader('RECOVERY','One-time recovery link')}<p class="muted">This creates a one-time recovery link for ${esc(target?.display_name||'this member')}. Existing browser sessions stay signed in.</p><label>Recovery link<input id="recoveryValue" value="${esc(r.recovery_url)}" readonly></label><div class="modal-actions"><button class="btn" id="copyRecovery">Copy link</button><button class="btn secondary" data-close-dialog>Done</button></div>`);$('#copyRecovery').onclick=()=>copyText(r.recovery_url);refreshActivity();}catch(err){toast(err.message,true);}
    }
    async function removePerson(id){if(!confirm('Delete this member from the project?'))return;try{await api(`/api/projects/${pid}/people/${id}`,{method:'DELETE'});state.people=state.people.filter(p=>p.id!==id);closeDialog();populateFilters();renderPeople();renderChannels();renderOverview();refreshActivity();toast('Member deleted');}catch(err){toast(err.message,true);}}
    async function showInvite(){if(isLocalProject())return;try{const r=await api(`/api/projects/${pid}/invite/regenerate`,{method:'POST',body:{pin:null}});$('#invitePanel').innerHTML=`<div class="invite-box"><div><p class="eyebrow" style="color:#c7c8c0">ACTIVE INVITE</p><h3>Share this link or QR</h3><input id="inviteValue" value="${esc(r.invite_url)}" readonly><div class="header-actions" style="margin-top:8px"><button class="btn" id="copyInvite">Copy link</button><button class="btn secondary" id="newInvite">Regenerate</button></div><p class="microcopy" style="color:#c4c5bd">Joining exchanges the invite for a secure browser credential. If that browser credential is lost later, an Owner can generate a one-time recovery link.</p></div><img class="invite-qr" src="/api/projects/${pid}/invite/qr?token=${encodeURIComponent(r.token)}" alt="Invite QR"></div>`;$('#copyInvite').onclick=()=>copyText(r.invite_url);$('#newInvite').onclick=showInvite;refreshActivity();}catch(err){toast(err.message,true);}}

    function renderActivity(){$('#activityList').innerHTML=activityHtml(state.activity);}
    function fillSettings(){if(!state.project)return;const pf=$('#projectSettingsForm');if(pf){pf.name.value=state.project.name;pf.description.value=state.project.description||'';pf.expiry.value=(state.project.expiry||'').slice(0,10);}if(state.settings){const sf=$('#storageSettingsForm');sf.quota_mb.value=state.settings.quota_mb||1024;}const block=$('#storageLocationBlock'),path=$('#storagePathValue');if(block&&path&&state.project.storage_path){block.hidden=false;path.textContent=state.project.storage_path;}else if(block){block.hidden=true;}}
    async function doExport(){toast('Preparing a consistent snapshot…');const ok=await downloadResource(`/api/projects/${pid}/export`,`${state.project.name.replace(/[^a-z0-9_-]+/gi,'-')}.zip`);if(ok){toast('Project pack saved');try{state.project=await api(`/api/projects/${pid}`);}catch{}}}
    async function archiveProject(){if(!confirm('Archive this project? The data will remain on this instance.'))return;try{await api(`/api/projects/${pid}/archive`,{method:'POST'});toast('Project archived');setTimeout(()=>location.reload(),350);}catch(err){toast(err.message,true);}}
    async function closeWorkflow(){try{await api(`/api/projects/${pid}/close`,{method:'POST'});state.project=await api(`/api/projects/${pid}`);const s=await api(`/api/projects/${pid}/close/summary`);openDialog(`${dialogHeader('DELETE PROJECT','Review before permanent deletion')}<div class="settings-grid"><section class="panel"><strong>${s.cards}</strong><div class="muted">Cards</div></section><section class="panel"><strong>${s.files}</strong><div class="muted">Files</div></section><section class="panel"><strong>${s.members}</strong><div class="muted">Members</div></section><section class="panel"><strong>${s.threads}</strong><div class="muted">Threads</div></section></div><p>Project size: <strong>${fmtBytes(s.size_bytes)}</strong></p><div class="banner ${s.export_current?'':'warn'}">${s.export_current?'A current export exists.':'Export the current state before permanent deletion is enabled.'}</div><div class="modal-actions"><button class="btn" id="closeExport">Export now</button><button class="btn danger" id="deleteProject" ${s.export_current?'':'disabled'}>Delete permanently</button><button class="btn secondary" data-close-dialog>Cancel</button></div>`);$('#closeExport').onclick=async()=>{await doExport();closeDialog();closeWorkflow();};$('#deleteProject').onclick=async()=>{if(!confirm('Permanently delete this canonical project copy?'))return;try{await api(`/api/projects/${pid}?confirm=true`,{method:'DELETE'});forgetProject(pid);location.href='/';}catch(err){toast(err.message,true);}};}catch(err){toast(err.message,true);}}

    function bindActions(){
      $('#cardSearch').oninput=renderCards;$$('[data-card-scope]').forEach(b=>b.onclick=()=>{state.cardScope=b.dataset.cardScope;$$('[data-card-scope]').forEach(x=>x.classList.toggle('active',x===b));renderCards();});
      $('#newAnnouncementBtn').onclick=newAnnouncementInline;$('#newThreadBtn').onclick=threadModal;$('#newChannelBtn').onclick=()=>openChannelModal();$('#manageChannelBtn').onclick=()=>openChannelModal(state.channels.find(c=>c.id===state.channel));
      $('#discussionSearch').oninput=renderThreads;$('#fileSearch').oninput=renderFiles;$('#uploadFileBtn').onclick=openUploadModal;$('#bulkDeleteFiles').onclick=bulkDeleteFiles;
      $('#inviteBtn').onclick=showInvite;$('#exportTopBtn').onclick=doExport;$('#exportSettingsBtn').onclick=doExport;$('#archiveSettingsBtn').onclick=archiveProject;$('#closeProjectBtn').onclick=closeWorkflow;
      $('#copyStoragePath')?.addEventListener('click',()=>{if(state.project.storage_path)copyText(state.project.storage_path);});
      $('#projectSettingsForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{state.project=await api(`/api/projects/${pid}`,{method:'PATCH',body:{expected_version:state.project.version,name:f.get('name'),description:f.get('description'),expiry:f.get('expiry')||null}});renderOverview();fillSettings();toast('Project details saved');}catch(err){toast(err.message,true);}};
      $('#storageSettingsForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{state.settings=await api(`/api/projects/${pid}/settings`,{method:'PATCH',body:{expected_version:state.settings.version,quota_mb:Number(f.get('quota_mb')),pin:f.get('pin')||''}});toast('Storage & access settings saved');}catch(err){toast(err.message,true);}};
    }
  }

  const page=document.body.dataset.page; if(page==='home')initHome(); else if(page==='join')initJoin(); else if(page==='locked')initLocked(); else if(page==='project')initProject();
})();
