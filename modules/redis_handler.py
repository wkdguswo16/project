import redis as rs
import threading

class RedisHandler(threading.Thread, rs.StrictRedis):
    def __init__(self, *args, **kwargs):
        rs.StrictRedis.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)
        self.ps = self.pubsub()
        self.func = None
        
    def listen(self, subscribe:str, func=None):
        self.ps.psubscribe(subscribe)
        self.func = func
        self.start()

    def run(self):
        while True:
            for m in self.ps.listen():
                if 'pmessage' != m['type']:
                    continue
                if '__admin__' == m['channel'] and 'shutdown' == m['data']:
                    print('Listener shutting down, bye bye.')
                    break
                if not self.func:
                    print(m)
                    break
                channel = m["channel"].decode("utf-8")
                data = m["data"].decode("utf-8")
                self.func(channel, data)