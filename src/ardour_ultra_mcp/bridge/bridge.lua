-- SPDX-License-Identifier: GPL-3.0-or-later
-- Original allowlisted bridge. File I/O ONLY in non-realtime EditorHook context.
ardour { ["type"] = "EditorHook", name = "Ardour Ultra MCP", author = "Ardour Ultra MCP contributors", license = "GPL-3.0-or-later", description = "Private local MCP mailbox; activate only on a trusted project" }
function signals() return LuaSignal.Set():add({[LuaSignal.LuaTimerDS] = true}) end

function factory(params)
  local root = @MAILBOX_LUA@
  local max_bytes = 4194304
  local NULL = {}
  local function array(t) return setmetatable(t or {}, {__json_array=true}) end
  local function fail(code, message, action) error({code=code, message=message, action=action or "Refresh state and correct the request.", details={}}, 0) end
  local function number(v, lo, hi, integer)
    if type(v)~="number" or v~=v or v==math.huge or v==-math.huge or v<lo or v>hi or (integer and v~=math.floor(v)) then fail("VALIDATION_ERROR", "Numeric value outside explicit range.") end
    return v
  end
  local function text(v, maxlen)
    if type(v)~="string" or #v<1 or #v>(maxlen or 200) or v:find("[%z\1-\31]") then fail("VALIDATION_ERROR", "Invalid string.") end
    return v
  end
  local function id(v) text(v,160); if v:find("[^%w_.:%-]") then fail("VALIDATION_ERROR","Invalid object ID.") end; return v end
  local function bool(v) if type(v)~="boolean" then fail("VALIDATION_ERROR","Expected boolean.") end;return v end
  local function name(v) text(v,200);if v:find("[/\\]") then fail("VALIDATION_ERROR","Names cannot contain path separators.") end;return v end
  local function list(v, limit)
    if type(v)~="table" or #v<1 or #v>limit then fail("VALIDATION_ERROR","Invalid batch size.") end
    local n=0;for k,_ in pairs(v) do n=n+1;if type(k)~="number" or k<1 or k>#v then fail("VALIDATION_ERROR","Expected array.") end end
    if n~=#v then fail("VALIDATION_ERROR","Sparse array.") end
    return v
  end
  -- Strict JSON parser; no load/loadstring/eval, duplicate keys rejected.
  local function decode(s)
    if #s>max_bytes then fail("PROTOCOL_ERROR","Payload too large.") end
    local i=1
    local function ws() local _,e=s:find("^[ \t\r\n]*",i);i=(e or i-1)+1 end
    local function str()
      if s:sub(i,i)~='"' then fail("PROTOCOL_ERROR","Expected JSON string.") end
      i=i+1;local parts={}
      while i<=#s do
        local c=s:sub(i,i);i=i+1
        if c=='"' then return table.concat(parts) end
        if c=='\\' then
          local e=s:sub(i,i);i=i+1
          local map={['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'}
          if map[e] then parts[#parts+1]=map[e]
          elseif e=='u' then
            local hex=s:sub(i,i+3);if #hex~=4 or hex:find('[^0-9a-fA-F]') then fail("PROTOCOL_ERROR","Invalid Unicode escape.") end
            local cp=tonumber(hex,16);i=i+4
            if cp>=0xd800 and cp<=0xdbff then
              if s:sub(i,i+1)~='\\u' then fail("PROTOCOL_ERROR","Missing low surrogate.") end
              local low=s:sub(i+2,i+5);if #low~=4 or low:find('[^0-9a-fA-F]') then fail("PROTOCOL_ERROR","Invalid surrogate.") end
              local lp=tonumber(low,16);if lp<0xdc00 or lp>0xdfff then fail("PROTOCOL_ERROR","Invalid surrogate.") end
              cp=0x10000+(cp-0xd800)*1024+lp-0xdc00;i=i+6
            elseif cp>=0xdc00 and cp<=0xdfff then fail("PROTOCOL_ERROR","Unexpected low surrogate.") end
            parts[#parts+1]=utf8.char(cp)
          else fail("PROTOCOL_ERROR","Invalid JSON escape.") end
        else if c:byte()<32 then fail("PROTOCOL_ERROR","Unescaped control character.") end;parts[#parts+1]=c end
      end
      fail("PROTOCOL_ERROR","Unterminated JSON string.")
    end
    local parse
    parse=function(depth)
      if depth>48 then fail("PROTOCOL_ERROR","JSON nesting limit.") end
      ws();local c=s:sub(i,i)
      if c=='"' then return str() end
      if c=='{' then
        i=i+1;ws();local t={};if s:sub(i,i)=='}' then i=i+1;return t end
        while true do
          ws();local k=str();if t[k]~=nil then fail("PROTOCOL_ERROR","Duplicate JSON key.") end
          ws();if s:sub(i,i)~=':' then fail("PROTOCOL_ERROR","Missing colon.") end;i=i+1;t[k]=parse(depth+1);ws();local e=s:sub(i,i);i=i+1
          if e=='}' then break end;if e~=',' then fail("PROTOCOL_ERROR","Missing comma.") end
        end;return t
      end
      if c=='[' then
        i=i+1;ws();local t=array();if s:sub(i,i)==']' then i=i+1;return t end
        while true do t[#t+1]=parse(depth+1);ws();local e=s:sub(i,i);i=i+1;if e==']' then break end;if e~=',' then fail("PROTOCOL_ERROR","Missing comma.") end end;return t
      end
      for word,v in pairs({['true']=true,['false']=false,['null']=NULL}) do if s:sub(i,i+#word-1)==word then i=i+#word;return v end end
      local rest=s:sub(i);local token=rest:match('^%-?%d+%.?%d*[eE][%+%-]?%d+') or rest:match('^%-?%d+%.%d+') or rest:match('^%-?%d+')
      if not token or token:match('^%-?0%d') then fail("PROTOCOL_ERROR","Invalid JSON number.") end
      i=i+#token;local n=tonumber(token);number(n,-9007199254740991,9007199254740991,false);return n
    end
    local v=parse(0);ws();if i<=#s then fail("PROTOCOL_ERROR","Trailing JSON data.") end;return v
  end
  local function quote(s)
    return '"'..s:gsub('[%z\1-\31\\"]',function(c) local map={['"']='\\"',['\\']='\\\\',['\n']='\\n',['\r']='\\r',['\t']='\\t'};return map[c] or string.format('\\u%04x',c:byte()) end)..'"'
  end
  local encode
  encode=function(v, depth)
    depth=depth or 0;if depth>48 then fail("PROTOCOL_ERROR","Result nesting limit.") end
    if v==NULL or v==nil then return 'null' end
    if type(v)=='boolean' then return v and 'true' or 'false' end
    if type(v)=='number' then if v~=v or v==math.huge or v==-math.huge then return 'null' end;return string.format('%.17g',v):gsub(',','.') end
    if type(v)=='string' then return quote(v) end
    if type(v)~='table' then fail("PROTOCOL_ERROR","Unserializable value.") end
    local m=getmetatable(v);local parts={}
    if m and m.__json_array then for _,x in ipairs(v) do parts[#parts+1]=encode(x,depth+1) end;return '['..table.concat(parts,',')..']' end
    local keys={};for k,_ in pairs(v) do if type(k)~='string' then fail("PROTOCOL_ERROR","JSON object key must be string.") end;keys[#keys+1]=k end;table.sort(keys)
    for _,k in ipairs(keys) do parts[#parts+1]=quote(k)..':'..encode(v[k],depth+1) end;return '{'..table.concat(parts,',')..'}'
  end
  local function read(file,limit)
    local f=io.open(root..'/'..file,'rb');if not f then return nil end
    local value=f:read((limit or max_bytes)+1);f:close();if #value>(limit or max_bytes) then fail("PROTOCOL_ERROR","IPC file too large.") end;return value
  end
  local function write(file,value)
    local data=encode(value);if #data>max_bytes then fail("PROTOCOL_ERROR","Result too large; paginate.") end
    local f=assert(io.open(root..'/'..file..'.part','wb'));assert(f:write(data));f:close();assert(os.rename(root..'/'..file..'.part',root..'/'..file))
  end
  local config=decode(assert(read('bridge-config.json',16384),'Run installer first'))
  assert(config.protocol==1 and type(config.token)=='string' and #config.token==64)
  local epoch=tostring(os.time())..'-'..tostring(ARDOUR.LuaAPI.monotonic_time())
  local generation=0;local last_signature=nil;local session_key=nil;local busy=false;local last_heartbeat=0
  local snapshots={};local snapshot_sequence=0
  local handlers={};local mutations={};local destructive={};local compensable={}
  local function session()
    if not Session then fail("SESSION_NOT_OPEN","No session open.","Open an Ardour session.") end
  end
  local function revision() return epoch..':'..generation end
  local function route(v)
    session();local r=Session:route_by_id(PBD.ID(id(v)));if r:isnil() then fail("OBJECT_NOT_FOUND","Route ID not found.") end;return r
  end
  local function present(v) return v and not v:isnil() end
  local function oid(v) if v.to_stateful then return v:to_stateful():id():to_s() end;return v:id():to_s() end
  local function db(v) if v<=0 then return -193 end;return 20*math.log(v)/math.log(10) end
  local function gain(v) return 10^(number(v,-193,24,false)/20) end
  local function control_value(c) if not present(c) then return NULL end;return c:get_value() end
  local function route_state(r)
    local t=r:to_track();local p=r:pan_azimuth_control();local kind='bus'
    if r:is_master() then kind='master' elseif present(t) then kind=t:data_type():to_string() end
    local playlist=present(t) and t:playlist() or nil
    return {id=oid(r),name=r:name(),kind=kind,gain_db=db(r:gain_control():get_value()),pan=present(p) and (2*p:get_value()-1) or NULL,mute=r:muted(),solo=r:soloed(),armed=present(t) and t:rec_enable_control():get_value()>0 or false,playlist_id=present(playlist) and oid(playlist) or NULL}
  end
  local function page(values,a)
    local offset=number(a.offset or 0,0,10000000,true);local limit=number(a.limit or 100,1,1000,true);local filtered=array();local pattern=a.name_filter or ''
    if type(pattern)~='string' or #pattern>200 then fail("VALIDATION_ERROR","Invalid filter.") end
    for _,v in ipairs(values) do if (v.name or ''):lower():find(pattern:lower(),1,true) or (v.category or ''):lower():find(pattern:lower(),1,true) then filtered[#filtered+1]=v end end
    local items=array();for i=offset+1,math.min(#filtered,offset+limit) do items[#items+1]=filtered[i] end
    return {items=items,total=#filtered,offset=offset,limit=limit,next_offset=offset+limit<#filtered and offset+limit or NULL}
  end
  local function pos(v)
    if type(v)~='table' then fail("INVALID_TIME_POSITION","Expected typed position.") end
    local tm=Temporal.TempoMap.read()
    if v.unit=='samples' then return Temporal.timepos_t(number(v.samples,0,9007199254740991,true)) end
    if v.unit=='seconds' then return Temporal.timepos_t(math.floor(number(v.seconds,0,1e10,false)*Session:nominal_sample_rate()+.5)) end
    if v.unit=='quarter_ticks' then return Temporal.timepos_t.from_ticks(number(v.ticks,0,9007199254740991,true)) end
    if v.unit=='bbt' then
      local bbt=Temporal.BBT_Argument(number(v.bar,1,1000000,true),number(v.beat,1,128,true),number(v.tick or 0,0,1919,true))
      local p=Temporal.timepos_t(tm:sample_at_beats(tm:quarters_at_bbt(bbt)))
      local canonical=tm:bbt_at(p)
      if canonical.bars~=bbt.bars or canonical.beats~=bbt.beats or math.abs(canonical.ticks-bbt.ticks)>1 then fail("INVALID_TIME_POSITION","BBT outside current meter.") end
      return p
    end
    fail("INVALID_TIME_POSITION","Unsupported time unit.")
  end
  local function region(a)
    local r=route(a.track_id);local t=r:to_track();if not present(t) then fail("OPERATION_NOT_SUPPORTED","Bus has no playlist.") end
    local pl=t:playlist();local reg=pl:region_by_id(PBD.ID(id(a.region_id)));if not present(reg) then fail("OBJECT_NOT_FOUND","Region not in route's active playlist.") end
    return reg,pl
  end
  local function region_state(r,pl,track_id)
    local midi=r:to_midiregion();local audio=r:to_audioregion()
    return {id=oid(r),name=r:name(),playlist_id=oid(pl),track_id=track_id,kind=present(midi) and 'midi' or 'audio',position_samples=r:position():samples(),length_samples=r:length():samples(),source_start_samples=r:start():samples(),source_start_ticks=r:start():ticks(),muted=r:muted(),locked=r:locked(),gain_db=present(audio) and db(audio:scale_amplitude()) or NULL}
  end
  local function processor(a,which)
    local r=route(a.track_id);local p=Session:processor_by_id(PBD.ID(id(a[which or 'processor_id'])))
    if not present(p) then fail("OBJECT_NOT_FOUND","Processor not found.") end
    local i=0;while true do local q=r:nth_processor(i);if not present(q) then break end;if oid(q)==oid(p) then return p,r end;i=i+1 end
    fail("OBJECT_NOT_FOUND","Processor does not belong to specified route.")
  end
  local function plugin(a)
    local p,r=processor(a);local pi=p:to_insert();if not present(pi) then fail("OPERATION_NOT_SUPPORTED","Processor is not plugin insert.") end;return p,pi:plugin(0),r
  end
  local function param(p,idx)
    number(idx,0,65535,true);local port,flags=p:nth_parameter(idx,false)
    if not flags[2] or not p:parameter_is_control(port) then fail("PARAMETER_NOT_FOUND","Not a control parameter ordinal.") end
    local rv,pd=p:get_parameter_descriptor(port,ARDOUR.ParameterDescriptor());if rv~=0 then fail("PARAMETER_NOT_FOUND","Descriptor unavailable.") end
    return port,pd[2]
  end
  local function notes(mm)
    local values=array();local refs={}
    for n in ARDOUR.LuaAPI.note_list(mm):iter() do
      if #values>=100000 then fail("BACKEND_UNSUPPORTED","Model exceeds bridge safety limit.") end
      values[#values+1]={pitch=n:note(),velocity=n:velocity(),channel=n:channel()+1,start_ticks=n:time():to_ticks(),duration_ticks=n:length():to_ticks()};refs[#refs+1]=n
    end;return values,refs
  end
  local function note_model(a)
    local r=region(a);local mr=r:to_midiregion();if not present(mr) then fail("OPERATION_NOT_SUPPORTED","Requires MIDI region.") end;return mr:midi_source(0):model(),r
  end
  local function new_note(n)
    number(n.pitch,0,127,true);number(n.velocity,1,127,true);number(n.channel,1,16,true);number(n.start_ticks,0,9007199254740991,true);number(n.duration_ticks,1,9007199254740991,true)
    return ARDOUR.LuaAPI.new_noteptr(n.channel-1,Temporal.Beats(math.floor(n.start_ticks/1920),n.start_ticks%1920),Temporal.Beats(math.floor(n.duration_ticks/1920),n.duration_ticks%1920),n.pitch,n.velocity)
  end
  local function diff(target,label,fn)
    target:to_stateful():clear_changes();Session:begin_reversible_command(label)
    local ok,err=pcall(fn)
    if not ok then Session:abort_reversible_command();fail("OUTCOME_UNCERTAIN","Region edit failed; native abort does not undo applied effects.","Inspect region and use native undo if a completed command exists.") end
    Session:add_stateful_diff_command(target:to_statefuldestructible());Session:commit_reversible_command(nil)
  end
  local function register(command,mutates,fn,delete,compensates)
    handlers[command]=fn;mutations[command]=mutates;destructive[command]=delete or false;compensable[command]=compensates or false
  end
  -- Revision observes route mixer and region properties only. MIDI has exact model guards.
  local function observe()
    local key=Session:path();if session_key~=key then generation=generation+1;last_signature=nil;session_key=key;snapshots={} end
    local state=array()
    for r in Session:get_routes():iter() do
      local s=route_state(r);local t=r:to_track();s.regions=array()
      if present(t) then for reg in t:playlist():region_list():iter() do s.regions[#s.regions+1]=region_state(reg,t:playlist(),oid(r)) end end
      state[#state+1]=s
    end
    local signature=encode(state)
    if last_signature and last_signature~=signature then generation=generation+1 end
    last_signature=signature
  end
  register('ping',false,function(a,dry) return {connected=true,session_open=true,epoch=epoch} end)
  register('get_session_info',false,function(a,dry)
    local uuid=Session.uuid and Session:uuid() or nil
    return {session_id=uuid or ('bridge-session:'..epoch),persistent_session_id=uuid~=nil,name=Session:name(),sample_rate=Session:nominal_sample_rate(),snapshot=Session:snap_name(),revision_scope='route mixer and region properties; MIDI uses exact model guard; excludes plugin/automation/ports/tempo human edits'}
  end)
  register('list_tracks',false,function(a,dry) local values=array();for r in Session:get_routes():iter() do if not r:is_monitor() and not r:is_auditioner() then values[#values+1]=route_state(r) end end;return page(values,a) end)
  register('get_track',false,function(a,dry) return route_state(route(a.track_id)) end)
  register('create_track',true,function(a,dry)
    name(a.name);number(a.channels,1,64,true);if a.kind~='audio' and a.kind~='midi' and a.kind~='bus' then fail("VALIDATION_ERROR","Unknown route kind.") end
    if dry then return {name=a.name,kind=a.kind} end
    local routes
    if a.kind=='audio' then routes=Session:new_audio_track(a.channels,a.channels,nil,1,a.name,-1,ARDOUR.TrackMode.Normal,true)
    elseif a.kind=='bus' then routes=Session:new_audio_route(a.channels,a.channels,nil,1,a.name,ARDOUR.PresentationInfo.Flag.AudioBus,-1)
    else local c=ARDOUR.ChanCount(ARDOUR.DataType('midi'),1);routes=Session:new_midi_track(c,c,true,ARDOUR.PluginInfo(),nil,nil,1,a.name,-1,ARDOUR.TrackMode.Normal,true) end
    if routes:empty() then fail("BACKEND_ERROR","Ardour did not create route.") end;return route_state(routes:front())
  end)
  register('delete_track',true,function(a,dry) local r=route(a.track_id);if r:is_singleton() then fail("PERMISSION_DENIED","Cannot delete singleton/master route.") end;if not dry then Session:remove_route(r) end;return {deleted_id=a.track_id,undoable=false} end,true)
  register('rename_track',true,function(a,dry) local r=route(a.track_id);name(a.name);local before=r:name();if not dry and not r:set_name(a.name) then fail("BACKEND_ERROR","Rename failed.") end;return {object_id=a.track_id,property='name',before=before,after=a.name,undoable=false} end,false,true)
  local function set_control(command, getter, key, validate, convert)
    register(command,true,function(a,dry)
      local r=route(a.track_id);local c=getter(r);if not present(c) then fail("OPERATION_NOT_SUPPORTED","Control not available on route.") end
      validate(a[key]);local value=convert(a[key]);number(value,c:lower(),c:upper(),false);local before=c:get_value()
      if not dry then c:set_value(value,PBD.GroupControlDisposition.NoGroup) end
      return {object_id=a.track_id,property=key,before=before,after=dry and value or c:get_value(),unit='native_control',undoable=false}
    end,false,true)
  end
  set_control('set_track_gain',function(r) return r:gain_control() end,'gain_db',function(v) number(v,-193,6,false) end,gain)
  set_control('set_track_pan',function(r) return r:pan_azimuth_control() end,'pan',function(v) number(v,-1,1,false) end,function(v) return (v+1)/2 end)
  set_control('set_track_mute',function(r) return r:mute_control() end,'enabled',bool,function(v) return v and 1 or 0 end)
  set_control('set_track_solo',function(r) return r:solo_control() end,'enabled',bool,function(v) return v and 1 or 0 end)
  set_control('arm_track',function(r) local t=r:to_track();if not present(t) then fail("OPERATION_NOT_SUPPORTED","Bus is not recordable.") end;return t:rec_enable_control() end,'enabled',bool,function(v) return v and 1 or 0 end)
  compensable.arm_track=false
  register('set_monitoring',true,function(a,dry)
    local r=route(a.track_id);local modes={auto=ARDOUR.MonitorChoice.MonitorAuto,input=ARDOUR.MonitorChoice.MonitorInput,disk=ARDOUR.MonitorChoice.MonitorDisk};local v=modes[a.mode];if not v then fail("VALIDATION_ERROR","Unknown monitoring mode.") end
    local c=r:monitoring_control();if not present(c) then fail("OPERATION_NOT_SUPPORTED","No monitoring control.") end;if not dry then c:set_value(v,PBD.GroupControlDisposition.NoGroup) end;return {mode=a.mode,undoable=false}
  end)
  register('get_transport',false,function(a,dry) return {samples=Session:transport_sample(),speed=Session:transport_speed(),record_enabled=Session:record_status()~=ARDOUR.Session.RecordState.Disabled,actively_recording=Session:actively_recording(),loop_enabled=Session:get_play_loop()} end)
  register('play',true,function(a,dry) if not dry then Session:request_roll(ARDOUR.TransportRequestSource.TRS_UI) end;return {requested='play',asynchronous=true} end)
  register('stop',true,function(a,dry) if not dry then Session:request_stop(false,false,ARDOUR.TransportRequestSource.TRS_UI) end;return {requested='stop',asynchronous=true} end)
  register('locate',true,function(a,dry) local p=pos(a.position);if not dry then Session:request_locate(p:samples(),false,ARDOUR.LocateTransportDisposition.MustStop,ARDOUR.TransportRequestSource.TRS_UI) end;return {requested_samples=p:samples(),asynchronous=true} end)
  register('start_recording',true,function(a,dry)
    local armed=false;for t in Session:get_tracks():iter() do if t:rec_enable_control():get_value()>0 then armed=true end end
    if not armed then fail("VALIDATION_ERROR","Arm a track before recording.") end
    if not dry then Session:maybe_enable_record();Session:request_roll(ARDOUR.TransportRequestSource.TRS_UI) end;return {requested='record',asynchronous=true}
  end)
  register('stop_recording',true,function(a,dry) if not dry then Session:request_stop(false,false,ARDOUR.TransportRequestSource.TRS_UI);Session:disable_record(false,true) end;return {requested='stop_recording',asynchronous=true} end)
  register('set_loop',true,function(a,dry) local s,e=pos(a.start),pos(a['end']);if e:samples()<=s:samples() then fail("INVALID_TIME_POSITION","Range end must follow start.") end;local loc=Session:locations():auto_loop_location();if not loc then fail("OPERATION_NOT_SUPPORTED","Create a loop location in Ardour first.") end;if not dry then loc:set(s,e);Session:request_play_loop(true,false,ARDOUR.TransportRequestSource.TRS_UI) end;return {start_samples=s:samples(),end_samples=e:samples()} end)
  register('clear_loop',true,function(a,dry) if not dry then Session:request_play_loop(false,false,ARDOUR.TransportRequestSource.TRS_UI) end;return {loop_enabled=false} end)
  register('convert_position',false,function(a,dry) local p=pos(a.position);local tm=Temporal.TempoMap.read();local b=tm:bbt_at(p);return {samples=p:samples(),seconds=p:samples()/Session:nominal_sample_rate(),quarter_ticks=tm:quarters_at(p):to_ticks(),bbt={bar=b.bars,beat=b.beats,tick=b.ticks},ticks_per_quarter=1920} end)
  register('set_tempo',true,function(a,dry) local p=pos(a.position);number(a.bpm,1,999,false);if not dry then local tm=Temporal.TempoMap.write_copy();local ok,err=pcall(function() tm:set_tempo(Temporal.Tempo(a.bpm,a.bpm,4),p);Temporal.TempoMap.update(tm) end);if not ok then Temporal.TempoMap.abort_update();error(err,0) end end;return {bpm=a.bpm,position_samples=p:samples(),undoable=false} end)
  register('set_time_signature',true,function(a,dry) local p=pos(a.position);number(a.numerator,1,128,true);if not ({[1]=true,[2]=true,[4]=true,[8]=true,[16]=true,[32]=true,[64]=true})[a.denominator] then fail("VALIDATION_ERROR","Invalid denominator.") end;if not dry then local tm=Temporal.TempoMap.write_copy();local ok,err=pcall(function() tm:set_meter(Temporal.Meter(a.numerator,a.denominator),p);Temporal.TempoMap.update(tm) end);if not ok then Temporal.TempoMap.abort_update();error(err,0) end end;return {numerator=a.numerator,denominator=a.denominator,undoable=false} end)
  register('save_session',true,function(a,dry) if not dry and Session:save_state('',false,false,false)~=0 then fail("BACKEND_ERROR","Session save failed.") end;return {saved=not dry} end)
  register('create_snapshot',true,function(a,dry)
    name(a.name);if not a.name:match('^[%w][%w _.%-]*$') or #a.name>100 then fail("VALIDATION_ERROR","Unsafe snapshot filename.") end
    local filename=Session:path()..'/'..a.name..'.ardour';local f=io.open(filename,'rb');if f then f:close();fail("FILE_EXISTS","Snapshot already exists.") end
    if not dry and Session:save_state(a.name,false,false,false)~=0 then fail("BACKEND_ERROR","Snapshot save failed.") end;return {snapshot=a.name,saved=not dry}
  end)
  register('list_regions',false,function(a,dry)
    local r=route(a.track_id);local t=r:to_track();local values=array();if not present(t) then return page(values,a) end
    local pl=t:playlist();for reg in pl:region_list():iter() do local s=region_state(reg,pl,a.track_id);if a.kind=='all' or a.kind==s.kind then values[#values+1]=s end end;return page(values,a)
  end)
  register('get_region',false,function(a,dry) local r,pl=region(a);return region_state(r,pl,a.track_id) end)
  register('create_midi_region',true,function(a,dry)
    name(a.name);local r=route(a.track_id);local t=r:to_track();if not present(t) or t:data_type():to_string()~='midi' then fail("OPERATION_NOT_SUPPORTED","Requires MIDI track.") end
    if not Editor then fail("BACKEND_UNSUPPORTED","MIDI region creation requires Editor context.") end
    local s,e=pos(a.start),pos(a['end']);if e:samples()<=s:samples() then fail("INVALID_TIME_POSITION","Region end must follow start.") end
    if dry then return {start_samples=s:samples(),end_samples=e:samples()} end
    local view=Editor:rtav_from_route(r):to_timeaxisview():to_midi_time_axis_view();local reg=view:add_region(s,s:distance(e),true)
    if not present(reg) then fail("BACKEND_ERROR","Ardour did not create region.") end;reg:set_name(a.name);return region_state(reg,t:playlist(),a.track_id)
  end)
  register('move_region',true,function(a,dry) local r,pl=region(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end;local p=pos(a.position);local before=r:position():samples();if not dry then diff(r,'Ultra move region',function() r:set_position(p) end) end;return {object_id=a.region_id,property='position_samples',before=before,after=p:samples(),undoable=true} end)
  register('trim_region',true,function(a,dry)
    local r=region(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end;local s,e=pos(a.start),pos(a['end']);local old=r:position():samples();local ending=old+r:length():samples()
    if s:samples()<old or e:samples()>ending or e:samples()<=s:samples() then fail("INVALID_TIME_POSITION","Trim bounds outside original region.") end
    if not dry then diff(r,'Ultra trim region',function() r:trim_to(s,s:distance(e)) end) end;return {region_id=a.region_id,start_samples=s:samples(),length_samples=e:samples()-s:samples(),undoable=true}
  end)
  register('split_region',true,function(a,dry)
    local r,pl=region(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end;local p=pos(a.position);local start=r:position():samples()
    if p:samples()<=start or p:samples()>=start+r:length():samples() then fail("INVALID_TIME_POSITION","Split must be strictly inside region.") end
    local old={};for x in pl:region_list():iter() do old[oid(x)]=true end
    if not dry then diff(pl,'Ultra split region',function() pl:split_region(r,p) end) end
    local added=array();if not dry then for x in pl:region_list():iter() do if not old[oid(x)] then added[#added+1]=oid(x) end end end
    return {removed_id=a.region_id,region_ids=added,undoable=true}
  end)
  register('delete_region',true,function(a,dry) local r,pl=region(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end;if not dry then diff(pl,'Ultra delete region',function() pl:remove_region(r) end) end;return {deleted_id=a.region_id,undoable=true} end,true)
  register('set_region_gain',true,function(a,dry) local r=region(a);local ar=r:to_audioregion();if not present(ar) then fail("OPERATION_NOT_SUPPORTED","Requires audio region.") end;local v=gain(a.gain_db);local before=db(ar:scale_amplitude());if not dry then diff(r,'Ultra region gain',function() ar:set_scale_amplitude(v) end) end;return {object_id=a.region_id,property='gain_db',before=before,after=a.gain_db,undoable=true} end)
  register('set_region_mute',true,function(a,dry) local r=region(a);bool(a.enabled);if not dry then diff(r,'Ultra region mute',function() r:set_muted(a.enabled) end) end;return {region_id=a.region_id,muted=a.enabled,undoable=true} end)
  register('set_region_lock',true,function(a,dry) local r=region(a);bool(a.enabled);if not dry then diff(r,'Ultra region lock',function() r:set_locked(a.enabled) end) end;return {region_id=a.region_id,locked=a.enabled,undoable=true} end)
  -- Fade length setters exist in some builds; capability is checked before use.
  register('set_region_fades',true,function(a,dry)
    local r=region(a);local ar=r:to_audioregion();if not present(ar) then fail("OPERATION_NOT_SUPPORTED","Requires audio region.") end
    if not ar.set_fade_in_length or not ar.set_fade_out_length then fail("BACKEND_UNSUPPORTED","Fade setters not bound in this Ardour build.") end
    number(a.fade_in_samples,1,r:length():samples(),true);number(a.fade_out_samples,1,r:length():samples(),true)
    if not dry then ar:set_fade_in_length(a.fade_in_samples);ar:set_fade_out_length(a.fade_out_samples) end;return {region_id=a.region_id,fade_in_samples=a.fade_in_samples,fade_out_samples=a.fade_out_samples,undoable=false}
  end)
  register('list_midi_notes',false,function(a,dry)
    local mm=note_model(a);local values=notes(mm);local signature=encode(values);snapshot_sequence=snapshot_sequence+1;local token=epoch..':notes:'..snapshot_sequence
    snapshots[token]={signature=signature,region_id=a.region_id};snapshots[epoch..':notes:'..(snapshot_sequence-128)]=nil
    for i,v in ipairs(values) do v.note_ref=token..':'..i end
    local result=page(values,a);result.model_fingerprint=token;result.ticks_per_quarter=1920;result.scope='source-relative, including notes outside trimmed region';return result
  end)
  register('insert_midi_notes',true,function(a,dry)
    local mm,r=note_model(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end;list(a.notes,10000)
    local ptrs={};for _,n in ipairs(a.notes) do ptrs[#ptrs+1]=new_note(n) end
    if not dry then local command=mm:new_note_diff_command('Ultra insert MIDI notes');for _,n in ipairs(ptrs) do command:add(n) end;mm:apply_diff_command_as_commit(Session,command) end
    return {region_id=a.region_id,inserted_count=#ptrs,undoable=true}
  end)
  local function edit_notes(a,dry,delete)
    local mm,r=note_model(a);if r:locked() then fail("PERMISSION_DENIED","Region locked.") end
    local snap=snapshots[a.model_fingerprint];local values,ptrs=notes(mm)
    if not snap or snap.region_id~=a.region_id or snap.signature~=encode(values) then fail("STALE_OBJECT","MIDI model changed or reference expired.","List notes again before editing.") end
    local edits=delete and a.note_refs or a.replacements;list(edits,10000);local removed={};local additions={}
    for _,edit in ipairs(edits) do
      local ref=delete and edit or edit.note_ref;text(ref,250);local prefix,index=ref:match('^(.*):(%d+)$');index=tonumber(index)
      if prefix~=a.model_fingerprint or not index or not ptrs[index] or removed[index] then fail("STALE_OBJECT","Invalid/duplicate note reference.") end
      removed[index]=true;if not delete then additions[#additions+1]=new_note(edit.note) end
    end
    if not dry then local command=mm:new_note_diff_command(delete and 'Ultra delete MIDI notes' or 'Ultra edit MIDI notes');for i,_ in pairs(removed) do command:remove(ptrs[i]) end;for _,n in ipairs(additions) do command:add(n) end;mm:apply_diff_command_as_commit(Session,command) end
    return {region_id=a.region_id,changed_count=#edits,undoable=true}
  end
  register('edit_midi_notes',true,function(a,dry) return edit_notes(a,dry,false) end)
  register('delete_midi_notes',true,function(a,dry) return edit_notes(a,dry,true) end,true)
  register('list_available_plugins',false,function(a,dry)
    local values=array();local seen={};for p in ARDOUR.LuaAPI.list_plugins():iter() do local format=ARDOUR.PluginType.name(p.type);local key=format..':'..p.unique_id;if not seen[key] then values[#values+1]={plugin_id=p.unique_id,name=p.name,format=format,category=p.category,creator=p.creator,is_instrument=p:is_instrument()};seen[key]=true end end;return page(values,a)
  end)
  register('list_track_plugins',false,function(a,dry)
    local r=route(a.track_id);local values=array();local i=0;while true do local proc=r:nth_plugin(i);if not present(proc) then break end;local pi=proc:to_insert();local p=pi:plugin(0);values[#values+1]={id=oid(proc),name=proc:name(),plugin_id=p:unique_id(),format=ARDOUR.PluginType.name(pi:type()),enabled=proc:active(),is_instrument=pi:is_instrument(),plugin_index=i};i=i+1 end;return page(values,a)
  end)
  register('add_plugin',true,function(a,dry)
    local r=route(a.track_id);text(a.plugin_id,1000);number(a.index,0,4096,true);local format=ARDOUR.PluginType[a.format];if not format then fail("VALIDATION_ERROR","Unsupported plugin format.") end
    local info=ARDOUR.LuaAPI.new_plugin_info(a.plugin_id,format);if not present(info) then fail("PLUGIN_NOT_FOUND","Plugin ID/format not in Ardour inventory.") end
    if dry then return {plugin_id=a.plugin_id,format=a.format} end
    local p=ARDOUR.LuaAPI.new_plugin(Session,a.plugin_id,format,'');if not present(p) then fail("PLUGIN_NOT_FOUND","Ardour could not load plugin.") end
    if r:add_processor_by_index(p,a.index,nil,true)~=0 then fail("BACKEND_ERROR","Plugin stream configuration incompatible with route.") end
    return {processor_id=oid(p),plugin_id=a.plugin_id,undoable=false}
  end)
  register('remove_plugin',true,function(a,dry) local p,_,r=plugin(a);if not dry and r:remove_processor(p,nil,false)~=0 then fail("BACKEND_ERROR","Plugin removal failed.") end;return {deleted_id=a.processor_id,undoable=false} end,true)
  register('set_plugin_enabled',true,function(a,dry) local p=plugin(a);bool(a.enabled);local before=p:active();if not dry then if a.enabled then p:activate() else p:deactivate() end end;return {object_id=a.processor_id,property='enabled',before=before,after=a.enabled,undoable=false} end,false,true)
  register('get_plugin_parameters',false,function(a,dry)
    local proc,p=plugin(a);local values=array()
    for i=0,p:parameter_count()-1 do
      local ok,value=pcall(function() local port,pd=param(p,i);return {parameter_index=i,parameter_id=tostring(port),name=p:parameter_label(port),value=p:get_parameter(port),minimum=pd.lower,maximum=pd.upper,default=pd.normal,unit='plugin_native',display_format=pd.print_fmt,normalized_value=NULL,automation_capable=p:parameter_is_input(port),integer_step=pd.integer_step,logarithmic=pd.logarithmic} end)
      if ok then values[#values+1]=value end
    end
    return page(values,a)
  end)
  register('set_plugin_parameters',true,function(a,dry)
    local proc,p=plugin(a);list(a.parameters,4096);local changes=array();local seen={}
    for _,item in ipairs(a.parameters) do
      local port,pd=param(p,item.parameter_index);if seen[item.parameter_index] then fail("VALIDATION_ERROR","Duplicate parameter ordinal.") end;seen[item.parameter_index]=true
      if item.unit~='plugin_native' then fail("VALIDATION_ERROR","Physical unit unavailable: use inspected plugin_native value.") end
      if not p:parameter_is_input(port) then fail("PERMISSION_DENIED","Parameter is read-only output.") end
      number(item.value,pd.lower,pd.upper,pd.integer_step or pd.toggled);if pd.toggled and item.value~=pd.lower and item.value~=pd.upper then fail("VALIDATION_ERROR","Toggle must be lower or upper value.") end
      changes[#changes+1]={parameter_index=item.parameter_index,before=p:get_parameter(port),after=item.value}
    end
    if not dry then
      local applied={}
      for _,c in ipairs(changes) do
        local ok,success=pcall(ARDOUR.LuaAPI.set_processor_param,proc,c.parameter_index,c.after)
        if not ok or not success then
          local restored=true;for i=#applied,1,-1 do local x=applied[i];local good,rv=pcall(ARDOUR.LuaAPI.set_processor_param,proc,x.parameter_index,x.before);restored=restored and good and rv end
          if not restored then fail("OUTCOME_UNCERTAIN","Parameter rollback failed.","Inspect all affected plugin parameters.") end
          fail("BACKEND_ERROR","Parameter set failed; prior values restored.")
        end
        applied[#applied+1]=c;local port=param(p,c.parameter_index);c.after=p:get_parameter(port)
      end
    end
    return {processor_id=a.processor_id,parameters=changes,undoable=false}
  end,false,true)
  register('list_plugin_presets',false,function(a,dry) local _,p=plugin(a);local values=array();for ps in p:get_info():get_presets():iter() do values[#values+1]={label=ps.label,uri=ps.uri,user=ps.user} end;return {items=values} end)
  register('load_plugin_preset',true,function(a,dry) local _,p=plugin(a);name(a.label);local ps=p:preset_by_label(a.label);if not ps or not ps.valid then fail("OBJECT_NOT_FOUND","Preset not found.") end;if not dry and not p:load_preset(ps) then fail("BACKEND_ERROR","Preset load failed.") end;return {loaded=a.label,undoable=false} end)
  local function sends(r)
    local values=array();local refs={};local i=0
    while true do local p=r:nth_send(i);if not present(p) then break end;local s=p:to_send();local internal=p:to_internalsend();local target=present(internal) and internal:target_route() or nil
      values[#values+1]={id=oid(p),name=p:name(),target_id=present(target) and oid(target) or NULL,gain_db=db(s:amp():gain_control():get_value())};refs[oid(p)]=p;i=i+1
    end;return values,refs
  end
  local function send(a) local p,r=processor(a,'send_id');local s=p:to_send();if not present(s) then fail("OPERATION_NOT_SUPPORTED","Processor is not send.") end;return p,s,r end
  register('list_sends',false,function(a,dry) return page(sends(route(a.track_id)),a) end)
  register('set_send_gain',true,function(a,dry) local p,s=send(a);number(a.gain_db,-193,6,false);local c=s:amp():gain_control();local before=db(c:get_value());if not dry then c:set_value(gain(a.gain_db),PBD.GroupControlDisposition.NoGroup) end;return {object_id=a.send_id,property='gain_db',before=before,after=a.gain_db,undoable=false} end,false,true)
  register('remove_send',true,function(a,dry) local p,s,r=send(a);if not dry and r:remove_processor(p,nil,false)~=0 then fail("BACKEND_ERROR","Send removal failed.") end;return {deleted_id=a.send_id,undoable=false} end,true)
  local function ports()
    local values=array();local by_name={};local engine=Session:engine()
    for _,datatype in ipairs({'audio','midi'}) do for _,direction in ipairs({'input','output'}) do
      local flag=direction=='input' and ARDOUR.PortFlags.IsInput or ARDOUR.PortFlags.IsOutput
      local _,rv=engine:get_backend_ports('',ARDOUR.DataType(datatype),flag,C.StringVector())
      for pname in rv[4]:iter() do
        local _,ct=engine:get_connections(pname,C.StringVector());local connections=array();for target in ct[2]:iter() do connections[#connections+1]=target end
        local p=engine:get_port_by_name(pname);local s={name=pname,id=pname,data_type=datatype,direction=direction,internal=present(p),connections=connections};values[#values+1]=s;by_name[pname]=s
      end
    end end;return values,by_name
  end
  register('list_ports',false,function(a,dry) return page(ports(),a) end)
  register('connect_ports',true,function(a,dry)
    text(a.source,500);text(a.destination,500);local _,all=ports();local source,dest=all[a.source],all[a.destination]
    if not source or not dest then fail("OBJECT_NOT_FOUND","Engine port not found.") end
    if source.direction~='output' or dest.direction~='input' or source.data_type~=dest.data_type then fail("VALIDATION_ERROR","Port direction/type mismatch.") end
    if source.internal and dest.internal then fail("OPERATION_NOT_SUPPORTED","Internal raw routing is disabled until full feedback graph validation is available.","Use create_send for route-to-bus routing.") end
    if not dry and Session:engine():connect(a.source,a.destination)~=0 then fail("BACKEND_ERROR","Port connect failed.") end;return {source=a.source,destination=a.destination,undoable=false}
  end)
  register('disconnect_ports',true,function(a,dry)
    text(a.source,500);text(a.destination,500);local _,all=ports();local source,dest=all[a.source],all[a.destination];if not source or not dest then fail("OBJECT_NOT_FOUND","Engine port not found.") end
    if not dry and Session:engine():disconnect(a.source,a.destination)~=0 then fail("BACKEND_ERROR","Port disconnect failed.") end;return {source=a.source,destination=a.destination,undoable=false}
  end)
  register('create_send',true,function(a,dry)
    local r,target=route(a.track_id),route(a.target_id);number(a.gain_db,-193,6,false)
    if r:is_singleton() or present(target:to_track()) then fail("PERMISSION_DENIED","Sends require a non-singleton source and bus target.") end
    -- Include internal send and main output edges when checking for feedback.
    local input_owner={};for x in Session:get_routes():iter() do local io=x:input();for i=0,io:n_ports()-1 do input_owner[io:nth(i):name()]=oid(x) end end
    local graph={};local engine=Session:engine()
    for x in Session:get_routes():iter() do local edges={};local sv=sends(x);for _,s in ipairs(sv) do if s.target_id~=NULL then edges[#edges+1]=s.target_id end end
      local io=x:output();for i=0,io:n_ports()-1 do local _,ct=engine:get_connections(io:nth(i):name(),C.StringVector());for p in ct[2]:iter() do if input_owner[p] then edges[#edges+1]=input_owner[p] end end end
      graph[oid(x)]=edges
    end
    local visited={};local function reaches(v) if v==a.track_id then return true end;if visited[v] then return false end;visited[v]=true;for _,d in ipairs(graph[v] or {}) do if reaches(d) then return true end end;return false end
    if reaches(a.target_id) then fail("PERMISSION_DENIED","Send would create audio feedback cycle.") end
    local prior,refs=sends(r);for _,s in ipairs(prior) do if s.target_id==a.target_id then fail("CONFLICT","Send to target already exists.","Inspect list_sends and edit existing send.") end end
    if dry then return {target_id=a.target_id,gain_db=a.gain_db} end
    Session:add_internal_send(target,r:main_outs(),r)
    local after=sends(r);for _,s in ipairs(after) do if not refs[s.id] and s.target_id==a.target_id then handlers.set_send_gain({track_id=a.track_id,send_id=s.id,gain_db=a.gain_db},false);s.gain_db=a.gain_db;s.undoable=false;return s end end
    fail("OUTCOME_UNCERTAIN","No newly created send identified.","Inspect routing before retrying.")
  end)
  local function automation(a)
    local r=route(a.track_id);local c;local unit
    if a.control=='gain' then c=r:gain_control();unit='linear_gain'
    elseif a.control=='pan' then c=r:pan_azimuth_control();unit='normalized_azimuth'
    elseif a.control=='send' then local _,s=send({track_id=a.track_id,send_id=a.processor_id});c=s:amp():gain_control();unit='linear_gain'
    elseif a.control=='plugin' then local proc=plugin(a);number(a.parameter_index,0,65535,true);local _,p=plugin(a);param(p,a.parameter_index);local al,cl,pd=ARDOUR.LuaAPI.plugin_automation(proc,a.parameter_index);if not present(al) then fail("OPERATION_NOT_SUPPORTED","Plugin parameter has no automation.") end;return al,pd,'plugin_native'
    else fail("VALIDATION_ERROR","Invalid automation control.") end
    if not present(c) then fail("OPERATION_NOT_SUPPORTED","Control unavailable.") end;return c:alist(),c:desc(),unit,c
  end
  register('get_automation',false,function(a,dry)
    local al,pd,unit,c=automation(a);local values=array();if al:size()>10000 then fail("BACKEND_UNSUPPORTED","Automation exceeds read safety limit; range pagination needed.") end
    for ev in al:events():iter() do values[#values+1]={samples=ev.when:samples(),quarter_ticks=ev.when:ticks(),value=ev.value} end
    return {points=values,unit=unit,mode=c and tostring(c:automation_state()) or 'not_exposed',control_id=c and oid(c) or oid(al),minimum=pd.lower,maximum=pd.upper}
  end)
  local function automation_edit(a,dry,clear)
    local al,pd,unit=automation(a);local points={};local seen={}
    if not clear then
      if a.unit~=unit then fail("VALIDATION_ERROR","Automation unit mismatch.") end;list(a.points,10000)
      if a.replace and not a._confirm_delete and not dry then fail("VALIDATION_ERROR","Automation replacement requires confirm_delete.") end
      for _,p in ipairs(a.points) do local where=pos(p.position);number(p.value,pd.lower,pd.upper,pd.integer_step);local key=where:samples();if seen[key] then fail("VALIDATION_ERROR","Duplicate automation point position.") end;seen[key]=true;points[#points+1]={position=where,value=p.value} end
      table.sort(points,function(x,y) return x.position:samples()<y.position:samples() end)
      if a.interpolation~='linear' and a.interpolation~='discrete' then fail("VALIDATION_ERROR","Unsupported interpolation.") end
    end
    if not dry then
      local before=al:get_state();Session:begin_reversible_command('Ultra automation edit')
      local ok,err=pcall(function()
        if clear or a.replace then al:clear_list() end
        if not clear then al:set_interpolation(a.interpolation=='linear' and Evoral.InterpolationStyle.Linear or Evoral.InterpolationStyle.Discrete);for _,p in ipairs(points) do al:add(p.position,p.value,false,true) end end
      end)
      if not ok then
        local after=al:get_state();local cmd=al:memento_command(before,after);Session:add_command(cmd);Session:commit_reversible_command(nil)
        if Editor then Editor:undo(1) else fail("OUTCOME_UNCERTAIN","Automation edit failed without Editor rollback.") end
        fail("BACKEND_ERROR","Automation edit failed; native undo restored prior list.")
      end
      Session:add_command(al:memento_command(before,al:get_state()));Session:commit_reversible_command(nil)
    end
    return {point_count=#points,unit=unit,undoable=true}
  end
  register('create_automation_points',true,function(a,dry) return automation_edit(a,dry,false) end)
  register('clear_automation',true,function(a,dry) return automation_edit(a,dry,true) end,true)
  register('set_automation_mode',true,function(a,dry)
    local al,pd,unit,c=automation(a)
    if not c then
      local proc,p=plugin(a);local port=param(p,a.parameter_index);c=proc:to_automatable():automation_control(Evoral.Parameter(ARDOUR.AutomationType.PluginAutomation,0,port),false)
    end
    local modes={off=ARDOUR.AutoState.Off,play=ARDOUR.AutoState.Play,write=ARDOUR.AutoState.Write,touch=ARDOUR.AutoState.Touch,latch=ARDOUR.AutoState.Latch};if not modes[a.mode] then fail("VALIDATION_ERROR","Invalid automation mode.") end
    if not dry then c:set_automation_state(modes[a.mode]) end;return {mode=a.mode,unit=unit,undoable=false}
  end)
  register('get_meter_state',false,function(a,dry)
    local r=route(a.track_id);local meter=r:peak_meter();local values=array();for i=0,r:n_outputs():n_audio()-1 do values[#values+1]=meter:meter_level(i,ARDOUR.MeterType.MeterPeak) end;return {track_id=a.track_id,peaks_dbfs=values,unit='dBFS',observed_at=os.time()}
  end)
  register('undo',true,function(a,dry) if not Editor then fail("BACKEND_UNSUPPORTED","Native undo requires Editor context.") end;if not dry then Editor:undo(1) end;return {requested='undo',history_introspection=false} end)
  register('redo',true,function(a,dry) if not Editor then fail("BACKEND_UNSUPPORTED","Native redo requires Editor context.") end;if not dry then Editor:redo(1) end;return {requested='redo',history_introspection=false} end)
  local function inverse(command,a,preview)
    local v={};for k,x in pairs(a) do v[k]=x end
    if command=='set_plugin_parameters' then v.parameters=array();for _,c in ipairs(preview.parameters) do v.parameters[#v.parameters+1]={parameter_index=c.parameter_index,value=c.before,unit='plugin_native'} end
    elseif command=='set_track_gain' then v.gain_db=db(preview.before)
    elseif command=='set_track_pan' then v.pan=2*preview.before-1
    elseif command=='set_track_mute' or command=='set_track_solo' then v.enabled=preview.before>0
    elseif command=='set_plugin_enabled' then v.enabled=preview.before
    elseif command=='set_send_gain' then v.gain_db=preview.before
    elseif command=='rename_track' then v.name=preview.before
    else fail("OPERATION_NOT_SUPPORTED","Command is not compensable.") end
    return v
  end
  register('execute_batch',true,function(a,dry)
    name(a.name);list(a.operations,100);local previews=array()
    for _,op in ipairs(a.operations) do if not compensable[op.command] then fail("OPERATION_NOT_SUPPORTED","Batch command is not compensable.") end;if type(op.arguments)~='table' then fail("VALIDATION_ERROR","Invalid batch arguments.") end;previews[#previews+1]=handlers[op.command](op.arguments,true) end
    if dry then return {operations=previews,transaction_model='prevalidated compensable controls; no grouped native undo'} end
    local applied={};local results=array()
    for _,op in ipairs(a.operations) do
      local preview=handlers[op.command](op.arguments,true);local inv=inverse(op.command,op.arguments,preview);applied[#applied+1]={command=op.command,arguments=inv}
      local ok,result=pcall(handlers[op.command],op.arguments,false)
      if not ok then
        local restored=true;for i=#applied,1,-1 do local good=pcall(handlers[applied[i].command],applied[i].arguments,false);restored=restored and good end
        if not restored then fail("OUTCOME_UNCERTAIN","Batch compensation failed.","Inspect every affected control before continuing.") end
        fail("BACKEND_ERROR","Batch failed; compensation completed.")
      end
      results[#results+1]=result
    end
    return {operations=results,transaction_model='compensating controls; no grouped native undo',undoable=false}
  end)
  register('render_range',true,function(a,dry)
    local s,e=pos(a.start),pos(a['end']);if e:samples()<=s:samples() then fail("INVALID_TIME_POSITION","Export end must follow start.") end
    name(a.name);text(a.output_directory,4000)
    -- Python creates a fresh empty directory under the installed allowlisted roots.
    -- Bridge rechecks exact prefix with platform separator boundaries.
    local allowed=false;local path=a.output_directory:gsub('\\','/')
    if path:find('/%.%./') or path:sub(-3)=='/..' or path:find('://',1,true) then fail("PERMISSION_DENIED","Unsafe export path.") end
    for _,prefix in ipairs(config.export_roots or {}) do local p=prefix:gsub('\\','/'):gsub('/$','');if path:sub(1,#p+1)==p..'/' then allowed=true end end
    if not allowed then fail("PERMISSION_DENIED","Export path outside installed export roots.") end
    if dry then return {start_samples=s:samples(),end_samples=e:samples(),output_directory=a.output_directory,format_source='Ardour export preset'} end
    local ex=Session:simple_export();ex:set_folder(a.output_directory);ex:set_name(a.name);ex:set_range(s:samples(),e:samples())
    if a.preset_id and a.preset_id~='' then if type(a.preset_id)~='string' or not a.preset_id:match('^[%w%-]+$') or not ex:set_preset(a.preset_id) then fail("OBJECT_NOT_FOUND","Export preset not found.") end end
    if not ex:check_outputs() then fail("BACKEND_ERROR","Export master has no configured channels.") end
    if not ex:run_export() then fail("BACKEND_ERROR","Ardour export failed.","Inspect Ardour logs and the new output directory.") end
    return {output_directory=a.output_directory,start_samples=s:samples(),end_samples=e:samples(),format_source='Ardour export preset',undoable=false}
  end)
  local function command_list()
    local values=array();for command,_ in pairs(handlers) do
      if Editor or (command~='create_midi_region' and command~='undo' and command~='redo') then values[#values+1]=command end
    end;table.sort(values);return values
  end
  local function heartbeat()
    write('heartbeat.json',{protocol=1,epoch=epoch,time=os.time(),commands=command_list(),session_open=Session~=nil,revision=revision(),revision_scope='observed route mixer and region properties only',busy=busy})
  end
  -- Factory bytecode is the installed entrypoint. Everything needed is in this scope.
  return function(signal,ref,...)
    if busy then return end
    local now=os.time()
    if now~=last_heartbeat then local ok,err=pcall(heartbeat);if not ok then print('Ultra MCP heartbeat failure') end;last_heartbeat=now end
    local ok,data=pcall(read,'request.json');if not ok or not data then return end
    busy=true
    local request
    local status,result=pcall(function()
      request=decode(data)
      if type(request)~='table' or request.protocol~=1 or request.token~=config.token or request.epoch~=epoch then fail("PROTOCOL_ERROR","Protocol/token/epoch mismatch.") end
      text(request.id,64);if not request.id:match('^[a-f0-9]+$') then fail("PROTOCOL_ERROR","Invalid request ID.") end
      if type(request.expires)~='number' or request.expires<=os.time() or request.expires>os.time()+3600 then fail("IPC_TIMEOUT","Request deadline expired or invalid.") end
      local handler=handlers[request.command];if not handler then fail("OPERATION_NOT_SUPPORTED","Command not allowlisted.") end
      if type(request.arguments)~='table' or type(request.options)~='table' then fail("VALIDATION_ERROR","Invalid command envelope.") end
      session();observe()
      local options=request.options;local dry=options.dry_run==true
      if options.expected_revision and options.expected_revision~=NULL and options.expected_revision~=revision() then fail("CONFLICT","Observed session revision changed.") end
      if destructive[request.command] and not dry and options.confirm_delete~=true then fail("VALIDATION_ERROR","Explicit confirm_delete required.") end
      if mutations[request.command] and Session:actively_recording() and request.command~='stop' and request.command~='stop_recording' then fail("BUSY","Editing is blocked while actively recording.") end
      request.arguments._confirm_delete=options.confirm_delete==true
      assert(os.rename(root..'/request.json',root..'/processing.json'))
      local before=revision();local payload=handler(request.arguments,dry)
      local changes=array()
      if mutations[request.command] and not dry then
        generation=generation+1;last_signature=nil
        if payload.object_id and payload.property then changes[#changes+1]={object_id=payload.object_id,property=payload.property,before=payload.before,after=payload.after}
        else changes[#changes+1]={object_id=request.arguments.region_id or request.arguments.processor_id or request.arguments.track_id or ('session:'..epoch),property=request.command,before=NULL,after=payload} end
      end
      return {success=true,data=dry and {valid=true,preview=payload} or payload,revision_before=before,revision_after=revision(),changed_objects=changes,warnings=array()}
    end)
    if not status then
      local err=type(result)=='table' and result or {code='OUTCOME_UNCERTAIN',message='Bridge API call failed; inspect state before retrying.',action='Check Ardour Lua console and affected objects.',details={}}
      -- Error messages never include the private nonce or request contents.
      if type(result)~='table' then print('Ultra MCP API error: '..tostring(result)) end
      result={success=false,data={},revision_after=revision(),changed_objects=array(),warnings=array(),error=err}
    end
    local reply={protocol=1,id=request and request.id or 'invalid',epoch=epoch,result=result}
    local written=pcall(write,'response.json',reply)
    if written then os.remove(root..'/processing.json');os.remove(root..'/request.json') end
    busy=false
  end
end
