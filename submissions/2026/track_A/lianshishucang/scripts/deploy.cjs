const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);
  console.log("Account balance:", (await deployer.provider.getBalance(deployer.address)).toString());

  const LianShiNFT = await hre.ethers.getContractFactory("LianShiNFT");
  const nft = await LianShiNFT.deploy();
  await nft.waitForDeployment();
  const nftAddress = await nft.getAddress();
  console.log("LianShiNFT deployed to:", nftAddress);

  const platformFeeBps = 250;
  const feeRecipient = deployer.address;

  const LianShiMarketplace = await hre.ethers.getContractFactory("LianShiMarketplace");
  const marketplace = await LianShiMarketplace.deploy(feeRecipient, platformFeeBps);
  await marketplace.waitForDeployment();
  const marketplaceAddress = await marketplace.getAddress();
  console.log("LianShiMarketplace deployed to:", marketplaceAddress);

  const bidIncrementBps = 500;

  const LianShiAuction = await hre.ethers.getContractFactory("LianShiAuction");
  const auction = await LianShiAuction.deploy(feeRecipient, platformFeeBps, bidIncrementBps);
  await auction.waitForDeployment();
  const auctionAddress = await auction.getAddress();
  console.log("LianShiAuction deployed to:", auctionAddress);

  console.log("\nDeployment Summary:");
  console.log("-------------------");
  console.log("Network:", hre.network.name);
  console.log("LianShiNFT:", nftAddress);
  console.log("LianShiMarketplace:", marketplaceAddress);
  console.log("LianShiAuction:", auctionAddress);
  console.log("Platform Fee (bps):", platformFeeBps);
  console.log("Bid Increment (bps):", bidIncrementBps);
  console.log("Fee Recipient:", feeRecipient);

  console.log("\nEnvironment variables for backend:");
  console.log(`NFT_CONTRACT=${nftAddress}`);
  console.log(`MARKETPLACE_CONTRACT=${marketplaceAddress}`);
  console.log(`AUCTION_CONTRACT=${auctionAddress}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
