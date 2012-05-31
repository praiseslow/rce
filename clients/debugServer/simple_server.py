#!/usr/bin/env python
from twisted.internet import reactor
from autobahn.websocket import WebSocketServerFactory, WebSocketServerProtocol, listenWS

import json
import uuid


class EchoServerProtocol(WebSocketServerProtocol):

	incoming_msg_count = 0 

	cmd_CSR = {"type":"CSR", "dest":None, "orig":"$$$$$$", "data":{"containerID":None}}

	def onConnect(self, _):
		print 'Connection established'
		  
	def onMessage(self, msg, binary):
		self.incoming_msg_count += 1
		print('received Message # '+str(self.incoming_msg_count))

		if not binary:
			cmd = json.loads(msg)
			if cmd['type']=="CS":
				print "received container creation method"
				self.cmd_CSR['dest']=cmd['orig']
				self.cmd_CSR['data']['containerID']=uuid.uuid4().hex
				self.sendMessage(json.dumps(self.cmd_CSR))
			else:
				pass
		else:
			pass


           
if __name__ == '__main__':
	factory = WebSocketServerFactory("ws://localhost:9000")
	factory.protocol = EchoServerProtocol
	listenWS(factory)
	reactor.run()
