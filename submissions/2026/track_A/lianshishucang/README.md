# LianShiShuCang

A simple NFT marketplace project with three parts:

- Hardhat-based Solidity contracts for NFT minting, fixed-price listings, and auctions
- A Go backend built with Gin and GORM
- PostgreSQL for application data

## Project Structure

```text
.
├── backend/      # Go API server
├── contracts/    # Solidity smart contracts
├── frontend/     # Vite + React inventory demo UI
├── scripts/      # Hardhat deployment scripts
├── package.json  # Hardhat tasks and root helper scripts
└── hardhat.config.cjs
```

## Frontend Inventory Demo

The inventory UI lives in `frontend/` and runs as a standalone Vite app.

### Install frontend dependencies

```bash
npm --prefix ./frontend install
```

### Start the frontend demo

```bash
npm run dev:frontend
```

Or directly:

```bash
npm --prefix ./frontend run dev
```

### Optional frontend environment

The frontend inventory client reads `VITE_API_BASE_URL` and defaults to `http://localhost:8080`.

Example:

```bash
VITE_API_BASE_URL=http://localhost:8080 npm --prefix ./frontend run dev
```

### Demo vs live mode

- Without a JWT token, the page runs in demo mode with mock inventory data.
- Paste a valid backend JWT into the UI to load real collections from `/api/v1/collections` and enable live collection actions.

## Smart Contracts

The contracts under `contracts/` include:

- `LianShiNFT.sol`: ERC-721 NFT minting with token URI storage and ERC-2981 royalties
- `LianShiMarketplace.sol`: fixed-price listings, offers, and royalty/platform fee settlement
- `LianShiAuction.sol`: timed auctions, bidding, refunds, and settlement

## Backend

The backend server lives in `backend/` and starts from `backend/main.go`.

Current behavior:

- Connects to PostgreSQL through GORM
- Runs schema migration on startup
- Exposes REST endpoints under `/api/v1`
- Starts an on-chain event listener when contract and RPC settings are configured

Key public routes:

- `GET /api/v1/health`
- `GET /api/v1/auth/nonce/:address`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/:address`

Authenticated routes include profile, NFT, marketplace, and auction APIs.

## Environment Variables

The backend reads configuration from environment variables and optionally from `backend/.env`.

Common variables:

```env
SERVER_PORT=8080
DATABASE_URL=postgres://postgres:postgres@localhost:5432/lianshishucang?sslmode=disable
JWT_SECRET=change-me-in-production
ETHEREUM_RPC=https://eth-sepolia.g.alchemy.com/v2/demo
CHAIN_ID=11155111
NFT_CONTRACT=
MARKETPLACE_CONTRACT=
AUCTION_CONTRACT=
PLATFORM_FEE_BPS=250
FEE_RECIPIENT=0x0000000000000000000000000000000000000000
```

Do not commit real secrets or private keys.

## Local Development

### 1. Install JavaScript dependencies

```bash
npm install
```

### 2. Compile contracts

```bash
npm run compile
```

### 3. Start PostgreSQL

Create a local database named `lianshishucang` or update `DATABASE_URL` to match your environment.

### 4. Start the backend

```bash
cd backend
go run .
```

### 5. Deploy contracts

```bash
npm run deploy
```

For Sepolia:

```bash
npm run deploy:sepolia
```

## Notes

- `node_modules/`, local env files, and build artifacts should stay out of Git history
- The backend can run without blockchain listeners, but on-chain integration requires RPC and contract addresses
- Contract deployment configuration is defined in `hardhat.config.cjs`
