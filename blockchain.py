import hashlib
import json
from time import time
from uuid import uuid4

from flask import Flask, jsonify, request

#define server endpoints - Mine operation, calculate proof, give coin, add block to chain
#new transaciton operation post request that adds new transaction to the list.
class Blockchain(object):

	def __init__(self):
		self.chain = []
		self.current_transactions = []

		#create genesis block
		self.new_block(previous_hash=1, proof=100)

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
		return block

	#add a new transaction to the list of transactions
	def new_transaction(self,sender,recipient,amount):
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

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)
