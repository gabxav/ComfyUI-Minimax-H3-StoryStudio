import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';

const TYPE = 'XavierH3Story';
const STUDIO_TYPE = 'XavierH3StoryStudio';
const STUDIO_NAME = 'ComfyUI-Minimax-H3-StoryStudio';
const uid = () => Array.from(crypto.getRandomValues(new Uint8Array(8)), b => b.toString(16).padStart(2,'0')).join('');
const css = document.createElement('style');
css.textContent = `
.xs-hidden {display:none !important;}
.xs-backdrop { position:fixed; inset:0; z-index:10000; background:#000b; display:grid; place-items:center; font:14px system-ui,sans-serif; color:#e9edf4; }
.xs { background:#171b23; border:1px solid #394252; border-radius:16px; width:min(1160px,96vw); height:min(880px,94vh); display:flex; flex-direction:column; box-shadow:0 24px 100px #0009; }
.xs * { box-sizing:border-box; }.xs button,.xs input,.xs select,.xs textarea { font:inherit; }
.xs header { padding:20px 24px; border-bottom:1px solid #333c49; display:flex; align-items:center; gap:16px; }.xs header h2 { font-size:20px; margin:0; }.xs .xs-sub { color:#a4b0c3; font-size:12px; margin-top:4px; }
.xs button { border:1px solid #44516a; background:#283345; color:#e9edf4; border-radius:7px; padding:9px 12px; cursor:pointer; }.xs button:hover { background:#354862; }.xs button:disabled { opacity:.5; cursor:wait; }.xs button.xs-primary { background:#287b70; border-color:#409d8e; }.xs button.xs-close { margin-left:auto; }.xs button.xs-danger { color:#ffb7ad; }
.xs-body { display:grid; grid-template-columns:220px 1fr; flex:1; min-height:0; }.xs aside { padding:18px 12px; border-right:1px solid #333c49; overflow:auto; }.xs main { padding:20px 24px; overflow:auto; min-width:0; }.xs .xs-scenes { display:grid; gap:8px; margin:14px 0; }.xs .xs-scene { text-align:left; display:flex; flex-direction:column; gap:5px; }.xs .xs-scene.active { border-color:#54c7ae; background:#24413f; }.xs .xs-scene small { color:#aebcd0; }
.xs label { display:block; margin:0 0 7px; font-weight:600; }.xs input:not([type=checkbox]),.xs select,.xs textarea { width:100%; color:#e9edf4; background:#0f141c; border:1px solid #3a485e; border-radius:7px; padding:10px; }.xs textarea { min-height:260px; resize:vertical; line-height:1.55; }.xs .xs-shared-prompt { min-height:130px; }.xs .xs-row { display:flex; gap:12px; align-items:center; margin-bottom:16px; }.xs .xs-grow { flex:1; }.xs .xs-duration { width:100px; }.xs .xs-check { display:flex; gap:8px; align-items:center; font-weight:400; }.xs details { border:1px solid #374356; border-radius:8px; padding:12px; margin-top:16px; }.xs summary { cursor:pointer; font-weight:600; }.xs details[open] summary { margin-bottom:14px; }.xs .xs-hint { color:#a4b0c3; line-height:1.5; font-size:12px; margin:8px 0 12px; }
.xs .xs-media { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }.xs .xs-media-col { background:#111821; border:1px solid #303e50; border-radius:8px; padding:10px; min-width:0; }.xs .xs-media-col h4 { margin:0 0 10px; }.xs .xs-asset { margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid #2d394a; }.xs .xs-asset img,.xs .xs-asset video { width:100%; height:80px; object-fit:contain; background:#080c12; }.xs .xs-asset audio { width:100%; height:30px; }.xs .xs-asset-name { word-break:break-all; font-size:11px; color:#b8c7da; margin:5px 0; }.xs .xs-asset button { padding:4px 7px; font-size:11px; }.xs .xs-times { display:flex; gap:5px; font-size:11px; margin-bottom:7px; }.xs .xs-times label { font-size:10px; font-weight:400; }.xs .xs-times input { padding:5px; }
.xs footer { border-top:1px solid #333c49; padding:14px 20px; }.xs .xs-actions { display:flex; gap:8px; flex-wrap:wrap; }.xs .xs-status { white-space:pre-wrap; max-height:80px; overflow:auto; color:#abc6ca; margin:10px 0 0; font-size:12px; }.xs .xs-preview { margin-top:16px; }.xs .xs-preview video { width:100%; max-height:270px; background:#090d14; }.xs .xs-preview a { color:#7bd4c8; }.xs .xs-save { color:#7bd4c8; font-size:11px; }
@media(max-width:720px){ .xs-body{grid-template-columns:155px 1fr}.xs main{padding:14px}.xs .xs-media{grid-template-columns:1fr}.xs header{padding:14px}.xs .xs-row{flex-wrap:wrap} }
`;
document.head.append(css);

function el(tag, attrs={}, children=[]) {
  const n=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs)) {
    if(k==='text') n.textContent=v;
    else if(k.startsWith('on')) n.addEventListener(k.slice(2),v);
    else if(k==='class') n.className=v;
    else if(k in n) n[k]=v;
    else n.setAttribute(k,v);
  }
  for(const child of children) n.append(child);
  return n;
}
const button=(text,action,cls='')=>el('button',{text,onclick:action,class:cls,type:'button'});
const widget=(node,name)=>node.widgets?.find(w=>w.name===name);
const urlFor=(path,type='input')=>{const parts=path.replaceAll('\\','/').split('/');const filename=parts.pop();return api.apiURL('/view?'+new URLSearchParams({filename,subfolder:parts.join('/'),type}));};
async function post(path,data){ const r=await api.fetchApi('/xavier-story/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}); const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d; }
function defaults(){return {version:1,project_id:'story_'+uid(),title:'My story',shared_prompt:'',references:{images:[],videos:[],audios:[]},context_frames:22,continue_audio:true,seed:101967611122254,ref_image_size:'max',scenes:[{title:'Scene 1',prompt:'',seconds:15,continue_previous:false,references:{images:[],videos:[],audios:[]}}]};}
function read(node){try{return JSON.parse(widget(node,'story_json').value)||defaults();}catch{return defaults();}}

function openEditor(node){
  let story=read(node), selected=Math.max(0,Math.min(story.scenes.length-1,(widget(node,'scene_index')?.value||1)-1));
  let state=null, polling=false, closed=false, timer;
  const backdrop=el('div',{class:'xs-backdrop'}), modal=el('section',{class:'xs',role:'dialog','aria-modal':'true','aria-label':'Story Director'});
  const status=el('div',{class:'xs-status',role:'status',text:'Ready. Edit your prompts and references.'});
  const list=el('div',{class:'xs-scenes'}), main=el('main'), saved=el('span',{class:'xs-save',text:'Saved to node'});
  function save(){widget(node,'story_json').value=JSON.stringify(story);widget(node,'scene_index').value=selected+1;node.title=node.type===STUDIO_TYPE?STUDIO_NAME:'Story · '+story.title;app.graph.setDirtyCanvas(true,true);saved.textContent='Saved to node';}
  function message(text,error=false){status.textContent=text;status.style.color=error?'#ffb7ad':'#abc6ca';}
  async function graph(){save();const p=await app.graphToPrompt();return {prompt:p.output,workflow:p.workflow,client_id:api.clientId};}
  async function refresh(){
    if(polling||closed)return;polling=true;
    try {const g=await graph();state=await post('status',{story,prompt:g.prompt});const j=state.job; if(j.status!=='idle')message(j.message||j.status,j.status==='failed');renderList();renderPreview();}
    catch(e){message(e.message,true);}finally{polling=false;}
  }
  async function run(mode){try{message('Validating the workflow…');await post('start',{...await graph(),mode,scene_index:selected+1});await refresh();}catch(e){message(e.message,true);}}
  function renderList(){
    list.replaceChildren();
    story.scenes.forEach((s,i)=>{
      const valid=state?.scenes?.[i];const b=button('',()=>{selected=i;save();render();},'xs-scene'+(selected===i?' active':''));
      b.append(el('strong',{text:`${String(i+1).padStart(2,'0')} · ${s.title}`}),el('small',{text:`${s.seconds}s · ${valid?'generated':'pending'}`}));list.append(b);
    });
  }
  async function upload(kind,refs){
    const input=el('input',{type:'file',multiple:true,accept:kind==='images'?'image/*':kind==='videos'?'video/*':'audio/*,video/*'});
    input.addEventListener('change',async()=>{try{
      const limits={images:9,videos:3,audios:3};
      for(const f of input.files){
        if(refs[kind].length>=limits[kind])throw Error(`Limit of ${limits[kind]} files in this group.`);
        message('Uploading '+f.name+'…');const form=new FormData();form.append('image',f);form.append('type','input');form.append('subfolder','story_director/'+story.project_id);
        const response=await api.fetchApi('/upload/image',{method:'POST',body:form});if(!response.ok)throw Error('Upload failed for '+f.name);
        const d=await response.json(),path=(d.subfolder?d.subfolder+'/':'')+d.name;
        refs[kind].push(kind==='images'?{path}:{path,start:0,seconds:15});
      }
      save();render();message('References added.');
    }catch(e){message(e.message,true);}});input.click();
  }
  function mediaPanel(refs,shared=false){
    const row=el('div',{class:'xs-media'});
    for(const [kind,label,tag] of [['images','Images','Picture'],['videos','Videos · motion','Video'],['audios','Audio · voice','Audio']]){
      refs[kind]??=[];const col=el('div',{class:'xs-media-col'},[el('h4',{text:label})]);
      refs[kind].forEach((m,i)=>{
        if(typeof m==='string')refs[kind][i]=m={path:m};
        const ordinal=i+1+(shared?0:(story.references[kind]?.length||0));
        const preview=kind==='images'?el('img',{src:urlFor(m.path),alt:'Reference '+ordinal}):el(kind==='videos'?'video':'audio',{src:urlFor(m.path),controls:true,preload:'metadata'});
        const asset=el('div',{class:'xs-asset'},[preview,el('div',{class:'xs-asset-name',text:`<${tag} ${ordinal}> · ${m.path.split('/').pop()}`})]);
        if(kind!=='images'){
          const times=el('div',{class:'xs-times'});
          for(const [key,name,min] of [['start','Start (s)',0],['seconds','Length (s)',.2]]){
            const field=el('input',{type:'number',value:m[key]??(key==='start'?0:15),min,step:.1,...(key==='seconds'?{max:15}:{}),'aria-label':`${name} ${tag} ${ordinal}`,onchange:e=>{m[key]=Number(e.target.value);save();}});
            times.append(el('div',{class:'xs-grow'},[el('label',{text:name}),field]));
          }asset.append(times);
        }
        asset.append(button('Remove',()=>{refs[kind].splice(i,1);save();render();},'xs-danger'));col.append(asset);
      });
      col.append(button('+ Add',()=>upload(kind,refs)));row.append(col);
    }return row;
  }
  let previewBox;
  function renderPreview(){
    if(!previewBox)return; const record=state?.scenes?.[selected],film=state?.assembled?.video;
    const key=(record?.revision||'')+'|'+(film||'');if(previewBox.dataset.key===key)return;previewBox.dataset.key=key;previewBox.replaceChildren();
    if(record){previewBox.append(el('label',{text:'Scene result'}),el('video',{src:urlFor(record.video,'output'),controls:true,preload:'metadata'}),el('a',{href:urlFor(record.video,'output'),target:'_blank',text:'Open scene video'}));}
    if(film)previewBox.append(el('p',{},[el('a',{href:urlFor(film,'output'),target:'_blank',text:'Open complete film'})]));
  }
  function render(){
    const openDetails=Array.from(main.querySelectorAll('details')).map(d=>d.open);renderList();main.replaceChildren();const scene=story.scenes[selected];
    const title=el('input',{value:scene.title,'aria-label':'Scene name',oninput:e=>{scene.title=e.target.value;save();renderList();}});
    const seconds=el('input',{type:'number',value:scene.seconds,min:1,max:15,step:1,'aria-label':'Duration in seconds',onchange:e=>{scene.seconds=Number(e.target.value);save();renderList();}});
    main.append(el('div',{class:'xs-row'},[el('div',{class:'xs-grow'},[el('label',{text:'Selected scene'}),title]),el('div',{class:'xs-duration'},[el('label',{text:'Seconds'}),seconds])]));
    if(selected>0)main.append(el('label',{class:'xs-check'},[el('input',{type:'checkbox',checked:scene.continue_previous!==false,onchange:e=>{scene.continue_previous=e.target.checked;save();}}),document.createTextNode('Continue from the end of the previous scene')]));
    main.append(el('p',{class:'xs-hint',text:'Write what happens in this scene. Use <Picture 1>, <Video 1> and <Audio 1> to match the references below.'}),el('textarea',{value:scene.prompt,placeholder:'Describe the action, camera and dialogue for this scene…','aria-label':'Scene prompt',oninput:e=>{scene.prompt=e.target.value;save();}}));
    const common=el('details',{},[el('summary',{text:'Shared references and instructions · all scenes'}),el('textarea',{class:'xs-shared-prompt',value:story.shared_prompt,placeholder:'Character identity, voice, setting and style…','aria-label':'Shared prompt',oninput:e=>{story.shared_prompt=e.target.value;save();}}),el('p',{class:'xs-hint',text:'Shared references keep the same numbering in every scene. Videos provide visuals and motion; add their soundtrack to the Audio column to use it as a voice reference.'}),mediaPanel(story.references,true)]);
    const extras=el('details',{},[el('summary',{text:'Extra references · this scene only'}),mediaPanel(scene.references??={images:[],videos:[],audios:[]})]);
    const settings=el('details',{},[el('summary',{text:'Continuity and project'})]);
    const context=el('select',{'aria-label':'Context frames',onchange:e=>{story.context_frames=Number(e.target.value);save();}},[5,22,39,56].map(n=>el('option',{value:n,text:`${n} frames · ${(n/24).toFixed(2)}s`,selected:n===story.context_frames})));
    const seed=el('input',{type:'number',min:0,max:Number.MAX_SAFE_INTEGER,value:story.seed,'aria-label':'Initial seed',onchange:e=>{story.seed=Number(e.target.value);save();}});
    const quality=el('select',{'aria-label':'Reference size',onchange:e=>{story.ref_image_size=e.target.value;save();}},[['max','Original (max)'],['match','Limit to generation resolution (match)']].map(([v,t])=>el('option',{value:v,text:t,selected:v===story.ref_image_size})));
    settings.append(el('label',{text:'Final frames used in the next scene'}),context,el('p',{class:'xs-hint',text:'The context segment is removed from the output. Each video will have the duration set above.'}),el('label',{class:'xs-check'},[el('input',{type:'checkbox',checked:story.continue_audio,onchange:e=>{story.continue_audio=e.target.checked;save();}}),document.createTextNode('Also continue ambient audio and voice')]),el('label',{text:'Initial seed'}),seed,el('label',{text:'Image references'}),quality,el('p',{class:'xs-hint',text:'Project: '+story.project_id}),button('Create a new story from this one',()=>{story.project_id='story_'+uid();state=null;save();render();message('New story created. Previous results remain saved.');}));
    [common,extras,settings].forEach((d,i)=>{d.open=!!openDetails[i];});previewBox=el('div',{class:'xs-preview'});main.append(common,extras,settings,previewBox);
    if(story.scenes.length>1)main.append(el('p',{},[button('Delete this scene from the script',()=>{story.scenes.splice(selected,1);selected=Math.max(0,selected-1);story.scenes[0].continue_previous=false;state=null;save();render();},'xs-danger')]));
    renderPreview();
  }
  function close(){closed=true;clearInterval(timer);save();backdrop.remove();}
  const name=el('input',{value:story.title,'aria-label':'Story name',oninput:e=>{story.title=e.target.value;save();}});
  const aside=el('aside',{},[el('label',{text:'Story'}),name,list,button('+ Add scene',()=>{story.scenes.push({title:'Scene '+(story.scenes.length+1),prompt:'',seconds:15,continue_previous:true,references:{images:[],videos:[],audios:[]}});selected=story.scenes.length-1;save();render();})]);
  modal.append(el('header',{},[el('div',{},[el('h2',{text:'Story Studio'}),el('div',{class:'xs-sub',text:'MiniMax H3 · prompts, references and continuity'})]),saved,button('Close',close,'xs-close')]),el('div',{class:'xs-body'},[aside,main]),el('footer',{},[el('div',{class:'xs-actions'},[button('Continue sequence',()=>run('continue'),'xs-primary'),button('Generate next scene',()=>run('next')),button('Generate / redo selected',()=>run('selected')),button('Stop after this scene',async()=>{try{save();await post('pause',{project_id:story.project_id});message('The sequence will stop after the current scene.');}catch(e){message(e.message,true);}})]),status]));
  backdrop.append(modal);document.body.append(backdrop);render();refresh();timer=setInterval(refresh,5000);
}

app.registerExtension({
  name:'ComfyUI.MinimaxH3.StoryStudio',
  async beforeRegisterNodeDef(nodeType,nodeData){
    if(![TYPE,STUDIO_TYPE].includes(nodeData.name))return;
    if(nodeData.name===STUDIO_TYPE){
      const configure=nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure=function(){
        configure?.apply(this,arguments);
        this.title=STUDIO_NAME;
        // Saved graphs may still contain the former optional media slots.
        for(let i=(this.inputs?.length??0)-1;i>=0;i--){
          if(['reference_image','reference_video','reference_audio'].includes(this.inputs[i].name))this.removeInput(i);
        }
      };
    }
    const original=nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated=function(){
      original?.apply(this,arguments);
      for(const name of ['story_json','execution_token']){
        const w=widget(this,name);if(!w)continue;w.type='hidden';w.computeSize=()=>[0,-4];if(w.inputEl)w.inputEl.classList.add('xs-hidden');if(w.element)w.element.classList.add('xs-hidden');
      }
      if(!widget(this,'story_json').value)widget(this,'story_json').value=JSON.stringify(defaults());
      this.addWidget('button','Open Story Studio',null,()=>openEditor(this),{serialize:false});
      if(nodeData.name===STUDIO_TYPE)this.title=STUDIO_NAME;
      this.color='#24413f';this.bgcolor='#172a2d';this.size=nodeData.name===STUDIO_TYPE?[520,670]:[380,220];
    };
  }
});
