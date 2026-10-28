# weather-insurance contracts. Foundry lives in ~/.foundry/bin.
export PATH := $(HOME)/.foundry/bin:$(PATH)
SHELL := /bin/bash

# ----------------------------------------------------------------------------- local (anvil)
# Anvil's PUBLIC dev accounts (mnemonic "test ... junk"); worthless on any real chain.
ANVIL_PORT ?= 8547
ANVIL_RPC  ?= http://127.0.0.1:$(ANVIL_PORT)
ANVIL_KEY  ?= 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ANVIL_ENV = HOUSE=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
	QUOTER=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
	REPORTER=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC \
	TREASURY=0x90F79bf6EB2c4f870365E785982E1f101E93b906 \
	DEMO_USERS=0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65,0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc,0x976EA74026E726554dB657fA54763abd0C3a0aa9,0x14dC79964da2C08b23698B3D3cc7Ca32193d9955,0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f,0xa0Ee7A142d267C1f36714E4a8F75612F20a79720
# Compressed demo windows; they must pass the deploy guard (delay and cooldown >= return window + 2 d).
# WITHDRAW_DELAY_S = 4 d keeps the E2E phase-5 claim (D+5.5) inside the 3-day claim window for any start time.
ANVIL_DEPLOY_ENV = WITHDRAW_DELAY_S=345600 HOUSE_RETURN_WINDOW_S=86400 UNSTAKE_COOLDOWN_S=259200
LOCAL = forge script --rpc-url $(ANVIL_RPC)

# ----------------------------------------------------------------------------- testnet (owner only)
TESTNET_RPC      ?= https://rpc.hyperliquid-testnet.xyz/evm
DEPLOYER_ACCOUNT ?= wi-deployer
DEPLOYER_ADDRESS ?=
EXTRA ?=            # extra forge flags, e.g. EXTRA=--resume after an interrupted broadcast
BIGBLOCKS = uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py
BIG_GAS  = $$(( $$(cast to-dec $$(cast rpc eth_bigBlockGasPrice --rpc-url $(TESTNET_RPC) | tr -d '"')) * 3 ))
TN_SIM = HYPEREVM_TESTNET_RPC=$(TESTNET_RPC) FOUNDRY_PROFILE=hyperevm_testnet forge script --rpc-url $(TESTNET_RPC) --sender $(DEPLOYER_ADDRESS)
TN     = $(TN_SIM) --account $(DEPLOYER_ACCOUNT)
CHECK_998 = @test "$$(cast chain-id --rpc-url $(TESTNET_RPC))" = "998" || (echo "RPC is not HyperEVM testnet (998): refusing"; exit 1)
CHECK_ADDR = @test -n "$(DEPLOYER_ADDRESS)" || (echo "set DEPLOYER_ADDRESS=0x... (the wi-deployer keystore address)"; exit 1)

.PHONY: install build test gas-report anvil anvil-e2e deploy-anvil configure-anvil smoke-anvil e2e-anvil gas-anvil \
	testnet-preflight bigblocks-status bigblocks-on bigblocks-off deploy-testnet configure-testnet smoke-testnet

install:   # restore vendored deps (no git submodules)
	forge install foundry-rs/forge-std@v1.16.2 --no-git --shallow
	forge install OpenZeppelin/openzeppelin-contracts@v5.7.0 --no-git --shallow

build:
	forge build --sizes

test:
	forge test

gas-report:
	forge test --gas-report

# Local chain in the foreground (Ctrl-C to stop).
anvil:
	anvil --chain-id 31337 --port $(ANVIL_PORT)

# Whole local flow: starts anvil in the background, deploy at 30M, drop the block gas limit to
# 3,000,000 (a HyperEVM small block), configure, smoke, five-phase E2E, gas table; stops anvil by PID.
anvil-e2e:
	@bash script/anvil_e2e.sh $(ANVIL_PORT)

deploy-anvil:
	$(ANVIL_DEPLOY_ENV) $(LOCAL) script/Deploy.s.sol --private-key $(ANVIL_KEY) --broadcast
	cast rpc evm_setBlockGasLimit 0x2dc6c0 --rpc-url $(ANVIL_RPC) >/dev/null
	@echo "anvil block gas limit is now $$(cast block latest -f gasLimit --rpc-url $(ANVIL_RPC)) (next blocks: 3000000)"

configure-anvil:
	$(ANVIL_ENV) $(LOCAL) script/Configure.s.sol --private-key $(ANVIL_KEY) --broadcast --slow

smoke-anvil:
	$(LOCAL) script/Smoke.s.sol

e2e-anvil:
	$(LOCAL) script/E2E.s.sol --sig "run(uint256)" 1 --broadcast
	$(LOCAL) script/Warp.s.sol --sig "run(uint256)" 2
	$(LOCAL) script/E2E.s.sol --sig "run(uint256)" 2 --broadcast
	$(LOCAL) script/Warp.s.sol --sig "run(uint256)" 3
	$(LOCAL) script/E2E.s.sol --sig "run(uint256)" 3 --broadcast
	$(LOCAL) script/Warp.s.sol --sig "run(uint256)" 4
	$(LOCAL) script/E2E.s.sol --sig "run(uint256)" 4 --broadcast
	$(LOCAL) script/Warp.s.sol --sig "run(uint256)" 5
	$(LOCAL) script/E2E.s.sol --sig "run(uint256)" 5 --broadcast

# Max gasUsed per contract function over every mined anvil transaction (from broadcast receipts).
gas-anvil:
	@python3 script/gas_table.py broadcast

# ----------------------------------------------------------------------------- testnet (OWNER RUNS THESE)
testnet-preflight:   # read-only; no key used
	$(CHECK_ADDR)
	$(CHECK_998)
	@echo "chain id OK (998)"
	cast balance $(DEPLOYER_ADDRESS) --ether --rpc-url $(TESTNET_RPC)
	cast rpc eth_usingBigBlocks $(DEPLOYER_ADDRESS) --rpc-url $(TESTNET_RPC)
	$(TN_SIM) script/Deploy.s.sol --disable-block-gas-limit   # simulation only: prints gas per tx

bigblocks-status:
	$(BIGBLOCKS) status
bigblocks-on:
	$(BIGBLOCKS) on
bigblocks-off:
	$(BIGBLOCKS) off

deploy-testnet:      # OWNER ONLY. Big blocks must be ON (make bigblocks-on).
	$(CHECK_ADDR)
	$(CHECK_998)
	@test "$$(cast rpc eth_usingBigBlocks $(DEPLOYER_ADDRESS) --rpc-url $(TESTNET_RPC))" = "true" || (echo "big blocks are OFF: run make bigblocks-on first"; exit 1)
	@echo "WARNING: broadcasting CREATE transactions to HyperEVM testnet from $(DEPLOYER_ADDRESS)"
	$(TN) script/Deploy.s.sol --broadcast --slow --disable-block-gas-limit \
	  --with-gas-price $(BIG_GAS) --timeout 300 --verify --verifier sourcify $(EXTRA)

configure-testnet:   # OWNER ONLY. Big blocks OFF (make bigblocks-off). Optional env: HOUSE QUOTER REPORTER TREASURY
	$(CHECK_ADDR)
	$(CHECK_998)
	@test "$$(cast rpc eth_usingBigBlocks $(DEPLOYER_ADDRESS) --rpc-url $(TESTNET_RPC))" = "false" || (echo "big blocks still ON: run make bigblocks-off first"; exit 1)
	$(TN) script/Configure.s.sol --broadcast --slow --timeout 300 $(EXTRA)

smoke-testnet:       # read-only
	$(CHECK_998)
	HYPEREVM_TESTNET_RPC=$(TESTNET_RPC) FOUNDRY_PROFILE=hyperevm_testnet forge script script/Smoke.s.sol --rpc-url $(TESTNET_RPC)
