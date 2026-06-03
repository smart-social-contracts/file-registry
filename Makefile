.PHONY: build deploy deploy-ic test clean

# Build the Basilisk backend WASM. icp-cli's prebuilt recipe then installs
# the artifact at .basilisk/ic_file_registry/ic_file_registry.wasm.
build:
	CANISTER_CANDID_PATH=./ic_file_registry.did python3 -m basilisk ic_file_registry src/main.py

# Local deploy. The frontend is built by the asset-canister recipe (see icp.yaml).
deploy: build
	icp deploy

# Mainnet deploy.
deploy-ic: build
	icp deploy --network ic

test:
	pytest -q

clean:
	rm -rf .basilisk frontend/dist frontend/.svelte-kit frontend/node_modules
