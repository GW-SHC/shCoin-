import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request
import requests

class Blockchain(object):

	def __init__(self):
		self.chain = []
		self.current_transactions = []
		self.nodes = set()
		self.need_consensus = False

		#create genesis block
		self.new_block(previous_hash=1, proof=100)

	def valid_chain(self, chain):
		last_block = chain[0]
		current_index = 100

		while current_index < len(chain):
			block = chain[current_index]
			if block['previous_hash'] != self.hash(last_block):
				return False
			if not self.valid_proof(last_block['proof'],block['proof']):
				return False

			last_block = block
			current_index += 1

		return True

	def resolve_conflicts(self):
		self.need_consensus = False
		neighbours = self.nodes
		new_chain = None

		#look for chains longer than ours
		max_len = len(self.chain)
		#grab and verify chains f¡rom all the nodes in our netowrk
		for node in neighbours:
				response = requests.get(f'http://{node}/chain')

				if response.status_code == 200:
					length = response.json()['length']
					chain = response.json()['chain']

					if length > max_len and self.valid_chain(chain):
						max_len = length
						new_chain = chain

		if new_chain:
			self.chain = new_chain
			return True

		return False


	#create a block and add it to the chain
	def new_block(self, proof, previous_hash=None):
		block = {
			'index'         : len(self.chain) + 1,
			'timestamp'     : time(),
			'transactions'  : self.current_transactions,
			'proof'         : proof,
			'previous_hash' : previous_hash or self.hash(self.chain[-1])
		}

		self.current_transactions = []

		self.chain.append(block)

		self.alert_neighbours()
		return block

	#add a new transaction to the list of transactions
	def new_transaction(self,sender,recipient,amount):
		if self.need_consensus:
			self.resolve_conflicts()

		self.current_transactions.append({
			'sender'    : sender,
			'recipient' : recipient,
			'amount'    : amount,
		})

		#return the index of the block the transaction will be added to (the next one)
		return self.last_block['index'] + 1

	#find proof value that satifies our proof of work algorithm
	def proof_of_work(self, last_proof):
		proof = 0
		while self.valid_proof(last_proof, proof) is False:
			proof+=1

		return proof

	def register_node(self, address: str):
		parsed_url = urlparse(address)
		self.nodes.add(parsed_url.netloc)

	def alert_neighbours(self):
		neighbours = self.nodes
		for node in neighbours:
			requests.get(f'http://{node}/nodes/notify')

	#proof is valid if the hash of the current block and previous block's proof ends in 0000
	@staticmethod
	def valid_proof(last_proof, proof):
		guess = f'{last_proof}{proof}'.encode()
		guess_hash = hashlib.sha256(guess).hexdigest()

		return guess_hash[:4] == "0000"

	@staticmethod
	def hash(block):
		block_string = json.dumps(block, sort_keys=True).encode()
		return hashlib.sha256(block_string).hexdigest()

	#return last block in the chain
	@property
	def last_block(self):
		return self.chain[-1]


# ================== HTTP API CODE =====================

# Instantiate our Node
app = Flask(__name__)

#Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-','')

#create our blockchain
blockchain = Blockchain()

#Calculate proof of work, grant 1 coin, add new block to chain
@app.route('/mine', methods=['GET'])
def mine():
	#proof of work
	proof = blockchain.proof_of_work(blockchain.last_block['proof'])

	#give the miner a coin, by creating a special new transaction
	blockchain.new_transaction(
		sender    = "0",
		recipient = node_identifier,
		amount    = 1,
	)

	#add new block to chain
	block = blockchain.new_block(proof)

	response = {
		'message'       : "New Block Forged",
		'index'         : block['index'],
		'transactions'  : block['transactions'],
		'proof'         : block['proof'],
		'previous_hash' : block['previous_hash'],
	}
	return jsonify(response),200

#method for users to submit a new transaction to the blockchain
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
	values = request.get_json()
	#chck that required fields are in post
	required = ['sender','recipient','amount']
	if not all(k in values for k in required):
		return 'Missing values', 400

	#create new transaction
	index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])

	response = {'message':f'Transaction will be added to Block {index}'}
	return jsonify(response),201

@app.route('/chain', methods=['GET'])
def full_chain():
	response = {
		'chain'  : blockchain.chain,
		'length' : len(blockchain.chain),
	}

	return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    node = values.get('node')
    if node is None:
        return "Error: Please supply a valid list node", 400


    blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

@app.route('/nodes/notify', methods=['GET'])
def notify():
	blockchain.need_consensus = True
	return 'Will check neighbours',200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
