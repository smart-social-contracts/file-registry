.PHONY: build build-backend build-frontend deploy deploy-ic test clean

# Both artifacts a Casals sheet consumes as `local:` sources:
#   .basilisk/ic_file_registry/ic_file_registry.wasm   (registry.wasms)
#   frontend/dist                                       (registry.publish bundle)
build: build-backend build-frontend

# Build the Basilisk backend WASM. icp-cli's prebuilt recipe then installs
# the artifact at .basilisk/ic_file_registry/ic_file_registry.wasm.
build-backend:
	CANISTER_CANDID_PATH=./ic_file_registry.did python3 -m basilisk ic_file_registry src/main.py

# Build the SvelteKit UI into frontend/dist. `icp deploy` runs the same two
# commands itself (icp.yaml); this target is for the orchestrator scripts
# (realms/scripts/up.sh, gos-as-a-service/scripts/up.sh) that publish the
# dist through a Casals sheet. No VITE_CANISTER_ID: the id comes at runtime
# (ic_env cookie or /canister_ids.js, see frontend/src/lib/api.ts).
build-frontend:
	npm --prefix frontend ci
	npm --prefix frontend run build
	test -f frontend/dist/index.html

# Local deploy. The frontend is built by the asset-canister recipe (see icp.yaml),
# so only the backend is built here.
deploy: build-backend
	icp deploy

# Mainnet deploy.
deploy-ic: build-backend
	icp deploy --network ic

test:
	pytest -q

clean:
	rm -rf .basilisk frontend/dist frontend/.svelte-kit frontend/node_modules
