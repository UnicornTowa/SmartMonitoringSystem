import os
from asyncio import Task, _register_task, as_completed, ensure_future, get_event_loop, new_event_loop, set_event_loop
from dataclasses import dataclass

from pyipv8.ipv8.community import Community
from pyipv8.ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition
from pyipv8.ipv8.configuration import Bootstrapper, BootstrapperDefinition, default_bootstrap_defs
from pyipv8.ipv8.lazy_community import lazy_wrapper
from pyipv8.ipv8.messaging.payload_dataclass import overwrite_dataclass
from pyipv8.ipv8_service import IPv8
from pyipv8.ipv8.peer import Peer

import string
import random
from threading import Thread
from threading import Event

from base64 import b64encode
from time import time

dataclass = overwrite_dataclass(dataclass)  # Enhance normal dataclasses for IPv8 (see the serialization documentation)

@dataclass(msg_id=1)  # The (byte) value 1 identifies this message and must be unique per community
class MyMessage:
	text: str

class MyPeer:
	def __init__(self, peer: Peer, online: bool):
		self.peer = peer
		self.online = online
	def __eq__(self, other):
		self.peer.address
		return self.peer.mid == other.peer.mid
all_peers = dict()

class MyCommunity(Community):
	community_id = bytes([254,10,128,88,75,5,188,130,10,151,179,240,26,88,125,221,44,223,239,217])

	def __init__(self, my_peer, endpoint, network):
		super().__init__(my_peer, endpoint, network)
		self.add_message_handler(MyMessage, self.on_message)

	def started(self):
		async def print_ip():
			ip = self.my_peer.address
			if ip[0] != "0.0.0.0":
				print("my ip: ", ip[0], ':', ip[1], sep="")
				self.cancel_pending_task("print_ip")

		async def save_peers():
			for p in all_peers.values():
				p.online = False
			for p in self.get_peers():
				all_peers[p.mid] = MyPeer(p, time() - p.last_response < 3)

			#for p in all_peers.values():
			#	print(b64encode(p.peer.mid).decode('utf-8'), "\t: ", p.online)

		self.register_task("print_ip", print_ip, interval=0.5, delay=1)
		self.register_task("save_peers", save_peers, interval=5, delay=5)

	def send(self, item):
		for p in self.get_peers():
			self.ez_send(p, MyMessage(item))

	@lazy_wrapper(MyMessage)
	def on_message(self, peer, payload):
		print(peer, ':', payload.text)


def open_peer():
	class ipv8_holder:
		ipv8: IPv8 = None
	holder = ipv8_holder()
	event = Event()

	async def start_peer():
		builder = ConfigBuilder().clear_keys().clear_overlays()
		builder.add_key("my peer", "medium", "key.pem")
		builder.add_overlay(
			"MyCommunity",
			"my peer",
			[WalkerDefinition(Strategy.RandomWalk, 10, {'timeout': 3.0})],
			[BootstrapperDefinition(Bootstrapper.UDPBroadcastBootstrapper, {})],
			{}, [('started',)])
		ipv8 = IPv8(builder.finalize(), extra_communities={'MyCommunity': MyCommunity})
		await ipv8.start()
		return ipv8

	def work():
		set_event_loop(new_event_loop())
		future = ensure_future(start_peer())
		get_event_loop().run_until_complete(future)
		holder.ipv8 = future.result()
		event.set()
		get_event_loop().run_forever()
	
	Thread(target = work).start()
	event.wait()
	return holder.ipv8
		

ipv8 = open_peer()
while True:
	ipv8.get_overlay(MyCommunity).send(input())
