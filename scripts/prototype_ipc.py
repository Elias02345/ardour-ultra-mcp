"""Architecture-only loopback/mailbox latency; not an Ardour performance claim."""
import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path

async def mailbox(root, rounds=30):
    request, response = root/'request', root/'response'
    async def bridge():
        for _ in range(rounds):
            while not request.exists():
                await asyncio.sleep(.1)  # native EditorHook timer period
            value=json.loads(request.read_text());request.unlink()
            part=root/'response.part';part.write_text(json.dumps(value));part.replace(response)
    worker=asyncio.create_task(bridge());values=[]
    for i in range(rounds):
        started=time.perf_counter();part=root/'request.part';part.write_text(json.dumps({'id':i}));part.replace(request)
        while not response.exists():await asyncio.sleep(.005)
        assert json.loads(response.read_text())['id']==i;response.unlink();values.append((time.perf_counter()-started)*1000)
    await worker
    return values
class Echo(asyncio.DatagramProtocol):
    def connection_made(self,t):self.t=t
    def datagram_received(self,d,a):self.t.sendto(d,a)
class Client(asyncio.DatagramProtocol):
    def datagram_received(self,d,a):self.future.set_result(d)
async def main():
    loop=asyncio.get_running_loop();srv,_=await loop.create_datagram_endpoint(Echo,local_addr=('127.0.0.1',0))
    cli,c=await loop.create_datagram_endpoint(Client,remote_addr=srv.get_extra_info('sockname'));values=[]
    for _ in range(100):
        c.future=loop.create_future();t=time.perf_counter();cli.sendto(b'/transport_frame\0\0\0\0,\0\0\0');await c.future;values.append((time.perf_counter()-t)*1000)
    cli.close();srv.close()
    with tempfile.TemporaryDirectory() as p:mail=await mailbox(Path(p))
    result={'scope':'synthetic transport only; no Ardour','osc_udp_echo_ms':{'median':statistics.median(values),'max':max(values)},'mailbox_100ms_hook_ms':{'median':statistics.median(mail),'max':max(mail)},'hybrid':'OSC realtime telemetry, mailbox acknowledged deep editing'}
    Path('artifacts/architecture-prototype.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
asyncio.run(main())
