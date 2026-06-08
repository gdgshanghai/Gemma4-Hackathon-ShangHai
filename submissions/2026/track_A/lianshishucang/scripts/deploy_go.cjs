const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const GOToken = await hre.ethers.getContractFactory("GOToken");
  const go = await GOToken.deploy();
  await go.waitForDeployment();
  const goAddress = await go.getAddress();
  console.log("GOToken deployed to:", goAddress);

  const userAddr = "0xBD004b7611d95c40c3D9821C43482779dc75b07d";
  const mintTx = await go.mint(userAddr, hre.ethers.parseUnits("10000", 18));
  await mintTx.wait();
  console.log("Minted 10000 GO to", userAddr);

  const userBalance = await go.balanceOf(userAddr);
  console.log("User GO balance:", hre.ethers.formatUnits(userBalance, 18));
  console.log("\nGO Token Address:", goAddress);
}

main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
