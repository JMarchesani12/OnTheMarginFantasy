import React, {useState} from '../../front-end/node_modules/react';
import {createRoot} from '../../front-end/node_modules/react-dom/client';
import {MemoryRouter} from '../../front-end/node_modules/react-router-dom';
import Home from '../../front-end/src/screens/Home/Home';
import DraftOrderEditor from '../../front-end/src/components/League/DraftOrderEditor';
import LeagueScoreboard from '../../front-end/src/components/League/LeagueScoreboard';
import '../../front-end/src/index.css';
import '../../front-end/src/screens/CreateLeague/CreateLeague.css';
import '../../front-end/src/screens/League/ManageLeaguePage.css';
const root=createRoot(document.getElementById('root')!);let serial=0;
function Draft({count}:{count:number}){
 const [members,setMembers]=useState<any[]>(Array.from({length:count},(_,i)=>({id:i+1,teamName:`Team ${i+1}`,userId:i+1,displayName:`User ${i+1}`,leagueId:1,draftOrder:i+1})));
 return <DraftOrderEditor orderedMembers={members} memberCount={members.length} membersLoading={false} membersError={null} memberActionError={null} draggingMemberId={null} currentUserId={1} onMoveMember={(id,d)=>setMembers(old=>{const next=[...old],i=next.findIndex(m=>m.id===id);[next[i],next[i+d]]=[next[i+d],next[i]];return next;})} onRandomize={()=>{}} onRemoveMember={()=>{}} onDragStart={()=>{}} onDragOver={()=>{}} onDragEnd={()=>{}}/>;
}
function Fixture({kind,count}:{kind:string;count:number}){
 return <MemoryRouter><main data-audit-kind={kind}>{kind==='home'?<Home/>:kind==='draft'?<Draft count={count}/>:<LeagueScoreboard weekNumbers={Array.from({length:13},(_,i)=>i+1)} currentWeekNumber={13} loading={false} error={null} rows={Array.from({length:count},(_,i)=>({memberId:i+1,teamName:`Team ${i+1}`,totalPoints:i,weeklyPoints:Object.fromEntries(Array.from({length:13},(_,w)=>[w+1,w+i])),weeklyDifferentials:Object.fromEntries(Array.from({length:13},(_,w)=>[w+1,i-w]))}))}/>}</main></MemoryRouter>;
}
const frames=()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
(window as any).audit={async mount(kind:string,count:number){(globalThis as any).__auditCount=count;const start=performance.now();root.render(<Fixture key={++serial} kind={kind} count={count}/>);const selector=kind==='home'?'.league-card':kind==='draft'?'.ml-draft-order-row':'.league-scoreboard__row:not(.league-scoreboard__row--header)';const deadline=performance.now()+5000;while(document.querySelectorAll(selector).length!==count||document.querySelector('main')?.getAttribute('data-audit-kind')!==kind){if(performance.now()>deadline)throw Error('Fixture DOM count timeout');await new Promise(r=>setTimeout(r,1));}await frames();return {kind,count,settleMs:performance.now()-start,rows:document.querySelectorAll(selector).length,domNodes:document.querySelectorAll('*').length};},frames};
